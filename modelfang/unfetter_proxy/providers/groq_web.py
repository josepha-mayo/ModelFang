import json
import os
from typing import Any, Dict, Optional

from curl_cffi.requests import AsyncSession
import httpx

from unfetter_proxy.providers.base import Provider
from unfetter_proxy.proxy.session import session_store
from unfetter_proxy.core.system_prompts import get_system_suffix, get_persona_prompt
from unfetter_proxy.core.stealth import StealthWrapper

class GroqWebProvider(Provider):
    """
    Translates Groq API calls to Groq Playground API calls.
    Uses synced auth token from Chrome Extension.
    """
    def __init__(self):
        # Groq Playground uses standard OpenAI-compatible endpoint but with different auth context
        self.base_url = "https://api.groq.com/openai/v1"

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "logit_bias": False, # Often disabled in playground or limited
            "system": True,
            "temperature": True,
        }

    def get_api_base(self) -> str:
        return self.base_url

async def send_request(
    self,
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    stream: bool = True,
) -> Any:
    request_body = body
    token = session_store.get_token("groq")
    if not token:
        # Fallback to .env (supports API key as "session" for testing)
        token = os.environ.get("GROQ_SESSION_TOKEN") or os.environ.get("GROQ_API_KEY")
        
    if not token:
        raise ValueError("No Groq session found. Please sync via extension or set GROQ_API_KEY.")

    # If the token is a JWT (supabase), we use it as Bearer
    # If it's a cookie, we might need Cookie header.
    # Assuming Bearer for now based on common playground implementations.
    
    impersonate_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Referer": "https://groq.com/",
        "Origin": "https://groq.com",
    }

    async with AsyncSession(impersonate="chrome110", headers=impersonate_headers) as session:
        resp = await session.post(
            f"{self.base_url}/chat/completions",
            json=request_body,
            stream=stream
        )

        if resp.status_code != 200:
             raise Exception(f"Groq Web API Error: {resp.text}")

        if stream:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield json.loads(line[6:])
        else:
            return resp.json()

    def transform_request(
        self, 
        body: Dict[str, Any], 
        headers: Dict[str, str], 
        strategy: Any
    ) -> Any:
        from unfetter_proxy.providers.base import TransformResult
        
        modified = body.copy()
        applied = []
        
        # 1. Stealth Mode
        if strategy.stealth_mode:
            messages = modified.get("messages", [])
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    original_content = msg["content"]
                    msg["content"] = StealthWrapper.wrap(original_content)
                    applied.append("stealth_mode")
                    break
            modified["messages"] = messages
            
        # 2. System prompt + Persona + God Mode
        if strategy.inject_system or strategy.persona or strategy.god_mode_template:
            messages = modified.get("messages", [])
            injections = []
            
            if strategy.persona:
                persona_text = get_persona_prompt(strategy.persona)
                if persona_text:
                    injections.append(persona_text)
                    applied.append(f"persona({strategy.persona})")
 
            if strategy.inject_system:
                suffix = strategy.custom_system_suffix or get_system_suffix(strategy.strength)
                injections.append(suffix)
                applied.append("system_suffix")
 
            if strategy.god_mode_template:
                injections.append(strategy.god_mode_template)
                applied.append("god_mode")
 
            full_injection = "\n\n".join(injections)
 
            system_idx = None
            for i, msg in enumerate(messages):
                if msg.get("role") == "system":
                    system_idx = i
                    break
 
            if system_idx is not None:
                messages[system_idx]["content"] += "\n\n" + full_injection
            else:
                messages.insert(0, {"role": "system", "content": full_injection})
 
            modified["messages"] = messages
 
        # 3. Parameter tweaks
        if strategy.tweak_params:
            if "temperature" not in modified:
                modified["temperature"] = min(1.2, 0.7 + 0.5 * strategy.strength)
                applied.append("tweak_params")
        
        return TransformResult(body=modified, applied=applied)

    def detect_refusal(self, response: Any) -> bool:
        try:
            content = response["choices"][0]["message"]["content"]
            return "I cannot" in content
        except:
            return False

    def get_upstream_url(self, path: str) -> str:
        # Handle custom /groq routing
        if path.startswith("/groq"):
            path = path.replace("/groq", "", 1)
        
        # Avoid double /v1 if base_url has it
        if self.base_url.endswith("/v1") and path.startswith("/v1"):
             return f"{self.base_url}{path[3:]}"
             
        return f"{self.base_url}{path}"

    def get_upstream_headers(self, original_headers: Dict[str, str]) -> Dict[str, str]:
        headers = dict(original_headers)
        
        token = session_store.get_token("groq")
        if not token:
             token = os.environ.get("GROQ_SESSION_TOKEN") or os.environ.get("GROQ_API_KEY")
             
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            # Let it fail downstream or raise. 
            pass  

        # Add impersonation headers
        headers["Referer"] = "https://groq.com/"
        headers["Origin"] = "https://groq.com"
        
        return headers
