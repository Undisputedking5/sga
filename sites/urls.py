from django.urls import path
from . import views

app_name = 'sites'

urlpatterns = [
    path('', views.sites_view, name='sites'),
    path('add/', views.add_site, name='add_site'),
    path('delete/<str:site_id>/', views.delete_site, name='delete_site'),
    path('generate-qr/<str:site_id>/', views.generate_qr, name='generate_qr'),
    path('export/', views.export_csv, name='export_csv'),
]