from django.urls import path
from . import views

app_name = 'guards'

urlpatterns = [
    path('', views.guards_directory, name='directory'),
    path('add/', views.add_guard, name='add_guard'),
    path('deactivate/<str:uid>/', views.deactivate_guard, name='deactivate'),
]