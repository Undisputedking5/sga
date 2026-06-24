from django.urls import path
from . import views

app_name = 'overview'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('respond-sos/<str:alert_id>/', views.respond_sos, name='respond_sos'),

]