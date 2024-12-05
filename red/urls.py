# red/urls.py
from django.urls import path
from . import views

app_name = 'red'

urlpatterns = [
    path('', views.order_status, name='order_status'),  # Home page
    path('mypay/', views.mypay, name='mypay'),  # MyPay overview
    path('mypay/transaction/', views.mypay_transaction, name='mypay_transaction'),  # MyPay transaction
    path('service_job_status/', views.service_job_status, name='service_job_status'),  # Service Job Status
    path('service_job1/', views.service_job1, name='service_job1'),  # Service Job Filter State 1
    path('service_job2/', views.service_job2, name='service_job2'),  # Service Job Filter State 2
    path('update_service_status/', views.update_service_status, name='update_service_status'),  # AJAX endpoint for status updates
    path('accept_order/', views.accept_order, name='accept_order'),  # AJAX endpoint to accept orders
]
