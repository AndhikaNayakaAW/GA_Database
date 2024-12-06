# urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('subcategory/<uuid:subcategory_id>/user/', views.subcategory_services_user, name='subcategory_services_user'),
    path('worker/<uuid:worker_id>/', views.worker_profile, name='worker_profile'),
    path('book-service/', views.book_service, name='book_service'),
    path('bookings/', views.view_user_bookings, name='view_user_bookings'),
    path('cancel-order/<uuid:order_id>/', views.cancel_order, name='cancel_order'),
    path('create-testimonial/<uuid:order_id>/', views.create_testimonial, name='create_testimonial'),
]
