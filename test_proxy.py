import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"

# Pehle ek test user banate hain aur API key generate karte hain
print("🔧 Setting up test user...")

# 1. Signup
signup_response = requests.post(f"{BASE_URL}/auth/signup", json={
    "email": "test@example.com",
    "password": "test123",
    "full_name": "Test User"
})

if signup_response.status_code == 200:
    print("✅ User created successfully")
    token = signup_response.json()["access_token"]
else:
    # User already exists, login karein
    login_response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "test@example.com",
        "password": "test123"
    })
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        print("✅ Logged in successfully")
    else:
        print(f"❌ Login Error: {login_response.json()}")
        exit()

# 2. API Key Generate karein
print("\n🔑 Generating API Key...")
key_response = requests.post(
    f"{BASE_URL}/api-keys/generate",
    headers={"Authorization": f"Bearer {token}"},
    json={"key_name": "Test Key"}
)

if key_response.status_code == 200:
    API_KEY = key_response.json()["api_key"]
    print(f"✅ API Key Generated: {API_KEY[:20]}...")
else:
    print(f"❌ Error: {key_response.json()}")
    exit()

# --- AB REAL TESTS ---

print("\n" + "="*60)
print("🚀 TEST 1: Simple Request (Should go to LOCAL)")
print("="*60)

simple_payload = {
    "messages": [
        {"role": "user", "content": "Hi!"}
    ]
}

response1 = requests.post(
    f"{BASE_URL}/v1/chat/completions",
    headers={"X-API-Key": API_KEY},
    json=simple_payload
)

if response1.status_code == 200:
    data = response1.json()
    print(f"✅ Response: {data['choices'][0]['message']['content'][:100]}...")
    print(f"📍 Routed to: {data['routing_info']['decision']}")
    print(f"🎯 Confidence: {data['routing_info']['confidence']}")
    print(f"💡 Reasons: {data['routing_info']['reasons']}")
else:
    print(f"❌ Error: {response1.status_code}")
    print(f"Details: {response1.json()}")

print("\n" + "="*60)
print("🚀 TEST 2: Complex Request (Should go to CLOUD)")
print("="*60)

complex_payload = {
    "messages": [
        {"role": "user", "content": "Explain quantum computing in detail with examples and historical context. Write a Python function to implement a quantum gate."}
    ]
}

response2 = requests.post(
    f"{BASE_URL}/v1/chat/completions",
    headers={"X-API-Key": API_KEY},
    json=complex_payload
)

if response2.status_code == 200:
    data = response2.json()
    print(f"✅ Response: {data['choices'][0]['message']['content'][:100]}...")
    print(f"📍 Routed to: {data['routing_info']['decision']}")
    print(f"🎯 Confidence: {data['routing_info']['confidence']}")
    print(f"💡 Reasons: {data['routing_info']['reasons']}")
    print(f"💰 Tokens Used: {data['usage']['total_tokens']}")
else:
    print(f"❌ Error: {response2.status_code}")
    print(f"Details: {response2.json()}")

print("\n" + "="*60)
print("✅ ALL TESTS COMPLETE!")
print("="*60)