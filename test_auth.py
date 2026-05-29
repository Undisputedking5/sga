import firebase_admin
from firebase_admin import credentials, auth

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

try:
    user = auth.get_user_by_email("admin@sgasecurity.com")
    print(f"✅ FOUND IN FIREBASE AUTH!")
    print(f"   UID: {user.uid}")
    print(f"   Custom Claims: {user.custom_claims}")
except Exception as e:
    print(f"❌ NOT FOUND or ERROR: {e}")