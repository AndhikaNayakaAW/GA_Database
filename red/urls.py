# red/urls.py
from django.urls import path
from . import views

app_name = 'red'

urlpatterns = [
    path('', views.order_status, name='order_status'),
    path('mypay/', views.mypay, name='mypay'),
    path('service_job_status/', views.service_job_status, name='service_job_status'),
    path('service_job1/', views.service_job1, name='service_job1'),
    path('service_job2/', views.service_job2, name='service_job2'),
    path('update_service_status/', views.update_service_status, name='update_service_status'),
    path('accept_order/', views.accept_order, name='accept_order'),
]
