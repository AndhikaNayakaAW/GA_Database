# yellow/urls.py

from django.urls import path
from . import views
from .views import homepage_view
from django.contrib.auth.views import LogoutView

app_name = 'yellow'

urlpatterns = [
    path('iflogin/', views.iflogin_view, name='iflogin'),
    path('logout/', views.logout_view, name='logout'),
    path('homepage/', homepage_view, name='homepage'),
    path('role_selection/', views.role_selection_view, name='role_selection'), 
    path('user_register/', views.user_register_view, name='user_register'),  
    path('worker_register/', views.worker_register_view, name='worker_register'),
    path('profile/', views.user_profile, name='user_profile'),  
]
