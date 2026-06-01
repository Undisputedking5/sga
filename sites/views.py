import csv
import json
import uuid
import qrcode
import base64
from io import BytesIO
from datetime import datetime

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET

from core.decorators import login_required
from core.firebase import db
import logging

logger = logging.getLogger(__name__)


def _get_sites_data():
    """Fetch all sites from Firebase."""
    try:
        ref = db.reference('/sites')
        data = ref.get()
        return data or {}
    except Exception as e:
        logger.error(f"Firebase sites fetch error: {e}")
        return {}


def _get_regions_data():
    """Fetch all regions from Firebase for dropdowns."""
    try:
        ref = db.reference('/regions')
        data = ref.get()
        return data or {}
    except Exception as e:
        logger.error(f"Firebase regions fetch error: {e}")
        return {}


def _build_sites_list(sites_raw):
    """Normalize raw Firebase sites data into a list."""
    sites = []
    for site_id, site in (sites_raw or {}).items():
        sites.append({
            'id': site_id,
            'name': site.get('name', 'Unknown Site'),
            'site_code': site.get('site_code', '—'),
            'region': site.get('region', '—'),
            'lat': site.get('lat', 0),
            'lng': site.get('lng', 0),
            'qr_generated': site.get('qr_generated', False),
            'created_at': site.get('created_at', '—'),
        })
    sites.sort(key=lambda x: x['name'])
    return sites


def _generate_qr_image(site_id, lat, lng):
    """Generate a QR code encoding site_id|lat|lng and return base64 PNG."""
    payload = json.dumps({
        'site_id': site_id,
        'lat': lat,
        'lng': lng,
    })
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


@login_required
def sites_view(request):
    sites_raw = _get_sites_data()
    regions_raw = _get_regions_data()
    all_sites = _build_sites_list(sites_raw)

    # Summary stats
    total_sites = len(all_sites)
    active_sites = total_sites  # all sites are considered active unless you add a status field
    qr_generated = sum(1 for s in all_sites if s['qr_generated'])
    qr_pending = total_sites - qr_generated

    # Regions for filter dropdown
    regions = []
    for region_id, region in (regions_raw or {}).items():
        regions.append({
            'id': region_id,
            'name': region.get('name', region_id),
        })
    regions.sort(key=lambda x: x['name'])

    # Filters
    search_query = request.GET.get('search', '').strip().lower()
    region_filter = request.GET.get('region', '')
    qr_filter = request.GET.get('qr_status', '')

    filtered_sites = all_sites
    if search_query:
        filtered_sites = [
            s for s in filtered_sites
            if search_query in s['name'].lower() or search_query in s['site_code'].lower()
        ]
    if region_filter:
        filtered_sites = [s for s in filtered_sites if s['region'] == region_filter]
    if qr_filter == 'generated':
        filtered_sites = [s for s in filtered_sites if s['qr_generated']]
    elif qr_filter == 'pending':
        filtered_sites = [s for s in filtered_sites if not s['qr_generated']]

    # Pagination
    page = int(request.GET.get('page', 1))
    per_page = 10
    total_pages = max(1, (len(filtered_sites) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    paginated_sites = filtered_sites[start:start + per_page]

    page_range = list(range(max(1, page - 2), min(total_pages + 1, page + 3)))

    context = {
        'sites': paginated_sites,
        'total_sites': total_sites,
        'active_sites': active_sites,
        'qr_generated': qr_generated,
        'qr_pending': qr_pending,
        'regions': regions,
        'search_query': search_query,
        'region_filter': region_filter,
        'qr_filter': qr_filter,
        'page': page,
        'total_pages': total_pages,
        'page_range': page_range,
        'total_filtered': len(filtered_sites),
        'active_nav': 'sites',
        'page_title': 'Sites Management',
    }
    return render(request, 'sites/sites.html', context)


@login_required
@require_POST
def add_site(request):
    """Add a new site to Firebase."""
    try:
        name = request.POST.get('name', '').strip()
        site_code = request.POST.get('site_code', '').strip().upper()
        region = request.POST.get('region', '').strip()
        lat = float(request.POST.get('lat', 0))
        lng = float(request.POST.get('lng', 0))

        if not name or not site_code or not region:
            return JsonResponse({'success': False, 'error': 'Name, code, and region are required.'})

        site_id = f"site_{uuid.uuid4().hex[:10]}"
        ref = db.reference(f'/sites/{site_id}')
        ref.set({
            'name': name,
            'site_code': site_code,
            'region': region,
            'lat': lat,
            'lng': lng,
            'qr_generated': False,
            'created_at': datetime.utcnow().strftime('%b %d, %Y'),
        })
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Add site error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def delete_site(request, site_id):
    """Delete a site from Firebase."""
    try:
        db.reference(f'/sites/{site_id}').delete()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Delete site error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def generate_qr(request, site_id):
    """Generate QR for a site, mark qr_generated=True, return base64 image."""
    try:
        ref = db.reference(f'/sites/{site_id}')
        site = ref.get()
        if not site:
            return JsonResponse({'success': False, 'error': 'Site not found.'})

        lat = site.get('lat', 0)
        lng = site.get('lng', 0)
        qr_b64 = _generate_qr_image(site_id, lat, lng)

        # Mark as generated
        ref.update({'qr_generated': True})

        return JsonResponse({
            'success': True,
            'qr_image': qr_b64,
            'site_name': site.get('name', ''),
            'site_code': site.get('site_code', ''),
        })
    except Exception as e:
        logger.error(f"Generate QR error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_GET
def export_csv(request):
    """Export all sites as CSV."""
    sites_raw = _get_sites_data()
    all_sites = _build_sites_list(sites_raw)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sga_sites.csv"'

    writer = csv.writer(response)
    writer.writerow(['Site Name', 'Site Code', 'Region', 'Latitude', 'Longitude', 'QR Status', 'Date Added'])
    for s in all_sites:
        writer.writerow([
            s['name'],
            s['site_code'],
            s['region'],
            s['lat'],
            s['lng'],
            'Generated' if s['qr_generated'] else 'Pending',
            s['created_at'],
        ])
    return response


from django.shortcuts import render

# Create your views here.