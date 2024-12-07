from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from datetime import date

# Helper function for database queries
def execute_query(query, params=()):
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()

# View Testimonials on Subcategory Services Page
def subcategory_services_testimonials(request, subcategory_id):
    try:
        # Fetch testimonials for the subcategory where service order status is "Order Completed"
        testimonials = execute_query("""
            SELECT T.Text, T.Rating, U.Name, T.Date
            FROM TESTIMONI T
            JOIN TR_SERVICE_ORDER SO ON T.serviceTrId = SO.Id
            JOIN "USER" U ON SO.customerId = U.Id
            WHERE SO.subcategoryId = %s AND SO.Status = 'Order Completed';
        """, (subcategory_id,))
        context = {'testimonials': testimonials, 'subcategory_id': subcategory_id}
    except Exception as e:
        print(e)
        context = {'testimonials': []}
    
    return render(request, 'subcategory_testimonials.html', context)

# Add a Testimonial
@csrf_exempt
def add_testimonial(request, order_id):
    if request.method == 'POST':
        try:
            rating = request.POST.get('rating')
            comment_text = request.POST.get('comment')
            user_id = request.user.id  # Assume user authentication
            
            # Validate order status
            order = execute_query("""
                SELECT Id FROM TR_SERVICE_ORDER
                WHERE Id = %s AND customerId = %s AND Status = 'Order Completed';
            """, (order_id, user_id))
            
            if not order:
                return JsonResponse({'status': 'error', 'message': 'Order not eligible for testimonial.'})
            
            # Insert testimonial
            execute_query("""
                INSERT INTO TESTIMONI (Text, Rating, serviceTrId, Date)
                VALUES (%s, %s, %s, NOW());
            """, (comment_text, rating, order_id))
            
            return JsonResponse({'status': 'success', 'message': 'Testimonial added!'})
        except Exception as e:
            print(e)
            return JsonResponse({'status': 'error', 'message': 'An error occurred while adding testimonial.'})
    else:
        return HttpResponse("Invalid request method.", status=405)

# Discount Page View
def discount_page(request):
    try:
        # Fetch available vouchers
        vouchers = execute_query("""
            SELECT Id, VoucherName, DiscountAmount, ExpiryDate
            FROM VOUCHER
            WHERE ExpiryDate >= CURRENT_DATE;
        """)
        context = {'vouchers': vouchers}
    except Exception as e:
        print(e)
        context = {'vouchers': []}
    
    return render(request, 'discount_page.html', context)

# Purchase Voucher
@csrf_exempt
def purchase_voucher(request, voucher_id):
    if request.method == 'POST':
        try:
            payment_method = request.POST.get('payment_method')
            user_id = request.user.id  # Assume user authentication
            
            # Check voucher validity
            voucher = execute_query("""
                SELECT DiscountAmount FROM VOUCHER
                WHERE Id = %s AND ExpiryDate >= CURRENT_DATE;
            """, (voucher_id,))
            
            if not voucher:
                return JsonResponse({'status': 'error', 'message': 'Voucher not available.'})
            
            discount_amount = voucher[0][0]
            
            if payment_method == 'MyPay':
                # Check MyPay balance
                balance = execute_query("""
                    SELECT Balance FROM USER_WALLET WHERE userId = %s;
                """, (user_id,))
                
                if not balance or balance[0][0] < discount_amount:
                    return JsonResponse({'status': 'error', 'message': 'Insufficient MyPay balance.'})
                
                # Deduct balance
                execute_query("""
                    UPDATE USER_WALLET SET Balance = Balance - %s WHERE userId = %s;
                """, (discount_amount, user_id))
            
            # Complete voucher purchase
            execute_query("""
                INSERT INTO USER_VOUCHER (userId, voucherId, PurchaseDate)
                VALUES (%s, %s, NOW());
            """, (user_id, voucher_id))
            
            return JsonResponse({'status': 'success', 'message': 'Voucher purchased successfully!'})
        except Exception as e:
            print(e)
            return JsonResponse({'status': 'error', 'message': 'An error occurred while purchasing voucher.'})
    else:
        return HttpResponse("Invalid request method.", status=405)
