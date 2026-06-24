from django.shortcuts import render
from datetime import datetime, timezone
from core.firebase import db
from core.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from firebase_admin import auth as firebase_auth
import json


def _relative_time(iso_str):
    if not iso_str:
        return "Unknown"
    try:
        dt  = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        s   = int((now - dt).total_seconds())
        if s < 60:      return "Now (Active)"
        elif s < 3600:  m = s // 60;  return f"{m} minute{'s' if m != 1 else ''} ago"
        elif s < 86400: h = s // 3600; return f"{h} hour{'s' if h != 1 else ''} ago"
        else:           d = s // 86400; return f"{d} day{'s' if d != 1 else ''} ago"
    except Exception:
        return "Unknown"


def _get_region_map():
    try:
        data = db.reference("regions").get() or {}
        return {rid: r.get("name", rid) for rid, r in data.items() if isinstance(r, dict)}
    except Exception:
        return {}


def _get_regions_list(region_map):
    return [("All Regions", "All Regions")] + sorted(region_map.items(), key=lambda x: x[1])


def _fetch_personnel(role_filter, status_filter, region_filter, rank_filter, search, region_map):
    """Fetch guards or managers based on role_filter ('guard' or 'manager')."""
    results   = []
    all_ranks = set()
    try:
        data = db.reference("guards").get() or {}
        for uid, g in data.items():
            if not isinstance(g, dict):
                continue

            role   = g.get("role", "guard")
            # Only include records matching the requested role
            if role != role_filter:
                continue

            rank   = g.get("rank", "")
            name   = g.get("name", "Unknown")
            status = g.get("status", "inactive")
            region = g.get("region", "")

            if rank:
                all_ranks.add(rank)

            if region_filter not in ("All Regions", "", None) and region != region_filter:
                continue
            if status_filter not in ("All Statuses", "", None) and status.lower() != status_filter.lower():
                continue
            if rank_filter not in ("All Ranks", "", None) and rank != rank_filter:
                continue
            if search and search not in name.lower() and search not in g.get("guard_id", "").lower():
                continue

            results.append({
                "uid":          uid,
                "name":         name,
                "guard_id":     g.get("guard_id", "—"),
                "avatar_url":   g.get("avatar_url"),
                "initials":     g.get("initials", name[:2].upper()),
                "avatar_color": g.get("avatar_color", "#6B7280"),
                "status":       status,
                "region":       region,
                "region_name":  region_map.get(region, region),
                "site_name":    g.get("site_name"),
                "site_sub":     g.get("site_sub"),
                "phone":        g.get("phone", "—"),
                "rank":         rank,
                "role":         role,
                "email":        g.get("email", "—"),
                "last_active":  _relative_time(g.get("last_active")),
            })
    except Exception as e:
        print(f"[Guards] Firebase error: {e}")

    results.sort(key=lambda g: g["name"])
    return results, ["All Ranks"] + sorted(all_ranks)


def _get_summary():
    try:
        data       = db.reference("guards").get() or {}
        all_guards = [g for g in data.values() if isinstance(g, dict) and g.get("role", "guard") == "guard"]
        all_managers = [g for g in data.values() if isinstance(g, dict) and g.get("role") == "manager"]
    except Exception:
        all_guards = []
        all_managers = []

    total_active   = sum(1 for g in all_guards if g.get("status") == "active")
    on_deployment  = sum(1 for g in all_guards if g.get("site_name"))
    vacancies      = sum(1 for g in all_guards if not g.get("site_name"))
    certifications = sum(1 for g in all_guards if g.get("certified"))
    deployment_pct = round((on_deployment / len(all_guards)) * 100) if all_guards else 0

    return {
        "total_active":    total_active,
        "deployment_pct":  deployment_pct,
        "vacancies":       vacancies,
        "certifications":  certifications,
        "total_managers":  len(all_managers),
        "active_managers": sum(1 for m in all_managers if m.get("status") == "active"),
    }


@login_required
def guards_directory(request):
    # Which tab is active — 'guards' or 'managers'
    active_tab    = request.GET.get("tab", "guards")
    role_filter   = "manager" if active_tab == "managers" else "guard"

    status_filter = request.GET.get("status", "All Statuses")
    region_filter = request.GET.get("region", "All Regions")
    rank_filter   = request.GET.get("rank",   "All Ranks")
    search        = request.GET.get("search", "").strip().lower()

    region_map              = _get_region_map()
    personnel, ranks        = _fetch_personnel(role_filter, status_filter, region_filter, rank_filter, search, region_map)
    summary                 = _get_summary()
    regions                 = _get_regions_list(region_map)

    context = {
        "guards":        personnel,
        "guard_count":   len(personnel),
        "active_tab":    active_tab,
        "statuses":      ["All Statuses", "active", "on_leave", "urgent", "inactive"],
        "regions":       regions,
        "ranks":         ranks,
        "active_status": status_filter,
        "active_region": region_filter,
        "active_rank":   rank_filter,
        "search_query":  search,
        "summary":       summary,
        "display_name":  request.session.get("display_name", "Admin"),
        "active_nav":    "guards",
    }
    return render(request, "guards/guards.html", context)


@login_required
@require_POST
def add_guard(request):
    try:
        name     = request.POST.get('name', '').strip()
        guard_id = request.POST.get('guard_id', '').strip().upper()
        phone    = request.POST.get('phone', '').strip()
        rank     = request.POST.get('rank', '').strip()
        region   = request.POST.get('region', '').strip()
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '').strip()
        role     = request.POST.get('role', 'guard').strip()

        if not name or not guard_id or not region or not email or not password:
            return JsonResponse({'success': False, 'error': 'Name, Guard ID, Region, Email, and Password are required.'})

        if role not in ('guard', 'manager'):
            return JsonResponse({'success': False, 'error': 'Invalid role.'})

        if len(password) < 6:
            return JsonResponse({'success': False, 'error': 'Password must be at least 6 characters.'})

        try:
            firebase_user = firebase_auth.create_user(
                email=email,
                password=password,
                display_name=name,
            )
            uid = firebase_user.uid
        except firebase_auth.EmailAlreadyExistsError:
            return JsonResponse({'success': False, 'error': f'A user with email {email} already exists.'})

        initials = ''.join(w[0].upper() for w in name.split()[:2])
        db.reference(f'/guards/{uid}').set({
            'name':         name,
            'guard_id':     guard_id,
            'initials':     initials,
            'email':        email,
            'phone':        phone,
            'rank':         rank,
            'region':       region,
            'role':         role,
            'status':       'active',
            'certified':    False,
            'last_active':  datetime.utcnow().isoformat() + 'Z',
            'avatar_color': '#B7131A',
        })

        return JsonResponse({'success': True, 'uid': uid, 'message': f'{role.title()} {name} created successfully.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def deactivate_guard(request, uid):
    try:
        db.reference(f'/guards/{uid}').update({'status': 'inactive'})
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def guard_detail_view(request, uid):
    """View a single guard/manager profile."""
    try:
        guard_raw = db.reference(f'/guards/{uid}').get()
        if not guard_raw or not isinstance(guard_raw, dict):
            from django.http import Http404
            raise Http404("Guard not found")

        region_map = _get_region_map()
        region_id  = guard_raw.get('region', '')

        # Fetch last 14 days of attendance
        try:
            attendance_raw = db.reference(f'/attendance/{uid}').get() or {}
            attendance = []
            for date_str, rec in sorted(attendance_raw.items(), reverse=True)[:14]:
                if not isinstance(rec, dict):
                    continue
                attendance.append({
                    'date':       date_str,
                    'status':     rec.get('status', 'absent'),
                    'clock_in':   rec.get('clock_in', '—'),
                    'clock_out':  rec.get('clock_out', '—'),
                    'site':       rec.get('site', '—'),
                })
        except Exception:
            attendance = []

        # Attendance summary
        present = sum(1 for a in attendance if a['status'] in ('on_time', 'late'))
        absent  = sum(1 for a in attendance if a['status'] == 'absent')
        late    = sum(1 for a in attendance if a['status'] == 'late')

        # Fetch guard's reports
        try:
            reports_raw = db.reference('/reports').get() or {}
            reports = []
            for rid, rep in reports_raw.items():
                if not isinstance(rep, dict):
                    continue
                if rep.get('submitted_by') != uid:
                    continue
                reports.append({
                    'id':     rid,
                    'title':  rep.get('title', 'Untitled'),
                    'date':   rep.get('date', '—'),
                    'status': rep.get('status', 'pending'),
                    'type':   rep.get('type', 'daily'),
                })
            reports.sort(key=lambda x: x['date'], reverse=True)
            reports = reports[:5]
        except Exception:
            reports = []

        guard = {
            'uid':          uid,
            'name':         guard_raw.get('name', 'Unknown'),
            'guard_id':     guard_raw.get('guard_id', '—'),
            'initials':     guard_raw.get('initials', '??'),
            'avatar_color': guard_raw.get('avatar_color', '#B7131A'),
            'avatar_url':   guard_raw.get('avatar_url', ''),
            'email':        guard_raw.get('email', '—'),
            'phone':        guard_raw.get('phone', '—'),
            'rank':         guard_raw.get('rank', '—'),
            'role':         guard_raw.get('role', 'guard'),
            'status':       guard_raw.get('status', 'inactive'),
            'region':       region_id,
            'region_name':  region_map.get(region_id, region_id),
            'site_name':    guard_raw.get('site_name', '—'),
            'certified':    guard_raw.get('certified', False),
            'last_active':  _relative_time(guard_raw.get('last_active')),
        }

        context = {
            'guard':       guard,
            'attendance':  attendance,
            'reports':     reports,
            'present':     present,
            'absent':      absent,
            'late':        late,
            'total_days':  len(attendance),
            'regions':     _get_regions_list(_get_region_map()),
            'page_title':  guard['name'],
            'active_nav':  'guards',
        }
        return render(request, 'guards/guard_detail.html', context)

    except Exception as e:
        from django.http import Http404
        raise Http404(str(e))


@login_required
@require_POST
def edit_guard_view(request, uid):
    """Edit a guard/manager profile."""
    try:
        data = json.loads(request.body)

        guard_raw = db.reference(f'/guards/{uid}').get()
        if not guard_raw:
            return JsonResponse({'error': 'Guard not found.'}, status=404)

        name   = data.get('name', '').strip()
        phone  = data.get('phone', '').strip()
        rank   = data.get('rank', '').strip()
        region = data.get('region', '').strip()
        status = data.get('status', '').strip()

        if not name:
            return JsonResponse({'error': 'Name is required.'}, status=400)
        if status not in ('active', 'on_leave', 'urgent', 'inactive'):
            return JsonResponse({'error': 'Invalid status.'}, status=400)

        initials = ''.join(w[0].upper() for w in name.split()[:2])

        db.reference(f'/guards/{uid}').update({
            'name':     name,
            'initials': initials,
            'phone':    phone,
            'rank':     rank,
            'region':   region,
            'status':   status,
        })

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)