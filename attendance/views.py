from django.shortcuts import render
from datetime import date, timedelta
from firebase_admin import db
from core.decorators import login_required


REGIONS = ["All Regions", "North", "South", "East", "West", "Central"]


def _get_date_range(range_key):
    today = date.today()
    if range_key == "yesterday":
        d = today - timedelta(days=1)
        return str(d), str(d)
    elif range_key == "week":
        return str(today - timedelta(days=6)), str(today)
    else:
        return str(today), str(today)


def _build_records(date_start, date_end, region_filter, status_filter, search):
    """
    Pull from Firebase. Expected structure:

    /guards/{uid}/
        name, initials, avatar_url, avatar_color

    /attendance/{uid}/{date}/
        clock_in, clock_out, status, site, region, shift_start, shift_end
    """
    records = []
    try:
        attendance_data = db.reference("attendance").get() or {}
        guards_data     = db.reference("guards").get() or {}

        for uid, dates in attendance_data.items():
            if not isinstance(dates, dict):
                continue
            guard = guards_data.get(uid, {})

            for record_date, rec in dates.items():
                if not isinstance(rec, dict):
                    continue
                if record_date < date_start or record_date > date_end:
                    continue

                status = rec.get("status", "absent")
                region = rec.get("region", "")
                site   = rec.get("site", "")
                name   = guard.get("name", "Unknown Guard")

                if region_filter != "All Regions" and region != region_filter:
                    continue
                if status_filter != "all" and status != status_filter:
                    continue
                if search and search not in name.lower() and search not in site.lower():
                    continue

                records.append({
                    "id":           f"{uid}_{record_date}",
                    "name":         name,
                    "initials":     guard.get("initials", name[:2].upper()),
                    "avatar_url":   guard.get("avatar_url"),
                    "avatar_color": guard.get("avatar_color", "#6B7280"),
                    "site":         site,
                    "region":       region,
                    "shift_start":  rec.get("shift_start", "--"),
                    "shift_end":    rec.get("shift_end", "--"),
                    "clock_in":     rec.get("clock_in"),
                    "clock_out":    rec.get("clock_out"),
                    "status":       status,
                    "date":         record_date,
                })

    except Exception as e:
        print(f"[Attendance] Firebase error: {e}")

    order = {"absent": 0, "late": 1, "on_time": 2}
    records.sort(key=lambda r: (order.get(r["status"], 9), r["name"]))
    return records


def _get_summary():
    today_str = str(date.today())
    s = {"total_guards": 0, "checked_in": 0, "late_count": 0, "absent_count": 0}
    try:
        guards_data     = db.reference("guards").get() or {}
        attendance_data = db.reference("attendance").get() or {}
        s["total_guards"] = len(guards_data)
        for uid, dates in attendance_data.items():
            if not isinstance(dates, dict):
                continue
            rec = dates.get(today_str, {})
            if not isinstance(rec, dict):
                continue
            status = rec.get("status")
            if status in ("on_time", "late"):
                s["checked_in"] += 1
            if status == "late":
                s["late_count"] += 1
            elif status == "absent":
                s["absent_count"] += 1
    except Exception as e:
        print(f"[Attendance] Summary error: {e}")
    return s


@login_required
def attendance_log(request):
    date_range = request.GET.get("date_range", "today")
    region     = request.GET.get("region", "All Regions")
    status     = request.GET.get("status", "all")
    search     = request.GET.get("search", "").strip().lower()

    date_start, date_end = _get_date_range(date_range)
    records = _build_records(date_start, date_end, region, status, search)
    summary = _get_summary()

    context = {
        "records":        records,
        "regions":        REGIONS,
        "today":          date.today().strftime("%B %d, %Y"),
        "date_options":   [("Today", "today"), ("Yesterday", "yesterday"), ("Last 7 Days", "week")],
        "status_options": [("All", "all"), ("On Time", "on_time"), ("Late", "late"), ("Absent", "absent")],
        "active_range":   date_range,
        "active_region":  region,
        "active_status":  status,
        "search_query":   search,
        "total_guards":   summary["total_guards"],
        "checked_in":     summary["checked_in"],
        "late_count":     summary["late_count"],
        "absent_count":   summary["absent_count"],
        "record_count":   len(records),
        "display_name":   request.session.get("display_name", "Admin"),
    }
    return render(request, "attendance/attendance.html", context)