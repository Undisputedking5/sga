import firebase_admin
from firebase_admin import credentials
import os
from dotenv import load_dotenv

load_dotenv()

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        "databaseURL": os.getenv("FIREBASE_DATABASE_URL")
    })

from firebase_admin import db