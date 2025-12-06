import httpx
from typing import Dict, Any


class WhiteClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def reset(self) -> None:
        try:
            httpx.post(f"{self.base_url}/reset", timeout=10)
        except Exception:
            pass

    def decide(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        r = httpx.post(f"{self.base_url}/decide", json=observation, timeout=60)
        r.raise_for_status()
        return r.json()
