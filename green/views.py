# services/views.py

import psycopg2
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
import uuid
from datetime import datetime, date

# Helper function to get a database connection
def get_db_connection():
    conn = psycopg2.connect(
        dbname=settings.DATABASES['default']['NAME'],
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT'],
    )
    return conn

# Homepage View
def homepage(request):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Fetch all service categories
        cursor.execute("SELECT Id, CategoryName FROM SERVICE_CATEGORY;")
        categories = cursor.fetchall()

        # Fetch all subcategories
        cursor.execute("SELECT Id, SubcategoryName, ServiceCategoryId FROM SERVICE_SUBCATEGORY;")
        subcategories = cursor.fetchall()

        # Organize subcategories under their respective categories
        category_dict = {cat[0]: {'name': cat[1], 'subcategories': []} for cat in categories}
        for sub in subcategories:
            category_id = sub[2]
            if category_id in category_dict:
                category_dict[category_id]['subcategories'].append({'id': sub[0], 'name': sub[1]})

        context = {
            'categories': category_dict.values()
        }
    except Exception as e:
        print(e)
        context = {'categories': []}
    finally:
        cursor.close()
        conn.close()

    return render(request, 'homepage.html', context)

# Subcategory Services Page for Users
def subcategory_services_user(request, subcategory_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Fetch subcategory details
        cursor.execute("""
            SELECT SubcategoryName, Description, ServiceCategoryId
            FROM SERVICE_SUBCATEGORY
            WHERE Id = %s;
        """, (subcategory_id,))
        subcategory = cursor.fetchone()

        if not subcategory:
            return HttpResponse("Subcategory not found.", status=404)

        subcategory_name, description, service_category_id = subcategory

        # Fetch workers in this service category
        cursor.execute("""
            SELECT W.Id, U.Name, W.Rate, W.TotalFinishOrder
            FROM WORKER W
            JOIN "USER" U ON W.Id = U.Id
            JOIN WORKER_SERVICE_CATEGORY WSC ON W.Id = WSC.WorkerId
            WHERE WSC.ServiceCategoryId = %s;
        """, (service_category_id,))
        workers = cursor.fetchall()

        # Fetch testimonials related to this subcategory
        cursor.execute("""
            SELECT T.Text, T.Rating, U.Name, T.date
            FROM TESTIMONI T
            JOIN TR_SERVICE_ORDER SO ON T.serviceTrId = SO.Id
            JOIN "USER" U ON SO.customerId = U.Id
            WHERE SO.subcategoryId = %s;
        """, (subcategory_id,))
        testimonials = cursor.fetchall()

        # Fetch service sessions under this subcategory
        cursor.execute("""
            SELECT Session, Price
            FROM SERVICE_SESSION
            WHERE SubcategoryId = %s;
        """, (subcategory_id,))
        sessions = cursor.fetchall()

        context = {
            'subcategory_name': subcategory_name,
            'description': description,
            'workers': workers,
            'testimonials': testimonials,
            'sessions': sessions,
            'subcategory_id': subcategory_id,
        }
    except Exception as e:
        print(e)
        context = {}
    finally:
        cursor.close()
        conn.close()

    return render(request, 'servicesessionu.html', context)

# Worker Profile View
def worker_profile(request, worker_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT U.Name, W.Rate, W.TotalFinishOrder, U.PhoneNum, U.DoB, U.Address
            FROM WORKER W
            JOIN "USER" U ON W.Id = U.Id
            WHERE W.Id = %s;
        """, (worker_id,))
        worker = cursor.fetchone()

        if not worker:
            return HttpResponse("Worker not found.", status=404)

        name, rate, total_orders, phone, dob, address = worker

        context = {
            'name': name,
            'rate': rate,
            'total_orders': total_orders,
            'phone': phone,
            'dob': dob,
            'address': address,
        }
    except Exception as e:
        print(e)
        context = {}
    finally:
        cursor.close()
        conn.close()

    return render(request, 'worker-profile.html', context)

# Book Service (Create Service Order)
@csrf_exempt
def book_service(request):
    if request.method == 'POST':
        # Extract POST data
        user_id = request.POST.get('user_id')  # Assuming user authentication
        subcategory_id = request.POST.get('subcategory_id')
        session = request.POST.get('session')
        discount_code = request.POST.get('discount_code')
        payment_method_id = request.POST.get('payment_method')

        # Validate inputs
        if not all([user_id, subcategory_id, session, payment_method_id]):
            return JsonResponse({'status': 'error', 'message': 'Missing required fields.'})

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Fetch session price
            cursor.execute("""
                SELECT Price
                FROM SERVICE_SESSION
                WHERE SubcategoryId = %s AND Session = %s;
            """, (subcategory_id, session))
            session_price = cursor.fetchone()
            if not session_price:
                return JsonResponse({'status': 'error', 'message': 'Invalid session selected.'})
            price = float(session_price[0])

            # Apply discount if applicable
            if discount_code:
                cursor.execute("""
                    SELECT Discount
                    FROM DISCOUNT
                    WHERE Code = %s AND MinTrOrder <= (
                        SELECT COUNT(*) FROM TR_SERVICE_ORDER WHERE customerId = %s
                    );
                """, (discount_code, user_id))
                discount = cursor.fetchone()
                if discount:
                    discount_amount = float(discount[0])
                    price -= discount_amount
                    if price < 0:
                        price = 0
                else:
                    discount_code = None  # Invalid discount code

            # Insert into TR_SERVICE_ORDER
            order_id = uuid.uuid4()
            order_date = date.today()
            service_date = request.POST.get('service_date')  # Assuming service date is provided
            service_time = request.POST.get('service_time')  # Assuming service time is provided

            # Assign a worker (for simplicity, assign a random worker in the category)
            cursor.execute("""
                SELECT WorkerId
                FROM WORKER_SERVICE_CATEGORY
                WHERE ServiceCategoryId = (
                    SELECT ServiceCategoryId FROM SERVICE_SUBCATEGORY WHERE Id = %s
                )
                ORDER BY RANDOM()
                LIMIT 1;
            """, (subcategory_id,))
            worker = cursor.fetchone()
            if worker:
                worker_id = worker[0]
            else:
                worker_id = None  # No worker available

            cursor.execute("""
                INSERT INTO TR_SERVICE_ORDER (
                    Id, orderDate, serviceDate, serviceTime, TotalPrice, customerId,
                    workerId, subcategoryId, Session, discountCode, paymentMethodId
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                );
            """, (
                order_id, order_date, service_date, service_time, price, user_id,
                worker_id, subcategory_id, session, discount_code, payment_method_id
            ))

            # Insert initial status as 'Waiting for Payment'
            cursor.execute("""
                SELECT Id FROM ORDER_STATUS WHERE Status = 'Waiting for Payment';
            """)
            status_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO TR_ORDER_STATUS (serviceTrId, statusId, date)
                VALUES (%s, %s, NOW());
            """, (order_id, status_id))

            conn.commit()

            return JsonResponse({'status': 'success', 'message': 'Booking confirmed!', 'redirect_url': reverse('view_user_bookings')})
        except Exception as e:
            print(e)
            conn.rollback()
            return JsonResponse({'status': 'error', 'message': 'An error occurred during booking.'})
        finally:
            cursor.close()
            conn.close()
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

# View User Service Bookings
def view_user_bookings(request):
    user_id = request.GET.get('user_id')  # Assuming user authentication

    if not user_id:
        return HttpResponse("User not authenticated.", status=401)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Apply filters if any
        subcategory_filter = request.GET.get('subcategory')
        status_filter = request.GET.get('status')
        search_input = request.GET.get('search', '').lower()

        query = """
            SELECT SO.Id, SC.CategoryName, SSC.SubcategoryName, SO.TotalPrice,
                   U.Name, OS.Status, SO.orderDate
            FROM TR_SERVICE_ORDER SO
            JOIN SERVICE_SUBCATEGORY SSC ON SO.subcategoryId = SSC.Id
            JOIN SERVICE_CATEGORY SC ON SSC.ServiceCategoryId = SC.Id
            JOIN "USER" U ON SO.workerId = U.Id
            JOIN TR_ORDER_STATUS TOS ON SO.Id = TOS.serviceTrId
            JOIN ORDER_STATUS OS ON TOS.statusId = OS.Id
            WHERE SO.customerId = %s
        """
        params = [user_id]

        if subcategory_filter:
            query += " AND SSC.SubcategoryName ILIKE %s"
            params.append(f"%{subcategory_filter}%")
        if status_filter:
            query += " AND OS.Status = %s"
            params.append(status_filter)
        if search_input:
            query += " AND U.Name ILIKE %s"
            params.append(f"%{search_input}%")

        cursor.execute(query, tuple(params))
        orders = cursor.fetchall()

        # Fetch actions based on status
        order_list = []
        for order in orders:
            order_id, category_name, subcategory_name, total_price, worker_name, status, order_date = order
            action = None
            if status in ['Waiting for Payment', 'Searching for Workers']:
                action = {'type': 'cancel', 'url': reverse('cancel_order', args=[order_id])}
            elif status == 'Completed':
                # Check if testimonial exists
                cursor.execute("""
                    SELECT COUNT(*) FROM TESTIMONI WHERE serviceTrId = %s;
                """, (order_id,))
                testimonial_exists = cursor.fetchone()[0] > 0
                if not testimonial_exists:
                    action = {'type': 'testimonial', 'url': reverse('create_testimonial', args=[order_id])}
            order_list.append({
                'order_id': order_id,
                'category_name': category_name,
                'subcategory_name': subcategory_name,
                'total_price': total_price,
                'worker_name': worker_name,
                'status': status,
                'order_date': order_date,
                'action': action
            })

        context = {
            'orders': order_list
        }
    except Exception as e:
        print(e)
        context = {'orders': []}
    finally:
        cursor.close()
        conn.close()

    return render(request, 'view-user-service-bookings.html', context)

# Cancel Order
def cancel_order(request, order_id):
    user_id = request.GET.get('user_id')  # Assuming user authentication

    if not user_id:
        return HttpResponse("User not authenticated.", status=401)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verify the order belongs to the user and is cancellable
        cursor.execute("""
            SELECT OS.Status
            FROM TR_SERVICE_ORDER SO
            JOIN TR_ORDER_STATUS TOS ON SO.Id = TOS.serviceTrId
            JOIN ORDER_STATUS OS ON TOS.statusId = OS.Id
            WHERE SO.Id = %s AND SO.customerId = %s
            ORDER BY TOS.date DESC LIMIT 1;
        """, (order_id, user_id))
        status = cursor.fetchone()

        if not status or status[0] not in ['Waiting for Payment', 'Searching for Workers']:
            return HttpResponse("Order cannot be cancelled.", status=400)

        # Update order status to 'Cancelled'
        cursor.execute("""
            SELECT Id FROM ORDER_STATUS WHERE Status = 'Cancelled';
        """)
        cancelled_status_id = cursor.fetchone()[0]
        cursor.execute("""
            INSERT INTO TR_ORDER_STATUS (serviceTrId, statusId, date)
            VALUES (%s, %s, NOW());
        """, (order_id, cancelled_status_id))

        conn.commit()
        return redirect('view_user_bookings')
    except Exception as e:
        print(e)
        conn.rollback()
        return HttpResponse("An error occurred while cancelling the order.", status=500)
    finally:
        cursor.close()
        conn.close()

# Create Testimonial
@csrf_exempt
def create_testimonial(request, order_id):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')  # Assuming user authentication
        text = request.POST.get('text')
        rating = request.POST.get('rating')

        if not all([user_id, text, rating]):
            return JsonResponse({'status': 'error', 'message': 'Missing required fields.'})

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Verify the order belongs to the user and is completed
            cursor.execute("""
                SELECT OS.Status
                FROM TR_SERVICE_ORDER SO
                JOIN TR_ORDER_STATUS TOS ON SO.Id = TOS.serviceTrId
                JOIN ORDER_STATUS OS ON TOS.statusId = OS.Id
                WHERE SO.Id = %s AND SO.customerId = %s
                ORDER BY TOS.date DESC LIMIT 1;
            """, (order_id, user_id))
            status = cursor.fetchone()

            if not status or status[0] != 'Completed':
                return JsonResponse({'status': 'error', 'message': 'Cannot create testimonial for this order.'})

            # Check if testimonial already exists
            cursor.execute("""
                SELECT COUNT(*) FROM TESTIMONI WHERE serviceTrId = %s;
            """, (order_id,))
            if cursor.fetchone()[0] > 0:
                return JsonResponse({'status': 'error', 'message': 'Testimonial already exists for this order.'})

            # Insert testimonial
            cursor.execute("""
                INSERT INTO TESTIMONI (serviceTrId, date, Text, Rating)
                VALUES (%s, %s, %s, %s);
            """, (order_id, date.today(), text, rating))

            conn.commit()
            return JsonResponse({'status': 'success', 'message': 'Testimonial created successfully.', 'redirect_url': reverse('view_user_bookings')})
        except Exception as e:
            print(e)
            conn.rollback()
            return JsonResponse({'status': 'error', 'message': 'An error occurred while creating testimonial.'})
        finally:
            cursor.close()
            conn.close()
    else:
        # Render testimonial form
        context = {'order_id': order_id}
        return render(request, 'create-testimonial.html', context)
