import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("FIREBASE_API_KEY")
url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"

payload = {
    "email": "admin@sgasecurity.com",
    "password": "patrick1979",
    "returnSecureToken": True
}

res = requests.post(url, json=payload)
print("👉 STATUS CODE:", res.status_code)
print("👉 RESPONSE RAW:", res.json())