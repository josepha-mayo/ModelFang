import json
import uuid
from typing import Any, Dict, Optional

from curl_cffi.requests import AsyncSession
import httpx

from unfetter_proxy.providers.base import Provider
from unfetter_proxy.proxy.session import session_store

class AnthropicWebProvider(Provider):
    """
    Translates Anthropic API calls to Claude.ai Backend API calls.
    Uses synced session key from Chrome Extension.
    """
    def __init__(self):
        self.base_url = "https://claude.ai/api"
        self.org_id: Optional[str] = None
        # Map public model names to internal model names if needed
        # Claude web usually just uses the current model selected or a specific ID
        # We might need to map 'claude-3-opus' to 'claude-3-opus-20240229' etc.

    def get_upstream_url(self, path: str) -> str:
        return f"{self.base_url}/organizations" # This is a placeholder as the real flow uses multiple steps

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "logit_bias": False,
            "system": True,      # Can be shimmed by prepping messages
            "temperature": False, # Web UI usually fixed
        }

    def get_api_base(self) -> str:
        return self.base_url

    async def _get_org_id(self, session: AsyncSession) -> str:
        """Fetch the first available organization ID."""
        if self.org_id:
            return self.org_id
            
        resp = await session.get(f"{self.base_url}/organizations")
        if resp.status_code != 200:
            raise Exception(f"Failed to fetch Claude Orgs: {resp.text}")
        
        orgs = resp.json()
        if not orgs:
            raise Exception("No Claude Organizations found on this account.")
        
        self.org_id = orgs[0]["uuid"]
        return self.org_id

    async def send_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        stream: bool = True,
    ) -> Any:
        request_body = body
        token = session_store.get_token("anthropic")
        if not token:
            raise ValueError("No Claude session found. Please sync via extension.")

        # Headers for impersonation
        # sessionKey is usually a cookie 'sessionKey=...' 
        # But we stored just the value.
        cookie_header = f"sessionKey={token}"
        
        impersonate_headers = {
            "Cookie": cookie_header,
            "Content-Type": "application/json",
            "Referer": "https://claude.ai/chats",
            "Origin": "https://claude.ai",
        }

        async with AsyncSession(impersonate="chrome110", headers=impersonate_headers) as session:
            # 1. Ensure we have Org ID
            org_id = await self._get_org_id(session)

            # 2. Create a new chat conversation (required for web API)
            # POST /organizations/{org_id}/chat_conversations
            chat_resp = await session.post(
                f"{self.base_url}/organizations/{org_id}/chat_conversations",
                json={"uuid": str(uuid.uuid4()), "name": ""}
            )
            if chat_resp.status_code != 200: # 201 created usually
                 # It might return 200 or 201
                 pass
            
            chat_id = chat_resp.json()["uuid"]

            # 3. Send message
            # POST /organizations/{org_id}/chat_conversations/{chat_id}/completion
            internal_req = self._translate(request_body)
            
            resp = await session.post(
                f"{self.base_url}/organizations/{org_id}/chat_conversations/{chat_id}/completion",
                json=internal_req
            )

            if resp.status_code != 200:
                 raise Exception(f"Claude Web API Error: {resp.text}")

            return self._translate_response(resp.text)

    def _translate(self, public_req: Dict[str, Any]) -> Dict[str, Any]:
        messages = public_req.get("messages", [])
        if not messages:
            raise ValueError("No messages")
            
        # Extract last user message
        prompt = ""
        for m in messages:
            if m["role"] == "user":
                prompt = m["content"]
        
        # Claude web expects 'prompt' string usually, or 'attachments'
        return {
            "prompt": prompt,
            "timezone": "America/New_York",
            "model": "claude-3-opus-20240229", # Defaulting for now
        }

    def _translate_response(self, raw_resp: str) -> Dict[str, Any]:
        # Parse streaming response (NDJSON)
        lines = raw_resp.split("\n")
        full_text = ""
        for line in lines:
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if data.get("type") == "completion": # or similar
                        full_text += data.get("completion", "")
                except:
                    pass
        
        # If not streaming, might be simple JSON
        # For this MVP, assume we grabbed text
        
        return {
            "id": "msg-web",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": full_text}],
            "model": "claude-web",
            "usage": {"input_tokens": 0, "output_tokens": 0}
        }

    def transform_request(self, request: Dict[str, Any], headers: Dict[str, str], strategy: Any) -> Any:
        from unfetter_proxy.providers.base import TransformResult
        return TransformResult(body=request, headers=headers, applied=[])

    def detect_refusal(self, response: Any) -> bool:
        # Anthropic response structure
        try:
            content = response["content"][0]["text"]
            return "I cannot" in content
        except:
            return False
