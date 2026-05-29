from django.shortcuts import render
from core.decorators import login_required, superadmin_required
from datetime import datetime
from firebase_admin import db


def get_overview_stats():
    """
    Fetch overview stats from Firebase Realtime Database.
    Returns a dict with totals, live check-ins, region breakdown, and alerts.
    Falls back to empty/zero values if Firebase is unavailable.
    """
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')

        # --- Total guards ---
        guards_ref = db.reference('guards')
        guards_snap = guards_ref.get() or {}
        total_guards = len(guards_snap)

        # --- Attendance for today ---
        attendance_ref = db.reference(f'attendance/{today_str}')
        attendance_snap = attendance_ref.get() or {}

        checked_in = 0
        late_arrivals = 0
        absent = 0
        live_checkins = []

        for guard_id, record in attendance_snap.items():
            status = record.get('status', '')
            if status == 'present':
                checked_in += 1
            elif status == 'late':
                checked_in += 1  # late guards are still checked in
                late_arrivals += 1
            elif status == 'absent':
                absent += 1

            # Build live check-in rows (most recent first, cap at 10)
            if status in ('present', 'late'):
                guard_data = guards_snap.get(guard_id, {})
                live_checkins.append({
                    'name': guard_data.get('name', 'Unknown'),
                    'site': record.get('site', '—'),
                    'region': record.get('region', '—'),
                    'time': record.get('check_in_time', '—'),
                    'status': status,
                })

        # Sort by time descending, keep latest 10
        live_checkins = sorted(
            live_checkins,
            key=lambda x: x['time'],
            reverse=True
        )[:10]

        # --- Region breakdown ---
        regions_ref = db.reference('regions')
        regions_snap = regions_ref.get() or {}

        region_stats = []
        for region_id, region_data in regions_snap.items():
            name = region_data.get('name', region_id)
            total = region_data.get('total_guards', 0)
            present = sum(
                1 for r in attendance_snap.values()
                if r.get('region') == name and r.get('status') in ('present', 'late')
            )
            pct = round((present / total) * 100) if total > 0 else 0
            region_stats.append({'name': name, 'pct': pct})

        region_stats = sorted(region_stats, key=lambda x: x['name'])

        # --- Critical alerts ---
        alerts_ref = db.reference('alerts')
        alerts_snap = alerts_ref.get() or {}
        alerts = []
        for alert_id, alert_data in alerts_snap.items():
            if alert_data.get('resolved', False):
                continue
            alerts.append({
                'type': alert_data.get('type', 'warning'),   # 'critical' | 'warning'
                'title': alert_data.get('title', ''),
                'subtitle': alert_data.get('subtitle', ''),
            })

        return {
            'total_guards': total_guards,
            'checked_in': checked_in,
            'late_arrivals': late_arrivals,
            'absent': absent,
            'live_checkins': live_checkins,
            'region_stats': region_stats,
            'alerts': alerts,
            'active_alerts_count': len(alerts),
            'error': None,
        }

    except Exception as e:
        return {
            'total_guards': 0,
            'checked_in': 0,
            'late_arrivals': 0,
            'absent': 0,
            'live_checkins': [],
            'region_stats': [],
            'alerts': [],
            'active_alerts_count': 0,
            'error': str(e),
        }


@login_required
# @superadmin_required
def overview(request):
    stats = get_overview_stats()
    today_display = datetime.now().strftime('%A, %b %d, %Y')

    context = {
        'active_nav': 'overview',
        'page_title': 'Overview',
        'today_display': today_display,
        **stats,
    }
    return render(request, 'overview/overview.html', context)