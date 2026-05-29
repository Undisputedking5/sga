import firebase_admin
from firebase_admin import credentials, auth

# Initialize Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

email = "admin@sgasecurity.com"
target_password = "patrick1979"

try:
    # Fetch the existing user
    user = auth.get_user_by_email(email)

    # Forcefully update their password and confirm claims
    auth.update_user(
        user.uid,
        password=target_password,
        email_verified=True
    )

    auth.set_custom_user_claims(user.uid, {
        "role": "superadmin"
    })

    print(f"🔄 SUCCESS: Password for {email} has been forcefully overwritten to '{target_password}'!")
    print(f"   Custom Claims verified as: {{'role': 'superadmin'}}")

except Exception as e:
    print(f"❌ ERROR updating user: {e}")