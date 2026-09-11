import os
from dotenv import load_dotenv

load_dotenv()  # Загружает переменные из .env

api_key = os.getenv("BYBIT_API_KEY")
secret_key = os.getenv("BYBIT_SECRET_KEY")

print(f"API Key loaded: {'YES' if api_key else 'NO'}")
print(f"Secret Key loaded: {'YES' if secret_key else 'NO'}")

if api_key:
    print(f"First 5 chars: {api_key[:5]}...")
if secret_key:
    print(f"First 5 chars: {secret_key[:5]}...")
