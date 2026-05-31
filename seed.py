"""
SGA Guard — Firebase Seed Script
Run from your project root: python seed.py

PURPOSE: Development data only. Wipe and replace with real data once the
Android app is live and guards are actively using the system.

This file is also your SCHEMA CONTRACT — the Android app must write to
Firebase using the exact same paths and field names defined here.

Requires: serviceAccountKey.json in the same directory
"""

import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta, date
import random

# ── Init ──────────────────────────────────────────────────────────────────────
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://sga-guard-default-rtdb.firebaseio.com"
    })

root = db.reference("/")

def iso(dt):
    return dt.isoformat() + "Z"

today = date.today()

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTANT: Replace "YOUR_FIREBASE_AUTH_UID" below with the actual UID from
# your Firebase Authentication console (the one you use to log into the dashboard).
# Find it at: Firebase Console → Authentication → Users → copy the User UID
# ─────────────────────────────────────────────────────────────────────────────
MY_ADMIN_UID = "PBQZ2JzfLubaRfwYf9JPhUVFAa42"

# ── Reference data ────────────────────────────────────────────────────────────
REGIONS = ["nairobi_cbd", "westlands", "karen", "industrial_area", "langata"]

REGION_META = {
    "nairobi_cbd": {
        "name": "Nairobi CBD",
        "region_code": "NBI-CBD",
        "map_code": "cbd",
        "status": "stable",
        "lat": -1.2864,
        "lng": 36.8172,
        "sites": 12,
        "incidents": "low",
        "manager_uid": MY_ADMIN_UID,
        "manager_name": "Head Office",
        "image_url": "",
    },
    "westlands": {
        "name": "Westlands",
        "region_code": "NBI-WL",
        "map_code": "wl",
        "status": "monitoring",
        "lat": -1.2676,
        "lng": 36.8117,
        "sites": 9,
        "incidents": "med",
        "manager_uid": MY_ADMIN_UID,
        "manager_name": "Head Office",
        "image_url": "",
    },
    "karen": {
        "name": "Karen",
        "region_code": "NBI-KRN",
        "map_code": "krn",
        "status": "stable",
        "lat": -1.3190,
        "lng": 36.7128,
        "sites": 7,
        "incidents": "low",
        "manager_uid": MY_ADMIN_UID,
        "manager_name": "Head Office",
        "image_url": "",
    },
    "industrial_area": {
        "name": "Industrial Area",
        "region_code": "NBI-IND",
        "map_code": "ind",
        "status": "critical",
        "lat": -1.3031,
        "lng": 36.8488,
        "sites": 15,
        "incidents": "high",
        "manager_uid": MY_ADMIN_UID,
        "manager_name": "Head Office",
        "image_url": "",
    },
    "langata": {
        "name": "Lang'ata",
        "region_code": "NBI-LNG",
        "map_code": "lng",
        "status": "stable",
        "lat": -1.3667,
        "lng": 36.7500,
        "sites": 6,
        "incidents": "low",
        "manager_uid": MY_ADMIN_UID,
        "manager_name": "Head Office",
        "image_url": "",
    },
}

GUARD_NAMES = [
    ("James",  "Odhiambo"),
    ("Faith",  "Wanjiku"),
    ("Brian",  "Mutua"),
    ("Grace",  "Achieng"),
    ("Kevin",  "Njoroge"),
    ("Mercy",  "Atieno"),
    ("Samuel", "Kipchoge"),
    ("Diana",  "Mwangi"),
    ("Peter",  "Kamau"),
    ("Linda",  "Chebet"),
]

RANKS    = ["guard", "senior_guard", "supervisor", "team_lead"]
STATUSES = ["active", "active", "active", "active", "on_leave", "urgent", "inactive"]
COLORS   = [
    "#E53935", "#1E88E5", "#43A047", "#FB8C00",
    "#8E24AA", "#00ACC1", "#F4511E", "#6D4C41",
    "#3949AB", "#039BE5",
]

SITES = {
    "nairobi_cbd":     [("ICEA Building", "Upper Hill"),          ("Afya Centre", "Tom Mboya St"),       ("Times Tower", "Haile Selassie Ave")],
    "westlands":       [("Sarit Centre", "Westlands Rd"),         ("ABC Place", "Waiyaki Way"),           ("Delta Corner", "Chiromo Rd")],
    "karen":           [("Karen Blixen Centre", "Karen Rd"),      ("Waterfront Mall", "Karen Hardy"),     ("Hub Karen", "Ngong Rd")],
    "industrial_area": [("EPZ Gate A", "Nbi Industrial"),         ("Export Processing", "Enterprise Rd"), ("Bamburi Plant", "Mombasa Rd")],
    "langata":         [("Carnivore Grounds", "Langata Rd"),      ("Wilson Airport", "Langata South"),    ("Uhuru Gardens", "Langata Rd")],
}

# ── 1. Guards ─────────────────────────────────────────────────────────────────
print("Seeding guards...")
guard_uids = []

for i, (first, last) in enumerate(GUARD_NAMES):
    uid = f"guard_{str(i+1).zfill(3)}"
    guard_uids.append(uid)
    region = REGIONS[i % len(REGIONS)]
    site_name, site_sub = SITES[region][i % len(SITES[region])]

    root.child(f"guards/{uid}").set({
        "name":         f"{first} {last}",
        "guard_id":     f"SGA-{2024 + (i % 2)}-{str(100 + i).zfill(4)}",
        "initials":     f"{first[0]}{last[0]}",
        "avatar_url":   "",
        "avatar_color": COLORS[i % len(COLORS)],
        "status":       STATUSES[i % len(STATUSES)],
        "region":       region,
        "site_name":    site_name,
        "site_sub":     site_sub,
        "phone":        f"+2547{random.randint(10000000, 99999999)}",
        "rank":         RANKS[i % len(RANKS)],
        "certified":    i % 3 != 0,
        "last_active":  iso(datetime.now() - timedelta(hours=random.randint(0, 48))),
    })

print(f"  ✓ {len(guard_uids)} guards seeded")

# ── 2. Attendance (14 days per guard) ─────────────────────────────────────────
print("Seeding attendance...")
att_count = 0
SHIFT_START = "07:00"
SHIFT_END   = "19:00"

for uid in guard_uids:
    guard_data = root.child(f"guards/{uid}").get()
    region    = guard_data["region"]
    site_name = guard_data["site_name"]

    for day_offset in range(14):
        record_date = today - timedelta(days=day_offset)
        date_str    = record_date.isoformat()

        roll = random.random()
        if record_date.weekday() >= 5:  # weekends more likely absent
            roll *= 0.6

        if roll < 0.10:
            status    = "absent"
            clock_in  = ""
            clock_out = ""
        elif roll < 0.25:
            status    = "late"
            late_mins = random.randint(15, 90)
            ci = datetime.combine(record_date, datetime.strptime(SHIFT_START, "%H:%M").time()) + timedelta(minutes=late_mins)
            co = datetime.combine(record_date, datetime.strptime(SHIFT_END,   "%H:%M").time()) + timedelta(minutes=random.randint(-10, 20))
            clock_in  = ci.strftime("%H:%M")
            clock_out = co.strftime("%H:%M")
        else:
            status     = "on_time"
            early_mins = random.randint(-15, 5)
            ci = datetime.combine(record_date, datetime.strptime(SHIFT_START, "%H:%M").time()) + timedelta(minutes=early_mins)
            co = datetime.combine(record_date, datetime.strptime(SHIFT_END,   "%H:%M").time()) + timedelta(minutes=random.randint(-5, 15))
            clock_in  = ci.strftime("%H:%M")
            clock_out = co.strftime("%H:%M")

        root.child(f"attendance/{uid}/{date_str}").set({
            "clock_in":    clock_in,
            "clock_out":   clock_out,
            "status":      status,
            "site":        site_name,
            "region":      region,
            "shift_start": SHIFT_START,
            "shift_end":   SHIFT_END,
        })
        att_count += 1

print(f"  ✓ {att_count} attendance records seeded")

# ── 3. Regions ────────────────────────────────────────────────────────────────
print("Seeding regions...")
for region_id, data in REGION_META.items():
    root.child(f"regions/{region_id}").set(data)
print(f"  ✓ {len(REGION_META)} regions seeded")

# ── 4. Reports ────────────────────────────────────────────────────────────────
print("Seeding reports...")

REPORTS = [
    ("Daily Patrol Summary — CBD",        "daily",    "pending",        "nairobi_cbd",     "James Odhiambo",  "guard_001", "JO", "#E53935", "All patrol checkpoints completed. No incidents to report during the shift."),
    ("Incident: Unauthorized Entry",       "incident", "critical",       "industrial_area", "Brian Mutua",     "guard_003", "BM", "#43A047", "Suspect apprehended at Gate 3. Police notified. CCTV footage preserved."),
    ("Monthly Operations Report — Karen",  "monthly",  "approved",       "karen",           "Kevin Njoroge",   "guard_005", "KN", "#8E24AA", "Monthly operations ran smoothly. Staff attendance at 94%. Minor equipment issues noted."),
    ("Security Audit Q2 2025",             "audit",    "approved",       "westlands",       "Faith Wanjiku",   "guard_002", "FW", "#1E88E5", "Full audit completed. 3 minor compliance gaps identified — corrective actions recommended."),
    ("Daily Patrol Summary — Westlands",   "daily",    "pending",        "westlands",       "Grace Achieng",   "guard_004", "GA", "#FB8C00", "Evening patrol logged. One suspicious vehicle noted near Zone B, no action required."),
    ("Incident: Equipment Theft",          "incident", "needs_revision", "industrial_area", "Samuel Kipchoge", "guard_007", "SK", "#00ACC1", "Two laptops and a radio missing from the equipment store. Investigation ongoing."),
    ("Daily Patrol Summary — Langata",     "daily",    "pending",        "langata",         "Mercy Atieno",    "guard_006", "MA", "#F4511E", "Quiet shift. Roads clear. All guard posts staffed throughout the night."),
    ("Monthly Report — Industrial Area",   "monthly",  "approved",       "industrial_area", "Diana Mwangi",    "guard_008", "DM", "#6D4C41", "High-traffic month due to port activity. Overtime logged for 6 guards."),
    ("Incident: Suspicious Vehicle",       "incident", "pending",        "nairobi_cbd",     "Peter Kamau",     "guard_009", "PK", "#3949AB", "Black sedan circled the compound 3 times. Reported to supervisor."),
    ("Security Audit Q1 2025",             "audit",    "approved",       "karen",           "Linda Chebet",    "guard_010", "LC", "#039BE5", "All security protocols in compliance. Recommended CCTV upgrade in Zone 4."),
]

for idx, (title, rtype, rstatus, region, submitted_by, sub_uid, initials, color, notes) in enumerate(REPORTS):
    report_id = f"RPT-{2025000 + idx + 1}"
    root.child(f"reports/{report_id}").set({
        "title":              title,
        "report_code":        report_id,
        "type":               rtype,
        "status":             rstatus,
        "submitted_by":       submitted_by,
        "submitter_uid":      sub_uid,
        "submitter_initials": initials,
        "submitter_color":    color,
        "region":             region,
        "site":               SITES[region][0][0],
        "date_submitted":     iso(datetime.now() - timedelta(days=random.randint(0, 20))),
        "notes":              notes,
    })

print(f"  ✓ {len(REPORTS)} reports seeded")

# ── 5. Admin profile (uses YOUR real UID, not a placeholder guard UID) ────────
# Only sets display_name and avatar_url — does NOT touch your auth credentials.
print("Seeding admin profile...")
if MY_ADMIN_UID == "YOUR_FIREBASE_AUTH_UID":
    print("  ⚠️  Skipped — replace MY_ADMIN_UID at the top of this file with your real UID first.")
else:
    root.child(f"admins/{MY_ADMIN_UID}").update({
        "avatar_url": "",
        # display_name and email are already set from your Auth account;
        # only add them here if your settings page reads from /admins/ instead of Auth directly.
    })
    print(f"  ✓ admin profile confirmed at /admins/{MY_ADMIN_UID}")

# ── 6. System settings ────────────────────────────────────────────────────────
print("Seeding system_settings...")
root.child("system_settings").set({
    "org_name":               "SGA Security Group",
    "timezone":               "Africa/Nairobi",
    "date_format":            "DD/MM/YYYY",
    "shift_start":            "07:00",
    "shift_end":              "19:00",
    "late_threshold_minutes": 15,
})
print("  ✓ system_settings seeded")

# ── 7. Security settings ──────────────────────────────────────────────────────
print("Seeding security_settings...")
root.child("security_settings").set({
    "session_timeout_hours": 24,
    "require_2fa":           False,
    "login_attempts_limit":  5,
    "ip_whitelist_enabled":  False,
    "ip_whitelist":          [],
})
print("  ✓ security_settings seeded")

# ── 8. Notification settings ──────────────────────────────────────────────────
print("Seeding notification_settings...")
if MY_ADMIN_UID != "YOUR_FIREBASE_AUTH_UID":
    root.child(f"notification_settings/{MY_ADMIN_UID}").set({
        "email_attendance_alerts": True,
        "email_incident_reports":  True,
        "email_daily_summary":     False,
        "push_urgent_alerts":      True,
        "push_region_updates":     True,
        "push_report_approvals":   False,
    })
    print(f"  ✓ notification_settings seeded for {MY_ADMIN_UID}")
else:
    print("  ⚠️  Skipped — set MY_ADMIN_UID first.")

# ── Done ──────────────────────────────────────────────────────────────────────
print("\n✅ Seed complete.")
print(f"   Guards:      {len(guard_uids)}")
print(f"   Attendance:  {att_count} records (14 days × {len(guard_uids)} guards)")
print(f"   Regions:     {len(REGION_META)}")
print(f"   Reports:     {len(REPORTS)}")
print( "   Settings:    system, security, notifications")
print()
print("NOTE: This is development data. Wipe /guards/, /attendance/, /reports/")
print("      from the Firebase console once the Android app goes live.")