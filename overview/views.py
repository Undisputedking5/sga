from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from core.decorators import login_required
from datetime import datetime
from core.firebase import db


def get_overview_stats():
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')

        guards_snap = db.reference('guards').get() or {}
        total_guards = len(guards_snap)

        attendance_snap = db.reference('attendance').get() or {}

        checked_in    = 0
        late_arrivals = 0
        absent        = 0
        live_checkins = []

        for uid, dates in attendance_snap.items():
            if not isinstance(dates, dict):
                continue
            rec = dates.get(today_str)
            if not isinstance(rec, dict):
                continue

            status = rec.get('status', '')
            if status == 'on_time':
                checked_in += 1
            elif status == 'late':
                checked_in   += 1
                late_arrivals += 1
            elif status == 'absent':
                absent += 1

            if status in ('on_time', 'late'):
                guard_data = guards_snap.get(uid, {})
                live_checkins.append({
                    'name':   guard_data.get('name', 'Unknown'),
                    'site':   rec.get('site', '—'),
                    'region': rec.get('region', '—'),
                    'time':   rec.get('clock_in', '—'),
                    'status': status,
                })

        live_checkins = sorted(live_checkins, key=lambda x: x['time'], reverse=True)[:10]

        regions_snap = db.reference('regions').get() or {}
        region_stats = []
        for region_id, region_data in regions_snap.items():
            name  = region_data.get('name', region_id)
            total = sum(
                1 for g in guards_snap.values()
                if isinstance(g, dict) and g.get('region') in (region_id, name)
            )
            present = sum(
                1 for uid, dates in attendance_snap.items()
                if isinstance(dates, dict)
                and isinstance(dates.get(today_str), dict)
                and dates[today_str].get('region') in (region_id, name)
                and dates[today_str].get('status') in ('on_time', 'late')
            )
            pct = round((present / total) * 100) if total > 0 else 0
            region_stats.append({'name': name, 'pct': pct})

        region_stats = sorted(region_stats, key=lambda x: x['name'])

        alerts_snap = db.reference('alerts').get() or {}
        alerts = []
        for alert_id, a in alerts_snap.items():
            if not isinstance(a, dict) or a.get('resolved', False):
                continue
            alert_type = a.get('type', 'warning')
            guard_name = a.get('guard_name', 'Unknown Guard')
            site       = a.get('site_name', a.get('site', ''))
            region     = a.get('region', '')

            if alert_type == 'sos':
                title    = f"SOS — {guard_name}"
                subtitle = f"{site} · {region}" if site else region
            elif alert_type == 'absent':
                title    = f"Absent — {guard_name}"
                subtitle = f"{site} · {region}" if site else region
            elif alert_type == 'late':
                title    = f"Late Arrival — {guard_name}"
                subtitle = f"{site} · {region}" if site else region
            else:
                title    = a.get('title', f"Alert — {guard_name}")
                subtitle = a.get('subtitle', region)

            alerts.append({
                'alert_id':   alert_id,          # ← NEW
                'type':       'critical' if alert_type == 'sos' else 'warning',
                'alert_type': alert_type,         # ← NEW (raw type for template logic)
                'title':      title,
                'subtitle':   subtitle,
                'guard_name': guard_name,         # ← NEW (for respond confirmation)
                'lat':        a.get('lat', ''),   # ← NEW (for map link)
                'lng':        a.get('lng', ''),   # ← NEW
            })

        return {
            'total_guards':        total_guards,
            'checked_in':          checked_in,
            'late_arrivals':       late_arrivals,
            'absent':              absent,
            'live_checkins':       live_checkins,
            'region_stats':        region_stats,
            'alerts':              alerts,
            'active_alerts_count': len(alerts),
            'error': None,
        }

    except Exception as e:
        return {
            'total_guards': 0, 'checked_in': 0, 'late_arrivals': 0, 'absent': 0,
            'live_checkins': [], 'region_stats': [], 'alerts': [],
            'active_alerts_count': 0, 'error': str(e),
        }


@login_required
def overview(request):
    stats = get_overview_stats()
    today_display = datetime.now().strftime('%A, %b %d, %Y')
    context = {
        'active_nav':    'overview',
        'page_title':    'Overview',
        'today_display': today_display,
        **stats,
    }
    return render(request, 'overview/overview.html', context)


@login_required
@require_POST
def respond_sos(request, alert_id):
    """Mark an SOS alert as resolved from the dashboard."""
    try:
        alert_ref = db.reference(f'alerts/{alert_id}')
        alert = alert_ref.get()
        if not alert:
            return JsonResponse({'success': False, 'error': 'Alert not found'}, status=404)

        alert_ref.update({
            'resolved':      True,
            'read':          True,
            'responded_at':  datetime.now().isoformat(),
            'responded_by':  request.session.get('uid', 'admin'),
        })
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)