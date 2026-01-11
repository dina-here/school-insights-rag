#!/usr/bin/env python3
"""
Test OpenAI API access and available models
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("Testing OpenAI API...")
print(f"API Key: {os.getenv('OPENAI_API_KEY')[:20]}...")
print()

# Test different embedding models
models_to_test = [
    "text-embedding-3-small",
    "text-embedding-3-large", 
    "text-embedding-ada-002",
]

test_text = "This is a test"

for model in models_to_test:
    try:
        print(f"Testing {model}...", end=" ")
        response = client.embeddings.create(
            model=model,
            input=test_text
        )
        print(f"✅ SUCCESS (dimension: {len(response.data[0].embedding)})")
    except Exception as e:
        print(f"❌ FAILED: {e}")

print()
print("Listing all available models...")
try:
    models = client.models.list()
    print(f"Total models: {len(models.data)}")
    embedding_models = [m for m in models.data if 'embed' in m.id.lower()]
    if embedding_models:
        print("\nEmbedding models:")
        for m in embedding_models:
            print(f"  - {m.id}")
    else:
        print("\n⚠️ No embedding models found in your account")
except Exception as e:
    print(f"Error listing models: {e}")
