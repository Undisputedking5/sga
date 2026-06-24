from django.urls import path
from . import views

app_name = 'guards'

urlpatterns = [
    path('', views.guards_directory, name='directory'),
    path('add/', views.add_guard, name='add_guard'),
    path('deactivate/<str:uid>/', views.deactivate_guard, name='deactivate'),
    path('<str:uid>/', views.guard_detail_view, name='detail'),
    path('<str:uid>/edit/', views.edit_guard_view, name='edit'),
]