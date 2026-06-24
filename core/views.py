import requests, os
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from dotenv import load_dotenv
load_dotenv()

FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
FIREBASE_LOGIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.session.get("uid"):
        return redirect("overview:overview")

    error = None

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        if not email or not password:
            error = "Email and password are required."
        else:
            try:
                res = requests.post(FIREBASE_LOGIN_URL, json={
                    "email": email,
                    "password": password,
                    "returnSecureToken": True
                }, timeout=10)

                data = res.json()

                if "idToken" in data:
                    request.session["uid"] = data["localId"]
                    request.session["email"] = data["email"]
                    request.session["id_token"] = data["idToken"]
                    request.session.set_expiry(86400)
                    return redirect("overview:overview")
                else:
                    code = data.get("error", {}).get("message", "")
                    error = _map_error(code)

            except requests.exceptions.Timeout:
                error = "Request timed out. Try again."
            except Exception:
                error = "An unexpected error occurred."

    return render(request, "core/login.html", {"error": error})


def logout_view(request):
    request.session.flush()
    return redirect("core:login")


def _map_error(code):
    return {
        "EMAIL_NOT_FOUND": "No account found with that email.",
        "INVALID_PASSWORD": "Incorrect password.",
        "USER_DISABLED": "This account has been disabled.",
        "INVALID_LOGIN_CREDENTIALS": "Invalid email or password.",
        "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Try later.",
    }.get(code, "Login failed. Check your credentials.")