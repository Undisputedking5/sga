from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_view, name='reports'),
    path('<str:report_id>/approve/', views.approve_report, name='approve_report'),
    path('<str:report_id>/notify/', views.send_report_notification, name='notify'),
    path('<str:report_id>/view/', views.report_detail_view, name='report_detail'),
]