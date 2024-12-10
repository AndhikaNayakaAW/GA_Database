# red/views.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.http import JsonResponse
from uuid import uuid4
from datetime import datetime, timedelta
import json

def order_status(request):
    """
    Redirects users to the appropriate page based on their role.
    """
    if not request.session.get('is_authenticated'):
        return redirect('/')  # Redirect to login page

    user_id = request.session.get('user_id')

    # Check user role in the database
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1 FROM Worker WHERE Id = %s', [user_id])
        isWorker = cursor.fetchone()

    with connection.cursor() as cursor:
        cursor.execute('SELECT 1 FROM "USER" WHERE Id = %s', [user_id])
        isUser = cursor.fetchone()

    if isWorker:
        return redirect('red:service_job_status')
    elif isUser:
        return redirect('red:mypay')

    return render(request, 'access_denied.html', status=403)


def mypay(request):
    """
    Handles displaying MyPay balance, transaction history, and processing transactions.
    """
    if not request.session.get('is_authenticated'):
        return redirect('/')  # Redirect to login page

    user_id = request.session.get('user_id')

    if request.method == 'POST':
        # Handle transaction processing
        transaction_category = request.POST.get('transaction_category')
        error = None

        try:
            with connection.cursor() as cursor, transaction.atomic():
                # Fetch user balance with row-level locking
                cursor.execute('SELECT MyPayBalance FROM "USER" WHERE Id = %s FOR UPDATE', [user_id])
                row = cursor.fetchone()
                if not row:
                    raise Exception("User not found")
                balance = row[0] if row[0] else 0.0

                if transaction_category == 'Top-Up':
                    amount = float(request.POST.get('amount', 0))
                    if amount <= 0:
                        raise Exception("Invalid top-up amount")

                    # Update user balance
                    new_balance = balance + amount
                    cursor.execute('UPDATE "USER" SET MyPayBalance = %s WHERE Id = %s', [new_balance, user_id])

                    # Insert transaction in TR_MYPAY (Top-Up)
                    cursor.execute("""
                        INSERT INTO TR_MYPAY (Id, UserId, Date, Nominal, CategoryId)
                        VALUES (%s, %s, CURRENT_DATE, %s,
                            (SELECT Id FROM TR_MYPAY_CATEGORY WHERE Name = 'Top-Up'))
                    """, [uuid4(), user_id, amount])

                elif transaction_category == 'Service Payment':
                    # User chooses an order to pay
                    order_id = request.POST.get('order_id')
                    if not order_id:
                        raise Exception("Order ID not provided")

                    # Fetch order price from TR_SERVICE_ORDER joined with SERVICE_SESSION
                    cursor.execute("""
                        SELECT o.Id, ss.Price
                        FROM TR_SERVICE_ORDER o
                        JOIN SERVICE_SESSION ss ON (o.subcategoryId = ss.SubcategoryId AND o.Session = ss.Session)
                        WHERE o.Id = %s AND o.customerId = %s AND o.Status = 'Waiting for Payment'
                    """, [order_id, user_id])
                    order = cursor.fetchone()
                    if not order:
                        raise Exception("Order not found or not in payable state")
                    service_price = float(order[1])

                    if balance < service_price:
                        raise Exception("Insufficient balance for service payment")

                    # Deduct balance
                    new_balance = balance - service_price
                    cursor.execute('UPDATE "USER" SET MyPayBalance = %s WHERE Id = %s', [new_balance, user_id])

                    # Insert TR_MYPAY record (Service Payment)
                    cursor.execute("""
                        INSERT INTO TR_MYPAY (Id, UserId, Date, Nominal, CategoryId)
                        VALUES (%s, %s, CURRENT_DATE, %s,
                            (SELECT Id FROM TR_MYPAY_CATEGORY WHERE Name = 'Payment'))
                    """, [uuid4(), user_id, -service_price])

                    # Update order status to 'Payment Confirmed'
                    cursor.execute("""
                        UPDATE TR_SERVICE_ORDER
                        SET Status = 'Payment Confirmed'
                        WHERE Id = %s AND customerId = %s
                    """, [order_id, user_id])

                elif transaction_category == 'Transfer':
                    recipient_phone = request.POST.get('recipient_phone')
                    transfer_amount = float(request.POST.get('transfer_amount', 0))
                    if not recipient_phone or transfer_amount <= 0:
                        raise Exception("Invalid recipient phone or transfer amount")

                    if balance < transfer_amount:
                        raise Exception("Insufficient balance for transfer")

                    # Find recipient
                    cursor.execute('SELECT Id FROM "USER" WHERE PhoneNum = %s', [recipient_phone])
                    rec = cursor.fetchone()
                    if not rec:
                        raise Exception("Recipient not found")
                    recipient_id = rec[0]

                    # Lock recipient's balance
                    cursor.execute('SELECT MyPayBalance FROM "USER" WHERE Id = %s FOR UPDATE', [recipient_id])
                    rec_balance_row = cursor.fetchone()
                    if not rec_balance_row:
                        raise Exception("Recipient user not found")
                    recipient_balance = rec_balance_row[0] if rec_balance_row[0] else 0.0

                    # Update sender's balance
                    new_balance = balance - transfer_amount
                    cursor.execute('UPDATE "USER" SET MyPayBalance = %s WHERE Id = %s', [new_balance, user_id])

                    # Update recipient's balance
                    new_recipient_balance = recipient_balance + transfer_amount
                    cursor.execute('UPDATE "USER" SET MyPayBalance = %s WHERE Id = %s', [new_recipient_balance, recipient_id])

                    # Insert TR_MYPAY for sender (Payment)
                    cursor.execute("""
                        INSERT INTO TR_MYPAY (Id, UserId, Date, Nominal, CategoryId)
                        VALUES (%s, %s, CURRENT_DATE, %s,
                            (SELECT Id FROM TR_MYPAY_CATEGORY WHERE Name = 'Payment'))
                    """, [uuid4(), user_id, -transfer_amount])

                    # Insert TR_MYPAY for recipient (Adjustment)
                    cursor.execute("""
                        INSERT INTO TR_MYPAY (Id, UserId, Date, Nominal, CategoryId)
                        VALUES (%s, %s, CURRENT_DATE, %s,
                            (SELECT Id FROM TR_MYPAY_CATEGORY WHERE Name = 'Adjustment'))
                    """, [uuid4(), recipient_id, transfer_amount])

                elif transaction_category == 'Withdrawal':
                    withdrawal_amount = float(request.POST.get('withdrawal_amount', 0))
                    if withdrawal_amount <= 0:
                        raise Exception("Invalid withdrawal amount")
                    if balance < withdrawal_amount:
                        raise Exception("Insufficient balance for withdrawal")

                    # Deduct balance
                    new_balance = balance - withdrawal_amount
                    cursor.execute('UPDATE "USER" SET MyPayBalance = %s WHERE Id = %s', [new_balance, user_id])

                    # Insert TR_MYPAY (Withdrawal)
                    cursor.execute("""
                        INSERT INTO TR_MYPAY (Id, UserId, Date, Nominal, CategoryId)
                        VALUES (%s, %s, CURRENT_DATE, %s,
                            (SELECT Id FROM TR_MYPAY_CATEGORY WHERE Name = 'Withdrawal'))
                    """, [uuid4(), user_id, -withdrawal_amount])

                else:
                    raise Exception("Invalid transaction type")

            # Transaction successful, redirect to 'mypay' page
            return redirect('red:mypay')

        except Exception as e:
            # On error, capture the error message
            error = str(e)

    # Handle GET request and display MyPay information
    try:
        with connection.cursor() as cursor:
            # Fetch MyPay balance from "USER"
            cursor.execute('SELECT MyPayBalance FROM "USER" WHERE Id = %s', [user_id])
            row = cursor.fetchone()
            balance = row[0] if row else 0.0

            # Fetch Transactions from TR_MYPAY joined with TR_MYPAY_CATEGORY
            cursor.execute("""
                SELECT t.Id, c.Name, t.Nominal, t.Date
                FROM TR_MYPAY t
                JOIN TR_MYPAY_CATEGORY c ON t.CategoryId = c.Id
                WHERE t.UserId = %s
                ORDER BY t.Date DESC
            """, [user_id])
            transactions = cursor.fetchall()
    except Exception as e:
        return render(request, 'mypay.html', {
            'error': f"Error fetching data: {str(e)}",
            'phone_number': request.session.get('user_phone'),
            'balance': 0.0,
            'transactions': [],
        })

    transaction_list = []
    for txn in transactions:
        txn_id, category, nominal, date = txn
        transaction_list.append({
            'id': str(txn_id),
            'transaction_type': category,
            'amount': float(nominal),
            'timestamp': date.strftime('%Y-%m-%d %H:%M:%S'),
        })

    # If there's an error from POST request, include it in the context
    context = {
        'phone_number': request.session.get('user_phone'),
        'balance': balance,
        'transactions': transaction_list,
    }

    if request.method == 'POST' and 'error' in locals():
        context['error'] = error

    # Fetch service sessions (orders) waiting for payment to populate the form
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT o.Id, ssc.SubcategoryName, ss.Price
                FROM TR_SERVICE_ORDER o
                JOIN SERVICE_SUBCATEGORY ssc ON o.subcategoryId = ssc.Id
                JOIN SERVICE_SESSION ss ON (o.subcategoryId = ss.SubcategoryId AND o.Session = ss.Session)
                WHERE o.customerId = %s AND o.Status = 'Waiting for Payment'
            """, [user_id])
            service_sessions = cursor.fetchall()
    except Exception as e:
        service_sessions = []

    service_sessions_list = []
    for sess in service_sessions:
        oid, sname, price = sess
        service_sessions_list.append({
            'service_booking_id': str(oid),
            'service_name': sname,
            'price': price,
        })

    context['service_sessions'] = service_sessions_list

    return render(request, 'mypay.html', context)


def service_job_status(request):
    """
    Displays the service orders assigned to the worker and allows updating their status.
    """
    if not request.session.get('is_authenticated'):
        return redirect('/')  # Redirect to login page

    if request.session.get('user_role') != 'Worker':
        return render(request, 'access_denied.html', status=403)

    user_id = request.session.get('user_id')

    # Fetch service orders assigned to the worker
    # Join with SERVICE_SUBCATEGORY to get subcategory name
    # Join with CUSTOMER and USER to get customer's name
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT o.Id, ssc.SubcategoryName, o.orderDate, o.serviceDate, o.Session, o.TotalPrice, o.Status, u.Name
            FROM TR_SERVICE_ORDER o
            JOIN SERVICE_SUBCATEGORY ssc ON o.subcategoryId = ssc.Id
            JOIN CUSTOMER c ON o.customerId = c.Id
            JOIN "USER" u ON c.Id = u.Id
            WHERE o.workerId = %s
            ORDER BY o.orderDate DESC
        """, [user_id])
        service_orders = cursor.fetchall()

    order_list = []
    for order in service_orders:
        oid, subcat, odate, sdate, sess, tprice, stat, uname = order
        order_list.append({
            'order_id': str(oid),
            'service_subcategory': subcat,
            'order_date': odate,
            'working_date': sdate,
            'session': sess,
            'total_amount': float(tprice),
            'status': stat,
            'user_name': uname,
        })

    return render(request, 'service_job_status.html', {'service_orders': order_list})


def update_service_status(request):
    """
    Handles AJAX requests to update the status of a service order.
    """
    if not request.session.get('is_authenticated'):
        return redirect('/')  # Redirect to login page

    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    if request.session.get('user_role') != 'Worker':
        return JsonResponse({'error': 'Access Denied'}, status=403)

    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('new_status')

        if not order_id or not new_status:
            raise Exception("Missing order_id or new_status")

        valid_transitions = {
            'Waiting for Worker to Depart': 'Worker Arrived at Location',
            'Worker Arrived at Location': 'Service in Progress',
            'Service in Progress': 'Order Completed',
        }

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT Status FROM TR_SERVICE_ORDER
                WHERE Id = %s AND workerId = %s
            """, [order_id, request.session.get('user_id')])
            row = cursor.fetchone()
            if not row:
                raise Exception("Service order not found or access denied")
            current_status = row[0]

            expected_new_status = valid_transitions.get(current_status)
            if expected_new_status != new_status:
                raise Exception("Invalid status transition")

            cursor.execute("""
                UPDATE TR_SERVICE_ORDER
                SET Status = %s
                WHERE Id = %s AND workerId = %s
            """, [new_status, order_id, request.session.get('user_id')])

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def service_job1(request):
    """
    Handles the service job filtering form (State 1).
    Just a form page; no queries.
    """
    if not request.session.get('is_authenticated'):
        return redirect('/')  # Redirect to login page

    if request.session.get('user_role') != 'Worker':
        return render(request, 'access_denied.html', status=403)

    if request.method == 'POST':
        # category and subcategory selected by the user
        category = request.POST.get('category')
        subcategory = request.POST.get('subcategory')
        # Redirect with GET params
        return redirect(f"{'/service_job2/'}?category={category}&subcategory={subcategory}")

    return render(request, 'service_job1.html')


def service_job2(request):
    """
    Displays filtered service jobs based on selected category and subcategory (State 2).
    """
    if not request.session.get('is_authenticated'):
        return redirect('/')  # Redirect to login page

    if request.session.get('user_role') != 'Worker':
        return render(request, 'access_denied.html', status=403)

    category = request.GET.get('category', '')
    subcategory = request.GET.get('subcategory', '')

    # Fetch available service orders that have no worker assigned
    # Join SERVICE_SUBCATEGORY to get subcategory name, SERVICE_CATEGORY to get category
    with connection.cursor() as cursor:
        query = """
            SELECT o.Id, ssc.SubcategoryName, o.orderDate, o.serviceDate, o.Session, o.TotalPrice, o.Status, u.Name
            FROM TR_SERVICE_ORDER o
            JOIN SERVICE_SUBCATEGORY ssc ON o.subcategoryId = ssc.Id
            JOIN CUSTOMER c ON o.customerId = c.Id
            JOIN "USER" u ON c.Id = u.Id
            JOIN SERVICE_CATEGORY sc ON ssc.ServiceCategoryId = sc.Id
            WHERE o.workerId IS NULL
        """
        params = []
        if category:
            query += " AND sc.CategoryName = %s"
            params.append(category.replace('_', ' ').title())  # Adjust naming if needed
        if subcategory:
            query += " AND ssc.SubcategoryName ILIKE %s"
            params.append('%' + subcategory.replace('_', ' ') + '%')

        query += " ORDER BY o.orderDate DESC"
        cursor.execute(query, params)
        service_orders = cursor.fetchall()

    order_list = []
    for order in service_orders:
        oid, subcat, odate, sdate, sess, tprice, stat, uname = order
        order_list.append({
            'order_id': str(oid),
            'service_subcategory': subcat,
            'order_date': odate,
            'working_date': sdate,
            'session': sess,
            'total_amount': float(tprice),
            'status': stat,
            'user_name': uname,
        })

    return render(request, 'service_job2.html', {'service_orders': order_list})


def accept_order(request):
    """
    Handles AJAX requests to accept a service order.
    """
    if not request.session.get('is_authenticated'):
        return redirect('/')  # Redirect to login page

    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    if request.session.get('user_role') != 'Worker':
        return JsonResponse({'error': 'Access Denied'}, status=403)

    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        if not order_id:
            raise Exception("Order ID not provided")

        user_id = request.session.get('user_id')
        job_date = datetime.now().date()
        job_duration = job_date + timedelta(days=1)  # 1 session = 1 day as stated

        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE TR_SERVICE_ORDER
                SET workerId = %s, Status = 'Waiting for Worker to Depart',
                    serviceDate = %s, 
                    serviceTime = CURRENT_TIMESTAMP
                WHERE Id = %s AND workerId IS NULL
            """, [user_id, job_date, order_id])

            if cursor.rowcount == 0:
                raise Exception("Order not found or already taken")

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
