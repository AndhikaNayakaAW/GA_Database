from django.urls import path
from . import views

urlpatterns = [
    # Testimonials
    path('subcategory/<int:subcategory_id>/testimonials/', 
         views.subcategory_services_testimonials, 
         name='subcategory_testimonials'),
    path('order/<int:order_id>/add-testimonial/', 
         views.add_testimonial, 
         name='add_testimonial'),
    
    # Discounts
    path('discounts/', 
         views.discount_page, 
         name='discount_page'),
    path('voucher/<int:voucher_id>/purchase/', 
         views.purchase_voucher, 
         name='purchase_voucher'),
]
