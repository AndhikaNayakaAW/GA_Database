from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from datetime import datetime

# Helper function for database queries
def execute_query(query, params=()):
    """Execute a database query and return the results."""
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()

# View Testimonials on Subcategory Services Page
def subcategory_services_testimonials(request, subcategory_id):
    """
    Fetch and display testimonials for a specific service subcategory
    where service order status is 'Order Completed'.
    """
    try:
        testimonials = execute_query("""
            SELECT T.Text, T.Rating, U.Name, T.Date
            FROM TESTIMONI T
            JOIN TR_SERVICE_ORDER SO ON T.serviceTrId = SO.Id
            JOIN "USER" U ON SO.customerId = U.Id
            WHERE SO.subcategoryId = %s AND SO.Status = 'Order Completed';
        """, (subcategory_id,))
        context = {'testimonials': testimonials, 'subcategory_id': subcategory_id}
    except Exception as e:
        print(f"Error fetching testimonials: {e}")
        context = {'testimonials': [], 'error_message': 'Unable to load testimonials.'}
    
    return render(request, 'subcategory_testimonials.html', context)

# Add a Testimonial
@csrf_exempt
def add_testimonial(request, order_id):
    """
    Handle POST requests to add a testimonial for a completed service order.
    """
    if request.method == 'POST':
        try:
            rating = request.POST.get('rating')
            comment_text = request.POST.get('comment')
            user_id = request.user.id  # Assume user authentication is implemented
            
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
                VALUES (%s, %s, %s, CURRENT_DATE);
            """, (comment_text, rating, order_id))
            
            return JsonResponse({'status': 'success', 'message': 'Testimonial added successfully!'})
        except Exception as e:
            print(f"Error adding testimonial: {e}")
            return JsonResponse({'status': 'error', 'message': 'An error occurred while adding the testimonial.'})
    return HttpResponse("Invalid request method.", status=405)

# Discount Page View
def discount_page(request):
    try:
        # Fetch voucher data
        vouchers = execute_query("""
            SELECT Id, VoucherName, DiscountAmount, ExpiryDate
            FROM VOUCHER
            WHERE ExpiryDate >= CURRENT_DATE;
        """)

        # Add role and name to the context
        context = {
            'vouchers': vouchers,
            'role': request.user.groups.first().name if request.user.groups.exists() else 'Guest',
            'name': request.user.get_full_name() or request.user.username,
        }
    except Exception as e:
        print(f"Error fetching vouchers: {e}")
        context = {'vouchers': [], 'error_message': 'Unable to load vouchers.'}

    return render(request, 'voucherpurchase.html', context)

# Purchase Voucher
@csrf_exempt
def purchase_voucher(request, voucher_id):
    """
    Handle POST requests for purchasing a voucher.
    """
    if request.method == 'POST':
        try:
            payment_method = request.POST.get('payment_method')
            user_id = request.user.id  # Assume user authentication is implemented
            
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
                VALUES (%s, %s, CURRENT_DATE);
            """, (user_id, voucher_id))
            
            return JsonResponse({'status': 'success', 'message': 'Voucher purchased successfully!'})
        except Exception as e:
            print(f"Error purchasing voucher: {e}")
            return JsonResponse({'status': 'error', 'message': 'An error occurred during voucher purchase.'})
    return HttpResponse("Invalid request method.", status=405)


def testimonial_view(request):
    return render(request, 'testimonial.html')