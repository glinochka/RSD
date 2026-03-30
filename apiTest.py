import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse


# Test key provided by the user.
API_KEY = "agnt_baYOViUeuDtTsoBJVzjgjCcpz2z9gBF7eJM-a2jxvZs"

# You can override in env:
#   set API_BASE_URL=http://localhost:8000
API_BASE_URL = "https://rsd-ai.ru"
URL = f"{API_BASE_URL}/api/agents/external/chat"


def main() -> int:
    message = sys.argv[1] if len(sys.argv) > 1 else "Привет! Подскажи, что ты умеешь."

    payload = {"message": message}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Agent-API-Key": API_KEY,
    }

    req = urllib.request.Request(URL, data=data, headers=headers, method="POST")

    try:
        print(f"POST {URL}")
        parsed = urlparse(API_BASE_URL)
        if parsed.scheme.lower() == "https":
            ctx = ssl.create_default_context()
            opener_args = {"context": ctx}
        else:
            opener_args = {}

        with urllib.request.urlopen(req, timeout=60, **opener_args) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            body = json.loads(raw) if raw else {}

            # Print only what's useful in terminal.
            if isinstance(body, dict) and "answer" in body:
                print("Ответ агента:")
                print(body.get("answer"))
                if body.get("sources"):
                    print("\nИсточники:")
                    for s in body.get("sources", []):
                        print("-", s)
            else:
                print("Ответ сервера (raw):")
                print(json.dumps(body, ensure_ascii=False, indent=2))

            return 0
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        print(f"HTTP Error: {e.code}")
        if raw:
            try:
                print("Body:")
                print(json.dumps(json.loads(raw), ensure_ascii=False, indent=2))
            except Exception:
                print(raw)
        return 1
    except Exception as e:
        print(f"Request failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

