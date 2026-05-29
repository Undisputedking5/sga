from django.urls import path
from . import views

urlpatterns = [
    path('', views.regions, name='regions'),
]