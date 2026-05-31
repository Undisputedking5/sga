from django.urls import path
from . import views

app_name = 'regions'

urlpatterns = [
    path('', views.regions_view, name='regions'),
    path('<str:region_id>/', views.region_detail_view, name='region_detail'),
]