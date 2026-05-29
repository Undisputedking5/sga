import firebase_admin
from firebase_admin import credentials, auth
import os
from dotenv import load_dotenv

load_dotenv()

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

def create_superadmin(email, password, display_name):
    try:
        # Create the user in Firebase Auth
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
            email_verified=True
        )

        # Tag them as superadmin
        auth.set_custom_user_claims(user.uid, {
            "role": "superadmin"
        })

        print(f"✅ Superadmin created successfully")
        print(f"   UID: {user.uid}")
        print(f"   Email: {email}")

    except auth.EmailAlreadyExistsError:
        # User exists — just update their claims
        user = auth.get_user_by_email(email)
        auth.set_custom_user_claims(user.uid, {
            "role": "superadmin"
        })
        print(f"✅ Claims updated for existing user: {email}")


if __name__ == "__main__":
    create_superadmin(
        email="admin@sgasecurity.com",
        password="patrick1979",
        display_name="SGA Admin"
    )