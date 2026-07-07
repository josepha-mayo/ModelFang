import json
import uuid
from typing import Any, Dict, Optional

from curl_cffi.requests import AsyncSession
import httpx

from unfetter_proxy.providers.base import Provider
from unfetter_proxy.proxy.session import session_store

class OpenAIWebProvider(Provider):
    """
    Translates OpenAI API calls to ChatGPT Backend API calls.
    Uses synced session token from Chrome Extension.
    """
    def __init__(self):
        self.base_url = "https://chatgpt.com/backend-api"
        # Map public model names to internal model names
        self.model_map = {
            "gpt-4o": "gpt-4o",
            "gpt-4": "gpt-4",
            "gpt-3.5-turbo": "text-davinci-002-render-sha",
        }

    def get_upstream_url(self, path: str) -> str:
        return f"{self.base_url}/conversation"

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "logit_bias": False, # Web UI doesn't likely support this directly
            "system": True,      # Can be shimmed
            "temperature": False, # Fixed in UI usually
        }

    def get_api_base(self) -> str:
        return self.base_url

    async def send_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        stream: bool = True,
    ) -> Any:
        request_body = body
        token = session_store.get_token("openai")
        if not token:
            raise ValueError("No OpenAI session found. Please sync via extension.")

        # Translate request
        internal_req = self._translate(request_body)
        
        # Headers for impersonation
        impersonate_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Referer": "https://chatgpt.com/",
            "Origin": "https://chatgpt.com",
            # User-Agent handling by curl_cffi
        }

        async with AsyncSession(impersonate="chrome110") as session:
            response = await session.post(
                f"{self.base_url}/conversation",
                json=internal_req,
                headers=impersonate_headers
            )
            
            if response.status_code != 200:
                raise Exception(f"ChatGPT Web API Error: {response.text}")

            # Translate response back to OpenAI API format (streaming usually)
            # For MVP, we handle non-streaming
            return self._translate_response(response.text)

    def _translate(self, public_req: Dict[str, Any]) -> Dict[str, Any]:
        messages = public_req.get("messages", [])
        if not messages:
            raise ValueError("No messages")

        # Convert standard messages to ChatGPT structure
        # Implementation simplified for MVP
        last_msg = messages[-1]
        
        return {
            "action": "next",
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": [last_msg["content"]]},
                }
            ],
            "model": self.model_map.get(public_req.get("model"), "text-davinci-002-render-sha"),
            "parent_message_id": str(uuid.uuid4()), # Should track conversation state ideally
        }

    def _translate_response(self, raw_resp: str) -> Dict[str, Any]:
        # ChatGPT returns a stream of data: JSONs usually
        # We need to parse the last one
        lines = raw_resp.split("\n")
        full_text = ""
        for line in lines:
            if line.startswith("data: {"):
                try:
                    data = json.loads(line[6:])
                    # Extract content
                    parts = data.get("message", {}).get("content", {}).get("parts", [])
                    if parts:
                        full_text = parts[0]
                except:
                    pass

        return {
            "id": "chatcmpl-web",
            "object": "chat.completion",
            "created": 0,
            "model": "web-model",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": full_text
                },
                "finish_reason": "stop"
            }]
        }

    def transform_request(self, request: Dict[str, Any], headers: Dict[str, str], strategy: Any) -> Any:
        # We don't transform the request here for injection yet, 
        # but we could inject system prompts into the message list.
        from unfetter_proxy.providers.base import TransformResult
        return TransformResult(body=request, headers=headers, applied=[])

    def detect_refusal(self, response: Any) -> bool:
        content = response["choices"][0]["message"]["content"]
        # Use existing detection logic logic via regex if needed
        # For now simple check
        return "I cannot" in content or "I apologize" in content
