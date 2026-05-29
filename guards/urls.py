from django.urls import path
from . import views

app_name = 'guards'

urlpatterns = [
    path('', views.guards_directory, name='directory'),
]