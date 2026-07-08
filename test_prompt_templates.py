#!/usr/bin/env python3
import requests
import time

base_url = "http://127.0.0.1:8000"

print("Creating API key...")
create_key_response = requests.post(
    f"{base_url}/api-keys",
    json={"name": "test-key-workflows", "description": "Test key for workflows"}
)
print(f"Create key status: {create_key_response.status_code}")
if create_key_response.status_code == 200:
    key_data = create_key_response.json()
    api_key = key_data["api_key"]
    print(f"Got API key: {api_key}")

    headers = {"Authorization": f"Bearer {api_key}"}
    print("\nTesting prompt templates endpoint...")
    templates_response = requests.get(
        f"{base_url}/gateway/api/workflows/prompt-templates",
        headers=headers
    )
    print(f"Prompt templates status: {templates_response.status_code}")
    print(f"Response: {templates_response.text}")
