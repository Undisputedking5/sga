from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
from core.decorators import login_required
from core.firebase import db
import logging
from datetime import datetime, timedelta
import json
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


def _get_reports_data():
    try:
        ref = db.reference('/reports')
        data = ref.get()
        return data or {}
    except Exception as e:
        logger.error(f"Firebase reports fetch error: {e}")
        return {}


def _parse_date(date_str):
    """Parse ISO date string safely."""
    if not date_str:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _build_reports_list(raw):
    """Convert Firebase dict to sorted list, newest first."""
    reports = []
    for rid, r in (raw or {}).items():
        date_obj = _parse_date(r.get('date_submitted', ''))
        reports.append({
            'id': rid,
            'title': r.get('title', 'Untitled Report'),
            'report_code': r.get('report_code', rid),
            'type': r.get('type', 'daily').lower(),
            'status': r.get('status', 'pending').lower(),
            'submitted_by': r.get('submitted_by', 'Unknown'),
            'submitter_uid': r.get('submitter_uid', ''),
            'submitter_initials': r.get('submitter_initials', '??'),
            'submitter_color': r.get('submitter_color', '#6b7280'),
            'submitter_avatar': r.get('submitter_avatar', ''),
            'region': r.get('region', ''),
            'site': r.get('site', ''),
            'date_submitted': r.get('date_submitted', ''),
            'date_obj': date_obj,
            'date_display': date_obj.strftime('%b %d, %Y') if date_obj else '—',
            'time_display': date_obj.strftime('%I:%M %p') if date_obj else '—',
            'notes': r.get('notes', ''),
        })
    reports.sort(key=lambda x: x['date_obj'] or datetime.min, reverse=True)
    return reports


@login_required
def reports_view(request):
    raw = _get_reports_data()
    all_reports = _build_reports_list(raw)

    # ── Summary stats ────────────────────────────────────────────────
    total = len(all_reports)
    approved_count = sum(1 for r in all_reports if r['status'] == 'approved')
    completion_pct = round((approved_count / total * 100)) if total else 0
    critical_count = sum(1 for r in all_reports if r['status'] == 'critical')

    # Overdue: pending reports older than 24h
    cutoff = datetime.now() - timedelta(hours=24)
    overdue_count = sum(
        1 for r in all_reports
        if r['status'] == 'pending' and r['date_obj'] and r['date_obj'] < cutoff
    )

    # Sparkline: submission counts for last 7 days
    today = datetime.now().date()
    sparkline = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = sum(
            1 for r in all_reports
            if r['date_obj'] and r['date_obj'].date() == day
        )
        sparkline.append(count)

    # ── Filters ──────────────────────────────────────────────────────
    type_filter   = request.GET.get('type', '').lower()
    status_filter = request.GET.get('status', '').lower()
    date_from     = request.GET.get('date_from', '')
    date_to       = request.GET.get('date_to', '')
    search_query  = request.GET.get('search', '').strip().lower()
    page          = max(1, int(request.GET.get('page', 1)))

    filtered = all_reports

    if type_filter:
        filtered = [r for r in filtered if r['type'] == type_filter]
    if status_filter:
        filtered = [r for r in filtered if r['status'] == status_filter]
    if search_query:
        filtered = [
            r for r in filtered
            if search_query in r['title'].lower()
            or search_query in r['report_code'].lower()
            or search_query in r['submitted_by'].lower()
            or search_query in r['site'].lower()
        ]
    if date_from:
        df = _parse_date(date_from)
        if df:
            filtered = [r for r in filtered if r['date_obj'] and r['date_obj'] >= df]
    if date_to:
        dt = _parse_date(date_to)
        if dt:
            dt = dt.replace(hour=23, minute=59, second=59)
            filtered = [r for r in filtered if r['date_obj'] and r['date_obj'] <= dt]

    # ── Pagination ───────────────────────────────────────────────────
    total_filtered = len(filtered)
    total_pages    = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    page           = min(page, total_pages)
    start          = (page - 1) * PAGE_SIZE
    end            = start + PAGE_SIZE
    page_reports   = filtered[start:end]

    page_range = list(range(max(1, page - 2), min(total_pages + 1, page + 3)))

    # Unique types for filter dropdown
    all_types = sorted(set(r['type'] for r in all_reports))

    context = {
        'reports': page_reports,
        'total': total,
        'approved_count': approved_count,
        'completion_pct': completion_pct,
        'critical_count': critical_count,
        'overdue_count': overdue_count,
        'sparkline': sparkline,
        'total_filtered': total_filtered,
        'total_pages': total_pages,
        'current_page': page,
        'page_range': page_range,
        'start_idx': start + 1,
        'end_idx': min(end, total_filtered),
        'all_types': all_types,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'page_title': 'Reports',
        'active_nav': 'reports',
    }
    return render(request, 'reports/reports.html', context)


@login_required
def approve_report(request, report_id):
    """AJAX: approve a report."""
    if request.method == 'POST':
        try:
            db.reference(f'/reports/{report_id}').update({'status': 'approved'})
            return JsonResponse({'success': True})
        except Exception as e:
            logger.error(f"Approve report error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False}, status=405)


@login_required
def report_detail_view(request, report_id):
    raw = _get_reports_data()
    report_raw = (raw or {}).get(report_id)
    if not report_raw:
        from django.http import Http404
        raise Http404("Report not found")

    reports = _build_reports_list({report_id: report_raw})
    report = reports[0] if reports else {}

    context = {
        'report': report,
        'page_title': report.get('title', 'Report Detail'),
    }
    return render(request, 'reports/report_detail.html', context)


@login_required
@require_POST
def send_report_notification(request, report_id):
    """Send a notification to a guard about their report."""
    try:
        data    = json.loads(request.body)
        message = data.get('message', '').strip()
        notify_type = data.get('type', 'report')  # 'report', 'revision', 'approved'

        if not message:
            return JsonResponse({'error': 'Message is required.'}, status=400)

        # Fetch the report
        report_raw = db.reference(f'/reports/{report_id}').get()
        if not report_raw:
            return JsonResponse({'error': 'Report not found.'}, status=404)

        submitter_uid  = report_raw.get('submitter_uid', '') or report_raw.get('submitted_by', '')
        submitter_name = report_raw.get('submitted_by_name', '') or report_raw.get('submitted_by', 'Guard')
        report_title   = report_raw.get('title', 'Report')
        region         = report_raw.get('region_name', '') or report_raw.get('region', '')

        # Write alert to Firebase — Android app listens to /alerts
        alert_ref = db.reference('/alerts').push()
        alert_ref.set({
            'type':        notify_type,
            'title':       f'Re: {report_title}',
            'message':     message,
            'guard_uid':   submitter_uid,
            'guard_name':  submitter_name,
            'site_name':   report_raw.get('site', ''),
            'region':      region,
            'report_id':   report_id,
            'timestamp':   {'.sv': 'timestamp'},
            'read':        False,
            'resolved':    False,
            'sent_by':     request.session.get('display_name', 'Admin'),
        })

        return JsonResponse({'success': True, 'alert_id': alert_ref.key})

    except Exception as e:
        logger.error(f"Send report notification error: {e}")
        return JsonResponse({'error': str(e)}, status=500)