from django.shortcuts import render
from core.decorators import login_required
from core.firebase import db
import logging

logger = logging.getLogger(__name__)


def _get_regions_data():
    """Fetch all regions from Firebase."""
    try:
        regions_ref = db.reference('/regions')
        data = regions_ref.get()
        if not data:
            return {}
        return data
    except Exception as e:
        logger.error(f"Firebase regions fetch error: {e}")
        return {}


def _get_guards_data():
    """Fetch all guards from Firebase."""
    try:
        guards_ref = db.reference('/guards')
        data = guards_ref.get()
        if not data:
            return {}
        return data
    except Exception as e:
        logger.error(f"Firebase guards fetch error: {e}")
        return {}


def _build_region_stats(regions_raw, guards_raw):
    """
    Enrich each region with live guard counts derived from /guards.
    Returns a list of region dicts sorted by region_code.
    """
    # Count guards per region
    region_guard_counts = {}
    region_active_counts = {}
    for uid, guard in (guards_raw or {}).items():
        r = guard.get('region', '')
        if not r:
            continue
        region_guard_counts[r] = region_guard_counts.get(r, 0) + 1
        if guard.get('status') == 'active':
            region_active_counts[r] = region_active_counts.get(r, 0) + 1

    regions = []
    for region_id, region in (regions_raw or {}).items():
        name = region.get('name', 'Unknown Region')
        guard_count = region_guard_counts.get(name, region_guard_counts.get(region_id, 0))
        active_count = region_active_counts.get(name, region_active_counts.get(region_id, 0))

        regions.append({
            'id': region_id,
            'name': name,
            'region_code': region.get('region_code', 'REG-0000'),
            'map_code': region.get('map_code', 'MAP-000'),
            'status': region.get('status', 'stable').lower(),
            'lat': region.get('lat', -1.2921),
            'lng': region.get('lng', 36.8219),
            'sites': region.get('sites', 0),
            'incidents': region.get('incidents', 'low').lower(),
            'manager_uid': region.get('manager_uid', ''),
            'manager_name': region.get('manager_name', 'Unassigned'),
            'image_url': region.get('image_url', ''),
            'guard_count': guard_count,
            'active_count': active_count,
        })

    regions.sort(key=lambda x: x['region_code'])
    return regions


@login_required
def regions_view(request):
    regions_raw = _get_regions_data()
    guards_raw = _get_guards_data()
    regions = _build_region_stats(regions_raw, guards_raw)

    # Summary stats
    total_sectors = len(regions)
    total_personnel = sum(r['guard_count'] for r in regions)
    active_incidents = sum(1 for r in regions if r['incidents'] in ('med', 'high') or r['status'] == 'critical')
    critical_regions = [r for r in regions if r['status'] == 'critical']

    # Map markers — all regions with coordinates
    map_markers = [
        {
            'id': r['id'],
            'name': r['name'],
            'lat': r['lat'],
            'lng': r['lng'],
            'status': r['status'],
            'guard_count': r['guard_count'],
            'sites': r['sites'],
            'incidents': r['incidents'],
        }
        for r in regions
    ]

    # Filter
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '').strip().lower()

    filtered_regions = regions
    if status_filter:
        filtered_regions = [r for r in filtered_regions if r['status'] == status_filter]
    if search_query:
        filtered_regions = [
            r for r in filtered_regions
            if search_query in r['name'].lower() or search_query in r['region_code'].lower()
        ]

    context = {
        'regions': filtered_regions,
        'all_regions': regions,
        'map_markers': map_markers,
        'total_sectors': total_sectors,
        'total_personnel': total_personnel,
        'active_incidents': active_incidents,
        'critical_regions': critical_regions,
        'status_filter': status_filter,
        'search_query': search_query,
        'page_title': 'Regions',
    }
    return render(request, 'regions/regions.html', context)


@login_required
def region_detail_view(request, region_id):
    """Detail view for a single region."""
    regions_raw = _get_regions_data()
    guards_raw = _get_guards_data()

    region_raw = (regions_raw or {}).get(region_id)
    if not region_raw:
        from django.http import Http404
        raise Http404("Region not found")

    regions = _build_region_stats({region_id: region_raw}, guards_raw)
    region = regions[0] if regions else {}

    # Guards in this region
    region_name = region.get('name', '')
    region_guards = [
        {'uid': uid, **guard}
        for uid, guard in (guards_raw or {}).items()
        if guard.get('region', '') in (region_name, region_id)
    ]

    context = {
        'region': region,
        'region_guards': region_guards,
        'page_title': region.get('name', 'Region Detail'),
    }
    return render(request, 'regions/region_detail.html', context)