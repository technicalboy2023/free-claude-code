import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY")

if not NVIDIA_NIM_API_KEY:
    print("No NVIDIA_NIM_API_KEY found")
    exit(1)

client = httpx.Client(
    base_url="https://integrate.api.nvidia.com/v1",
    headers={"Authorization": f"Bearer {NVIDIA_NIM_API_KEY}"},
    timeout=30.0,
)


def test_kimi():
    print("Testing basic chat completion...")
    payload = {
        "model": "moonshotai/kimi-k2.6",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 1024,
        "temperature": 0.0,
    }

    resp = client.post("/chat/completions", json=payload)
    print(f"Status: {resp.status_code}")
    print(resp.text)

    print("\nTesting tools...")
    payload["tools"] = [
        {
            "type": "function",
            "function": {
                "name": "Bash",
                "description": "Run bash",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string", "default": ""}},
                    "required": ["command"],
                },
            },
        }
    ]
    resp = client.post("/chat/completions", json=payload)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text)
    else:
        print("Tools test succeeded")

    print("\nTesting max_tokens = 8192...")
    payload["max_tokens"] = 8192
    resp = client.post("/chat/completions", json=payload)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text)
    else:
        print("max_tokens test succeeded")

    print("\nTesting tools with additionalProperties: False...")
    payload["tools"][0]["function"]["parameters"]["additionalProperties"] = False
    resp = client.post("/chat/completions", json=payload)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text)
    else:
        print("additionalProperties test succeeded")


test_kimi()
