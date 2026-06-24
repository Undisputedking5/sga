"""
SGA Guard — Firebase Seed Data Wipe Script
Run from your project root: python wipe_seed_data.py

PURPOSE: Clears all dummy/seed data from Firebase before going live.
         Run this once the Android app is deployed and real guards are
         actively using the system.

WHAT GETS WIPED:
  ✗ /guards/         — all 10 seed guards (guard_001 … guard_010)
  ✗ /attendance/     — all 140 seed attendance records
  ✗ /reports/        — all 10 seed reports (RPT-2025001 … RPT-2025010)
  ✗ /regions/        — seed region metadata (you'll re-add real ones via the web dashboard)

WHAT IS PRESERVED:
  ✓ /admins/                          — your admin profile
  ✓ /system_settings/                 — org name, timezone, shift times etc.
  ✓ /security_settings/               — session timeout, login limits etc.
  ✓ /notification_settings/           — your notification preferences
  ✓ Firebase Authentication users     — untouched (this script only touches the DB)

Requires: serviceAccountKey.json in the same directory
"""

import firebase_admin
from firebase_admin import credentials, db

# ── Init ──────────────────────────────────────────────────────────────────────
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://sga-guard-default-rtdb.firebaseio.com"
    })

root = db.reference("/")

# ── Safety confirmation ───────────────────────────────────────────────────────
print("=" * 60)
print("  SGA Guard — Seed Data Wipe")
print("=" * 60)
print()
print("This will permanently delete:")
print("  • /guards/      (all seed guards)")
print("  • /attendance/  (all seed attendance records)")
print("  • /reports/     (all seed reports)")
print("  • /regions/     (all seed region metadata)")
print()
print("Your admin profile, system settings, security settings,")
print("and notification settings will NOT be touched.")
print()

confirm = input("Type  YES  to proceed: ").strip()
if confirm != "YES":
    print("\nAborted. Nothing was deleted.")
    exit(0)

print()

# ── Wipe ─────────────────────────────────────────────────────────────────────

# 1. Guards
print("Wiping /guards/ ...")
guards_ref = root.child("guards")
guards_snapshot = guards_ref.get()
if guards_snapshot:
    seed_guards = [uid for uid in guards_snapshot.keys() if uid.startswith("guard_")]
    for uid in seed_guards:
        guards_ref.child(uid).delete()
    print(f"  ✓ Deleted {len(seed_guards)} seed guard(s)")
else:
    print("  — /guards/ was already empty")

# 2. Attendance
print("Wiping /attendance/ ...")
att_ref = root.child("attendance")
att_snapshot = att_ref.get()
if att_snapshot:
    seed_att = [uid for uid in att_snapshot.keys() if uid.startswith("guard_")]
    for uid in seed_att:
        att_ref.child(uid).delete()
    print(f"  ✓ Deleted attendance records for {len(seed_att)} seed guard(s)")
else:
    print("  — /attendance/ was already empty")

# 3. Reports
print("Wiping /reports/ ...")
reports_ref = root.child("reports")
reports_snapshot = reports_ref.get()
if reports_snapshot:
    seed_reports = [rid for rid in reports_snapshot.keys() if rid.startswith("RPT-2025")]
    for rid in seed_reports:
        reports_ref.child(rid).delete()
    print(f"  ✓ Deleted {len(seed_reports)} seed report(s)")
else:
    print("  — /reports/ was already empty")

# 4. Regions
print("Wiping /regions/ ...")
regions_ref = root.child("regions")
seed_region_ids = [
    "nairobi_cbd", "westlands", "karen", "industrial_area", "langata"
]
deleted_regions = 0
for region_id in seed_region_ids:
    ref = regions_ref.child(region_id)
    if ref.get() is not None:
        ref.delete()
        deleted_regions += 1
if deleted_regions:
    print(f"  ✓ Deleted {deleted_regions} seed region(s)")
else:
    print("  — seed regions were already gone")

# ── Done ─────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("  ✅ Wipe complete. Firebase is clean and ready for real data.")
print("=" * 60)
print()
print("Next steps:")
print("  1. Add your real regions via the web dashboard (Regions → Add Region)")
print("  2. Add your real guard accounts via the web dashboard (Guards → Add Guard)")
print("  3. Guards log in on the Android app and attendance starts flowing in")
print("  4. Reports submitted via the app will appear in the web dashboard")
print()
print("NOTE: If you have any real guards or regions already in Firebase")
print("      that share IDs with the seed data, they were also deleted.")
print("      Check Firebase console to confirm everything looks correct.")