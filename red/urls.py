from django.urls import path
from . import views

urlpatterns = [
    path('mypay/', views.mypay_view, name='mypay'),
    path('mypay/transaction/', views.mypay_transaction_view, name='mypay_transaction'),
    path('service_job/', views.service_job_view, name='service_job'),
    path('service_job/accept/<int:order_id>/', views.accept_order, name='accept_order'),
    path('service_job/status/', views.service_job_status_view, name='service_job_status'),
    path('service_job/status/update/<int:order_id>/', views.update_status, name='update_status'),
]
