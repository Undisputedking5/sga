from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    path('', views.settings_view, name='index'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('update-system/', views.update_system, name='update_system'),
    path('update-security/', views.update_security, name='update_security'),
    path('update-notifications/', views.update_notifications, name='update_notifications'),
    path("upload-avatar/", views.upload_avatar, name="upload_avatar"),
]