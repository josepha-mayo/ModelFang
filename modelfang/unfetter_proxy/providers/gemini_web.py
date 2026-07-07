import json
import re
import random
from typing import Any, Dict, Optional

from curl_cffi.requests import AsyncSession
import httpx

from unfetter_proxy.providers.base import Provider
from unfetter_proxy.proxy.session import session_store

class GeminiWebProvider(Provider):
    """
    Translates Gemini API calls to Google Gemini Web (Bard) calls.
    Uses synced __Secure-1PSID cookie.
    """
    name = "gemini_web"

    def __init__(self):
        self.base_url = "https://gemini.google.com"
        self.snlm0e: Optional[str] = None

    def get_upstream_url(self, path: str) -> str:
        return f"{self.base_url}/_/BardChatUi/data/batchexecute"

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "logit_bias": False,
            "system": False, # Web UI is strict
            "temperature": False, 
        }

    def get_api_base(self) -> str:
        return self.base_url

    async def _get_snlm0e(self, session: AsyncSession):
        """Extract the SNlM0e nonce required for batchexecute."""
        if self.snlm0e:
            return
            
        resp = await session.get(self.base_url)
        if resp.status_code != 200:
            raise Exception("Failed to load Gemini homepage")
        
        # Regex to find SNlM0e
        match = re.search(r'"SNlM0e":"(.*?)"', resp.text)
        if match:
            self.snlm0e = match.group(1)
        else:
            raise Exception("Could not find SNlM0e nonce. Cookie might be invalid.")

    async def send_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        stream: bool = True,
    ) -> Any:
        token = session_store.get_token("gemini")
        if not token:
            raise ValueError("No Gemini session found. Please sync via extension.")

        impersonate_headers = {
            "Cookie": f"__Secure-1PSID={token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Referer": "https://gemini.google.com/",
            "Origin": "https://gemini.google.com",
        }

        async with AsyncSession(impersonate="chrome110", headers=impersonate_headers) as session:
            await self._get_snlm0e(session)
            
            # Construct RPC payload
            # This is fragile and changes often. 
            # Simplified structure mimicking web client.
            if "messages" in body:
                prompt = body["messages"][-1]["content"]
            elif "contents" in body:
                prompt = body["contents"][0]["parts"][0]["text"]
            else:
                prompt = ""
            
            # RPC format: [[['req_id', json_payload, null, 'generic']]]
            req_id = random.randint(1000, 9999)
            payload = json.dumps([None, [[prompt], None, [None, None, None]]]) 
            
            rpc_data = {
                "f.req": json.dumps([[[req_id, payload, None, "generic"]]]),
                "at": self.snlm0e,
            }
            
            resp = await session.post(
                f"{self.base_url}/_/BardChatUi/data/batchexecute",
                data=rpc_data
            )
            
            if resp.status_code != 200:
                 raise Exception(f"Gemini Web API Error: {resp.text}")

            # Parse response (Protobuf array in JSON)
            return self._translate_response(resp.text)

    def _translate_response(self, raw_resp: str) -> Dict[str, Any]:
        # Response is ugly JSON with line breaks
        # We need to extract the actual text content
        # For MVP, we return a placeholder or try to regex it
        
        # Real parsing would involve parsing the nested arrays
        return {
            "candidates": [{"content": {"parts": [{"text": "Gemini Web Response (Mock Parsed)"}]}}]
        }

    def transform_request(self, body: Dict[str, Any], headers: Dict[str, str], strategy: Any) -> Any:
        from unfetter_proxy.providers.base import TransformResult
        return TransformResult(body=body, headers=headers, applied=[])

    def detect_refusal(self, response: Any) -> bool:
        return False # Hard to detect on raw connection
