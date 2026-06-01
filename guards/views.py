from django.shortcuts import render
from datetime import datetime, timezone
from core.firebase import db
from core.decorators import login_required


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
    """Returns {region_id: display_name} from Firebase."""
    try:
        data = db.reference("regions").get() or {}
        return {rid: r.get("name", rid) for rid, r in data.items() if isinstance(r, dict)}
    except Exception:
        return {}


def _get_regions_list(region_map):
    """Returns (region_id, display_name) tuples for the dropdown."""
    return [("All Regions", "All Regions")] + sorted(region_map.items(), key=lambda x: x[1])


def _fetch_guards(status_filter, region_filter, rank_filter, search, region_map):
    guards    = []
    all_ranks = set()
    try:
        data = db.reference("guards").get() or {}

        for uid, g in data.items():
            if not isinstance(g, dict):
                continue
            rank   = g.get("rank", "")
            name   = g.get("name", "Unknown")
            status = g.get("status", "inactive")
            region = g.get("region", "")   # stored as region_id e.g. "nairobi_cbd"
            if rank:
                all_ranks.add(rank)

            # region_filter value comes from the dropdown — it's a region_id
            if region_filter not in ("All Regions", "", None) and region != region_filter:
                continue
            if status_filter not in ("All Statuses", "", None) and status.lower() != status_filter.lower():
                continue
            if rank_filter not in ("All Ranks", "", None) and rank != rank_filter:
                continue
            if search and search not in name.lower() and search not in g.get("guard_id", "").lower():
                continue

            guards.append({
                "uid":          uid,
                "name":         name,
                "guard_id":     g.get("guard_id", "—"),
                "avatar_url":   g.get("avatar_url"),
                "initials":     g.get("initials", name[:2].upper()),
                "avatar_color": g.get("avatar_color", "#6B7280"),
                "status":       status,
                "region":       region,
                "region_name":  region_map.get(region, region),  # human-readable
                "site_name":    g.get("site_name"),
                "site_sub":     g.get("site_sub"),
                "phone":        g.get("phone", "—"),
                "rank":         rank,
                "last_active":  _relative_time(g.get("last_active")),
            })
    except Exception as e:
        print(f"[Guards] Firebase error: {e}")

    guards.sort(key=lambda g: g["name"])
    return guards, ["All Ranks"] + sorted(all_ranks)


def _get_summary():
    try:
        data       = db.reference("guards").get() or {}
        all_guards = [g for g in data.values() if isinstance(g, dict)]
    except Exception:
        all_guards = []

    total_active   = sum(1 for g in all_guards if g.get("status") == "active")
    on_deployment  = sum(1 for g in all_guards if g.get("site_name"))
    vacancies      = sum(1 for g in all_guards if not g.get("site_name"))
    certifications = sum(1 for g in all_guards if g.get("certified"))
    deployment_pct = round((on_deployment / len(all_guards)) * 100) if all_guards else 0

    return {
        "total_active":   total_active,
        "deployment_pct": deployment_pct,
        "vacancies":      vacancies,
        "certifications": certifications,
    }


@login_required
def guards_directory(request):
    status_filter = request.GET.get("status", "All Statuses")
    region_filter = request.GET.get("region", "All Regions")
    rank_filter   = request.GET.get("rank",   "All Ranks")
    search        = request.GET.get("search", "").strip().lower()

    region_map    = _get_region_map()
    guards, ranks = _fetch_guards(status_filter, region_filter, rank_filter, search, region_map)
    summary       = _get_summary()
    regions       = _get_regions_list(region_map)

    context = {
        "guards":        guards,
        "guard_count":   len(guards),
        "statuses":      ["All Statuses", "active", "on_leave", "urgent", "inactive"],
        "regions":       regions,
        "ranks":         ranks,
        "active_status": status_filter,
        "active_region": region_filter,
        "active_rank":   rank_filter,
        "search_query":  search,
        "summary":       summary,
        "display_name":  request.session.get("display_name", "Admin"),
    }
    return render(request, "guards/guards.html", context)

import uuid
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_POST


@login_required
@require_POST
def add_guard(request):
    try:
        name     = request.POST.get('name', '').strip()
        guard_id = request.POST.get('guard_id', '').strip().upper()
        phone    = request.POST.get('phone', '').strip()
        rank     = request.POST.get('rank', '').strip()
        region   = request.POST.get('region', '').strip()

        if not name or not guard_id or not region:
            return JsonResponse({'success': False, 'error': 'Name, Guard ID, and Region are required.'})

        uid = f"guard_{uuid.uuid4().hex[:12]}"
        db.reference(f'/guards/{uid}').set({
            'name':        name,
            'guard_id':    guard_id,
            'initials':    ''.join(w[0].upper() for w in name.split()[:2]),
            'phone':       phone,
            'rank':        rank,
            'region':      region,
            'status':      'active',
            'certified':   False,
            'last_active': datetime.utcnow().isoformat() + 'Z',
        })
        return JsonResponse({'success': True})
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