from django.shortcuts import render
from core.decorators import login_required
from core.firebase import db
import logging
import json
import re
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

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
        'active_nav': 'regions',
    }
    return render(request, 'regions/regions.html', context)

@login_required
def region_detail_view(request, region_id):
    regions_raw = _get_regions_data()
    guards_raw  = _get_guards_data()

    region_raw = (regions_raw or {}).get(region_id)
    if not region_raw:
        from django.http import Http404
        raise Http404("Region not found")

    regions = _build_region_stats({region_id: region_raw}, guards_raw)
    region  = regions[0] if regions else {}

    region_name = region.get('name', '')

    # Guards in this region
    region_guards = [
        {'uid': uid, **guard}
        for uid, guard in (guards_raw or {}).items()
        if guard.get('region', '') in (region_name, region_id)
    ]

    # All managers — for the assign manager dropdown
    all_managers = [
        {'uid': uid, 'name': g.get('name', ''), 'region': g.get('region', '')}
        for uid, g in (guards_raw or {}).items()
        if g.get('role') == 'manager'
    ]
    all_managers.sort(key=lambda x: x['name'])

    # Sites in this region
    try:
        sites_raw = db.reference('/sites').get() or {}
        region_sites = [
            {'id': sid, **s}
            for sid, s in sites_raw.items()
            if s.get('region') == region_id
        ]
        region_sites.sort(key=lambda x: x.get('name', ''))
    except Exception:
        region_sites = []

    context = {
        'region':        region,
        'region_id':     region_id,
        'region_guards': region_guards,
        'all_managers':  all_managers,
        'region_sites':  region_sites,
        'page_title':    region.get('name', 'Region Detail'),
    }
    return render(request, 'regions/region_detail.html', context)
@login_required
@require_POST
def assign_manager_view(request, region_id):
    """Assign a manager to a region."""
    try:
        data = json.loads(request.body)
        manager_uid  = data.get('manager_uid', '').strip()
        manager_name = data.get('manager_name', '').strip()

        if not manager_uid or not manager_name:
            return JsonResponse({'error': 'Manager UID and name are required.'}, status=400)

        # Verify the guard exists and has manager role
        guard_snap = db.reference(f'/guards/{manager_uid}').get()
        if not guard_snap:
            return JsonResponse({'error': 'Guard not found.'}, status=404)
        if guard_snap.get('role') != 'manager':
            return JsonResponse({'error': 'Selected guard is not a manager.'}, status=400)

        db.reference(f'/regions/{region_id}').update({
            'manager_uid':  manager_uid,
            'manager_name': manager_name,
        })

        return JsonResponse({'success': True, 'manager_name': manager_name})

    except Exception as e:
        logger.error(f"Assign manager error: {e}")
        return JsonResponse({'error': 'Failed to assign manager.'}, status=500)


@login_required
@require_POST
def edit_region_view(request, region_id):
    """Edit an existing region's details."""
    try:
        data = json.loads(request.body)

        # Check region exists
        existing = db.reference(f'/regions/{region_id}').get()
        if not existing:
            return JsonResponse({'error': 'Region not found.'}, status=404)

        name      = data.get('name', '').strip()
        code      = data.get('region_code', '').strip()
        status    = data.get('status', 'stable')
        incidents = data.get('incidents', 'low')
        lat       = data.get('lat')
        lng       = data.get('lng')
        sites     = data.get('sites', 0)

        if not name or not code:
            return JsonResponse({'error': 'Name and region code are required.'}, status=400)

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid coordinates.'}, status=400)

        if status not in ('stable', 'monitoring', 'critical'):
            return JsonResponse({'error': 'Invalid status.'}, status=400)
        if incidents not in ('low', 'med', 'high'):
            return JsonResponse({'error': 'Invalid incident level.'}, status=400)

        db.reference(f'/regions/{region_id}').update({
            'name':         name,
            'region_code':  code.upper(),
            'status':       status,
            'incidents':    incidents,
            'lat':          lat,
            'lng':          lng,
            'sites':        int(sites),
        })

        return JsonResponse({'success': True})

    except Exception as e:
        logger.error(f"Edit region error: {e}")
        return JsonResponse({'error': 'Failed to update region.'}, status=500)


@login_required
@require_POST
def create_region_view(request):
    try:
        data = json.loads(request.body)

        # ── Validate required fields ──────────────────────────────
        name         = data.get('name', '').strip()
        region_code  = data.get('region_code', '').strip()
        status       = data.get('status', 'stable')
        lat          = data.get('lat')
        lng          = data.get('lng')
        sites        = data.get('sites', 0)
        incidents    = data.get('incidents', 'low')
        manager_name = data.get('manager_name', 'Unassigned').strip()

        if not name or not region_code:
            return JsonResponse({'error': 'Name and region code are required.'}, status=400)

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Latitude and longitude must be valid numbers.'}, status=400)

        if not (-90 <= lat <= 90):
            return JsonResponse({'error': 'Latitude must be between -90 and 90.'}, status=400)
        if not (-180 <= lng <= 180):
            return JsonResponse({'error': 'Longitude must be between -180 and 180.'}, status=400)

        if status not in ('stable', 'monitoring', 'critical'):
            return JsonResponse({'error': 'Invalid status value.'}, status=400)
        if incidents not in ('low', 'med', 'high'):
            return JsonResponse({'error': 'Invalid incidents value.'}, status=400)

        # ── Build region_id from name ─────────────────────────────
        # e.g. "Nairobi CBD" → "nairobi_cbd"
        region_id = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

        # ── Check for duplicate ───────────────────────────────────
        existing = db.reference(f'/regions/{region_id}').get()
        if existing:
            return JsonResponse({'error': f'A region with ID "{region_id}" already exists.'}, status=400)

        # ── Build map_code from region_code ───────────────────────
        # e.g. "NBI-CBD-001" → "nbi_cbd_001"
        map_code = re.sub(r'[^a-z0-9]+', '_', region_code.lower()).strip('_')

        # ── Write to Firebase ─────────────────────────────────────
        region_data = {
            'name':         name,
            'region_code':  region_code.upper(),
            'map_code':     map_code,
            'status':       status,
            'lat':          lat,
            'lng':          lng,
            'sites':        int(sites),
            'incidents':    incidents,
            'manager_uid':  '',
            'manager_name': manager_name,
            'image_url':    '',
        }

        db.reference(f'/regions/{region_id}').set(region_data)

        return JsonResponse({
            'success': True,
            'region_id': region_id,
            'region': {**region_data, 'id': region_id, 'guard_count': 0, 'active_count': 0}
        })

    except Exception as e:
        logger.error(f"Region creation error: {e}")
        return JsonResponse({'error': 'Failed to create region. Please try again.'}, status=500)

