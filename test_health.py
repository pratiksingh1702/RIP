#!/usr/bin/env python3
import requests
import time

print("Testing health endpoints...")
time.sleep(3)

try:
    r = requests.get("http://localhost:8000/health", timeout=10)
    print(f"RIP Health: {r.status_code} - {r.text}")
except Exception as e:
    print(f"RIP Health error: {e}")

try:
    r = requests.get("http://localhost:8000/gateway/health", timeout=10)
    print(f"Gateway Health: {r.status_code} - {r.text}")
except Exception as e:
    print(f"Gateway Health error: {e}")
