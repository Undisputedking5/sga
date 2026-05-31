from django.shortcuts import render
from core.decorators import login_required
from datetime import datetime
from firebase_admin import db


def get_overview_stats():
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')

        # --- Guards ---
        guards_snap = db.reference('guards').get() or {}
        total_guards = len(guards_snap)

        # --- Attendance: structure is /attendance/{uid}/{date}/ ---
        attendance_snap = db.reference('attendance').get() or {}

        checked_in   = 0
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
                checked_in  += 1
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

        # --- Region breakdown ---
        regions_snap = db.reference('regions').get() or {}
        region_stats = []
        for region_id, region_data in regions_snap.items():
            name = region_data.get('name', region_id)
            # count guards assigned to this region
            total = sum(
                1 for g in guards_snap.values()
                if isinstance(g, dict) and g.get('region') == region_id
            )
            present = sum(
                1 for uid, dates in attendance_snap.items()
                if isinstance(dates, dict)
                and isinstance(dates.get(today_str), dict)
                and dates[today_str].get('region') == region_id
                and dates[today_str].get('status') in ('on_time', 'late')
            )
            pct = round((present / total) * 100) if total > 0 else 0
            region_stats.append({'name': name, 'pct': pct})

        region_stats = sorted(region_stats, key=lambda x: x['name'])

        # --- Alerts ---
        alerts_snap = db.reference('alerts').get() or {}
        alerts = [
            {
                'type':     a.get('type', 'warning'),
                'title':    a.get('title', ''),
                'subtitle': a.get('subtitle', ''),
            }
            for a in alerts_snap.values()
            if isinstance(a, dict) and not a.get('resolved', False)
        ]

        return {
            'total_guards':       total_guards,
            'checked_in':         checked_in,
            'late_arrivals':      late_arrivals,
            'absent':             absent,
            'live_checkins':      live_checkins,
            'region_stats':       region_stats,
            'alerts':             alerts,
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
        'active_nav':   'overview',
        'page_title':   'Overview',
        'today_display': today_display,
        **stats,
    }
    return render(request, 'overview/overview.html', context)