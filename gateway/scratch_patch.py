import sys, urllib.request, json
import urllib.error

url = "http://127.0.0.1:8000/gateway/api/sandbox/sandbox-default-c07290e6"
data = json.dumps({"name": "Codex Env", "description": "Running codex testing here"}).encode()
req = urllib.request.Request(url, data=data, method="PATCH")
req.add_header("Content-Type", "application/json")
# Assuming api key doesn't matter for the patch endpoint unless verify_api_key enforces it, wait, it does!
req.add_header("Authorization", "Bearer api-key:4")

try:
    with urllib.request.urlopen(req) as resp:
        print("Success:", resp.read().decode())
except urllib.error.HTTPError as e:
    print("Error:", e.code, e.read().decode())
