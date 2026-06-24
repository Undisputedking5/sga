import requests
import os
from django.shortcuts import render, redirect
from django.contrib import messages
from core.decorators import login_required
from core.firebase import db

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from firebase_admin import storage, db as rtdb



@login_required
def settings_view(request):
    uid = request.session.get('uid')
    email = request.session.get('email')
    display_name = request.session.get('display_name', '')
    tab = request.GET.get('tab', 'profile')

    # Fetch admin profile from Firebase (if stored)
    admin_data = {}
    try:
        admin_data = db.reference(f'/admins/{uid}').get() or {}
    except Exception:
        pass

    # Fetch system settings
    system_data = {}
    try:
        system_data = db.reference('/system_settings').get() or {}
    except Exception:
        pass

    # Fetch security settings
    security_data = {}
    try:
        security_data = db.reference('/security_settings').get() or {}
    except Exception:
        pass

    # Fetch notification settings
    notif_data = {}
    try:
        notif_data = db.reference(f'/notification_settings/{uid}').get() or {}
    except Exception:
        pass

    tabs = [
        ('profile', 'Profile'),
        ('system', 'System'),
        ('security', 'Security'),
        ('notifications', 'Notifications'),
    ]

    timezones = [
        'Africa/Nairobi', 'Africa/Lagos', 'Africa/Johannesburg', 'Africa/Cairo',
        'Africa/Casablanca', 'UTC', 'Europe/London', 'Europe/Paris',
        'America/New_York', 'America/Los_Angeles', 'Asia/Dubai',
    ]

    email_toggles = [
        ('email_attendance', 'Attendance Alerts', 'Email when guards clock in late or are absent'),
        ('email_incidents', 'Incident Reports', 'Email when a new incident report is submitted'),
        ('email_summary', 'Daily Summary', 'Receive a daily attendance and activity digest'),
    ]

    push_toggles = [
        ('push_urgent', 'Urgent Alerts', 'Instant alerts for urgent guard or region status'),
        ('push_regions', 'Region Updates', 'Notifications when a region status changes'),
        ('push_approvals', 'Report Approvals', 'Alerts when reports are pending your approval'),
    ]

    context = {
        'tab': tab,
        'tabs': tabs,
        'uid': uid,
        'email': email,
        'display_name': display_name,
        'admin_data': admin_data,
        'system_data': system_data,
        'security_data': security_data,
        'notif_data': notif_data,
        'timezones': timezones,
        'email_toggles': email_toggles,
        'push_toggles': push_toggles,
        'active_nav': 'settings',
    }
    return render(request, 'settings/settings.html', context)


@login_required
def update_profile(request):
    if request.method != 'POST':
        return redirect('settings:index')

    uid = request.session.get('uid')
    name = request.POST.get('admin_name', '').strip()
    email = request.POST.get('email', '').strip()

    try:
        db.reference(f'/admins/{uid}').update({
            'display_name': name,
            'email': email,
        })
        request.session['display_name'] = name
        request.session['email'] = email
        messages.success(request, 'Profile updated successfully.')
    except Exception as e:
        messages.error(request, f'Failed to update profile: {e}')

    return redirect('settings:index')


@login_required
def reset_password(request):
    if request.method != 'POST':
        return redirect('settings:index')

    email = request.session.get('email')
    api_key = os.environ.get('FIREBASE_API_KEY')

    try:
        response = requests.post(
            f'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}',
            json={'requestType': 'PASSWORD_RESET', 'email': email}
        )
        response.raise_for_status()
        messages.success(request, f'Password reset email sent to {email}.')
    except Exception as e:
        messages.error(request, 'Failed to send password reset email.')

    return redirect('settings:index')


@login_required
def update_system(request):
    if request.method != 'POST':
        return redirect('/settings/?tab=system')

    try:
        data = {
            'org_name': request.POST.get('org_name', '').strip(),
            'timezone': request.POST.get('timezone', '').strip(),
            'date_format': request.POST.get('date_format', '').strip(),
            'shift_start': request.POST.get('shift_start', '').strip(),
            'shift_end': request.POST.get('shift_end', '').strip(),
            'late_threshold_minutes': int(request.POST.get('late_threshold', 15)),
        }
        db.reference('/system_settings').update(data)
        messages.success(request, 'System settings saved.')
    except Exception as e:
        messages.error(request, f'Failed to save system settings: {e}')

    return redirect('/settings/?tab=system')


@login_required
def update_security(request):
    if request.method != 'POST':
        return redirect('/settings/?tab=security')

    try:
        data = {
            'session_timeout_hours': int(request.POST.get('session_timeout', 24)),
            'require_2fa': request.POST.get('require_2fa') == 'on',
            'login_attempts_limit': int(request.POST.get('login_attempts', 5)),
            'ip_whitelist_enabled': request.POST.get('ip_whitelist') == 'on',
            'ip_whitelist': request.POST.get('ip_whitelist_ips', '').strip(),
        }
        db.reference('/security_settings').update(data)
        messages.success(request, 'Security settings saved.')
    except Exception as e:
        messages.error(request, f'Failed to save security settings: {e}')

    return redirect('/settings/?tab=security')


@login_required
def update_notifications(request):
    if request.method != 'POST':
        return redirect('/settings/?tab=notifications')

    uid = request.session.get('uid')
    try:
        data = {
            'email_attendance_alerts': request.POST.get('email_attendance') == 'on',
            'email_incident_reports': request.POST.get('email_incidents') == 'on',
            'email_daily_summary': request.POST.get('email_summary') == 'on',
            'push_urgent_alerts': request.POST.get('push_urgent') == 'on',
            'push_region_updates': request.POST.get('push_regions') == 'on',
            'push_report_approvals': request.POST.get('push_approvals') == 'on',
        }
        db.reference(f'/notification_settings/{uid}').update(data)
        messages.success(request, 'Notification preferences saved.')
    except Exception as e:
        messages.error(request, f'Failed to save notifications: {e}')

    return redirect('/settings/?tab=notifications')


from django.shortcuts import render

# Create your views here.
# settings/views.py  — add this view alongside your existing update_profile / reset_password views


@login_required
@require_POST
def upload_avatar(request):
    """
    POST with file field 'avatar'  → upload to Firebase Storage, save URL to /admins/{uid}/avatar_url
    POST with body param 'remove=1' → delete from Storage and clear URL in DB
    Returns JSON {"avatar_url": "..."} or {"ok": true} or {"error": "..."}
    """
    uid = request.user.uid  # adjust if you store UID differently on your user model

    # ── Remove ────────────────────────────────────────────────────────────────
    if request.POST.get("remove"):
        try:
            bucket = storage.bucket()
            for ext in ("jpg", "jpeg", "png", "webp"):
                blob = bucket.blob(f"avatars/{uid}.{ext}")
                if blob.exists():
                    blob.delete()
            rtdb.reference(f"admins/{uid}").update({"avatar_url": ""})
            return JsonResponse({"ok": True})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # ── Upload ────────────────────────────────────────────────────────────────
    avatar_file = request.FILES.get("avatar")
    if not avatar_file:
        return JsonResponse({"error": "No file provided."}, status=400)

    # Validate content type
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if avatar_file.content_type not in allowed:
        return JsonResponse({"error": "Only JPEG, PNG, or WebP images are allowed."}, status=400)

    # Validate size (max 5 MB)
    if avatar_file.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "Image must be under 5 MB."}, status=400)

    ext = avatar_file.content_type.split("/")[-1]   # jpeg / png / webp
    blob_path = f"avatars/{uid}.{ext}"

    try:
        bucket = storage.bucket()
        blob = bucket.blob(blob_path)
        blob.upload_from_file(avatar_file, content_type=avatar_file.content_type)
        blob.make_public()
        download_url = blob.public_url

        # Persist URL to Realtime DB
        rtdb.reference(f"admins/{uid}").update({"avatar_url": download_url})

        return JsonResponse({"avatar_url": download_url})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)