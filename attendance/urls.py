from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.attendance_log, name='log'),
    path('export/', views.export_attendance_csv, name='export'),
]