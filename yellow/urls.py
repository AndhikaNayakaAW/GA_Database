# yellow/urls.py

from django.urls import path
from . import views
from .views import homepage_view, update_user_profile, update_worker_profile, user_profile_view
from django.contrib.auth.views import LogoutView
from .views import profile_worker_view

app_name = 'yellow'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('iflogin/', views.iflogin_view, name='iflogin'),
    path('logout/', views.logout_view, name='logout'),
    path('homepage/', homepage_view, name='homepage'),
    path('role_selection/', views.role_selection_view, name='role_selection'), 
    path('user_register/', views.user_register_view, name='user_register'),  
    path('worker_register/', views.worker_register_view, name='worker_register'),
    path('user/profile/', user_profile_view, name='user_profile'),  
    path('worker/profile/', profile_worker_view, name='worker_profile'),
    path('worker/profile/update/', update_worker_profile, name='update_worker_profile'),
     path('user/profile/update/', update_user_profile, name='update_user_profile'),
]
