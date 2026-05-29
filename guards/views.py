from django.shortcuts import render
from datetime import datetime, timezone
from firebase_admin import db
from core.decorators import login_required


STATUSES = ["All Statuses", "Active", "On Leave", "Urgent", "Inactive"]
REGIONS  = ["All Regions", "North Sector", "South Sector", "East Sector", "West Sector", "Central"]


def _relative_time(iso_str):
    """Convert ISO timestamp to relative string like '2 hours ago'."""
    if not iso_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())

        if seconds < 60:
            return "Now (Active)"
        elif seconds < 3600:
            m = seconds // 60
            return f"{m} minute{'s' if m != 1 else ''} ago"
        elif seconds < 86400:
            h = seconds // 3600
            return f"{h} hour{'s' if h != 1 else ''} ago"
        else:
            d = seconds // 86400
            return f"{d} day{'s' if d != 1 else ''} ago"
    except Exception:
        return "Unknown"


def _fetch_guards(status_filter, region_filter, rank_filter, search):
    """
    Read all guards from Firebase /guards/ node.
    Applies filters and returns (guard_list, ranks_list).

    Expected Firebase structure:
    /guards/{uid}/
        name:         "Elena Rodriguez"
        guard_id:     "S-88294"
        avatar_url:   null
        initials:     "ER"
        avatar_color: "#4F46E5"
        status:       "active"   ← active | on_leave | urgent | inactive
        region:       "North Sector"
        site_name:    "Metro Plaza"
        site_sub:     "Tower A Reception"
        phone:        "+1 (555) 012-9844"
        rank:         "Officer"
        last_active:  "2026-05-29T07:54:00Z"
    """
    guards = []
    all_ranks = set()

    try:
        data = db.reference("guards").get() or {}

        for uid, g in data.items():
            if not isinstance(g, dict):
                continue

            rank = g.get("rank", "")
            if rank:
                all_ranks.add(rank)

            name    = g.get("name", "Unknown")
            status  = g.get("status", "inactive")
            region  = g.get("region", "")

            # ── Filters ──────────────────────────────────────────────────────
            if status_filter != "All Statuses" and status.lower() != status_filter.lower():
                continue
            if region_filter != "All Regions" and region != region_filter:
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
                "site_name":    g.get("site_name"),
                "site_sub":     g.get("site_sub"),
                "phone":        g.get("phone", "—"),
                "rank":         rank,
                "last_active":  _relative_time(g.get("last_active")),
            })

    except Exception as e:
        print(f"[Guards] Firebase error: {e}")

    guards.sort(key=lambda g: g["name"])
    ranks = ["All Ranks"] + sorted(all_ranks)
    return guards, ranks


def _get_summary(guards_data):
    """Compute bottom summary bar stats from the full unfiltered guard list."""
    try:
        data = db.reference("guards").get() or {}
        all_guards = list(data.values()) if isinstance(data, dict) else []
    except Exception:
        all_guards = []

    total_active    = sum(1 for g in all_guards if isinstance(g, dict) and g.get("status") == "active")
    on_deployment   = sum(1 for g in all_guards if isinstance(g, dict) and g.get("site_name"))
    vacancies       = sum(1 for g in all_guards if isinstance(g, dict) and not g.get("site_name"))
    certifications  = sum(1 for g in all_guards if isinstance(g, dict) and g.get("certified"))

    deployment_pct = (
        round((on_deployment / len(all_guards)) * 100) if all_guards else 0
    )

    return {
        "total_active":    total_active,
        "deployment_pct":  deployment_pct,
        "vacancies":       vacancies,
        "certifications":  certifications,
    }


@login_required
def guards_directory(request):
    status_filter = request.GET.get("status", "All Statuses")
    region_filter = request.GET.get("region", "All Regions")
    rank_filter   = request.GET.get("rank", "All Ranks")
    search        = request.GET.get("search", "").strip().lower()

    guards, ranks = _fetch_guards(status_filter, region_filter, rank_filter, search)
    summary       = _get_summary(guards)

    context = {
        "guards":          guards,
        "guard_count":     len(guards),
        "statuses":        STATUSES,
        "regions":         REGIONS,
        "ranks":           ranks,
        "active_status":   status_filter,
        "active_region":   region_filter,
        "active_rank":     rank_filter,
        "search_query":    search,
        "summary":         summary,
        "display_name":    request.session.get("display_name", "Admin"),
    }
    return render(request, "guards/guards.html", context)