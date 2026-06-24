from django.urls import path
from . import views

app_name = 'regions'

urlpatterns = [
    path('', views.regions_view, name='regions'),
    path('create/', views.create_region_view, name='create_region'),
    path('<str:region_id>/', views.region_detail_view, name='region_detail'),
    path('<str:region_id>/edit/', views.edit_region_view, name='edit_region'),
    path('<str:region_id>/assign-manager/', views.assign_manager_view, name='assign_manager'),
]