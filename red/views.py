# red/views.py

from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.http import JsonResponse
from uuid import uuid4
from datetime import datetime, timedelta
import json

from decimal import Decimal

def get_order_status_id(status_name, cursor):
    """
    Helper function to fetch the ID of a given status name.
    """
    cursor.execute("""
        SELECT Id FROM ORDER_STATUS WHERE Status = %s
    """, [status_name])
    row = cursor.fetchone()
    if not row:
        raise Exception(f"Status '{status_name}' does not exist in ORDER_STATUS")
    return row[0]


def order_status(request):
    """
    Redirects users to the 'mypay' page.
    """
    user_id = request.session.get('user_id')

    # Always redirect to 'mypay' page
    return redirect('red:mypay')


def mypay(request):
    """
    Handles displaying MyPay balance, transaction history, and processing transactions.
    """
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
                balance = Decimal(row[0]) if row[0] else Decimal('0.0')

                if transaction_category == 'Top-Up':
                    amount = Decimal(request.POST.get('amount', '0'))
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

                    # Fetch order price and verify status via TR_ORDER_STATUS
                    cursor.execute("""
                        SELECT o.Id, ss.Price, os.Status
                        FROM TR_SERVICE_ORDER o
                        JOIN SERVICE_SESSION ss ON (o.subcategoryId = ss.SubcategoryId AND o.Session = ss.Session)
                        LEFT JOIN (
                            SELECT tos.serviceTrId, os.Status
                            FROM TR_ORDER_STATUS tos
                            JOIN ORDER_STATUS os ON tos.statusId = os.Id
                            WHERE (tos.serviceTrId, tos.date) IN (
                                SELECT serviceTrId, MAX(date)
                                FROM TR_ORDER_STATUS
                                GROUP BY serviceTrId
                            )
                        ) os ON o.Id = os.serviceTrId
                        WHERE o.Id = %s AND o.customerId = %s
                    """, [order_id, user_id])
                    order = cursor.fetchone()
                    if not order:
                        raise Exception("Order not found")
                    _, service_price, current_status = order

                    if current_status != 'Waiting for Payment':
                        raise Exception("Order is not in a payable state")

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

                    # Insert new status 'Payment Confirmed' into TR_ORDER_STATUS
                    payment_confirmed_status_id = get_order_status_id('Payment Confirmed', cursor)
                    cursor.execute("""
                        INSERT INTO TR_ORDER_STATUS (serviceTrId, statusId, date)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                    """, [order_id, payment_confirmed_status_id])

                elif transaction_category == 'Transfer':
                    recipient_phone = request.POST.get('recipient_phone')
                    transfer_amount = Decimal(request.POST.get('transfer_amount', '0'))
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
                    recipient_balance = Decimal(rec_balance_row[0]) if rec_balance_row[0] else Decimal('0.0')

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
                    withdrawal_amount = Decimal(request.POST.get('withdrawal_amount', '0'))
                    bank_name = request.POST.get('bank_name')
                    bank_account_number = request.POST.get('bank_account_number')

                    # Validate withdrawal amount
                    if withdrawal_amount <= 0:
                        raise Exception("Invalid withdrawal amount")
                    if balance < withdrawal_amount:
                        raise Exception("Insufficient balance for withdrawal")

                    # Validate bank details
                    if not bank_name:
                        raise Exception("Bank name is required for withdrawal")
                    if not bank_account_number:
                        raise Exception("Bank account number is required for withdrawal")
                    if not bank_account_number.isdigit() or not (10 <= len(bank_account_number) <= 20):
                        raise Exception("Invalid bank account number format")

                    # Deduct balance
                    new_balance = balance - withdrawal_amount
                    cursor.execute('UPDATE "USER" SET MyPayBalance = %s WHERE Id = %s', [new_balance, user_id])

                    # Insert TR_MYPAY (Withdrawal)
                    cursor.execute("""
                        INSERT INTO TR_MYPAY (Id, UserId, Date, Nominal, CategoryId, Details)
                        VALUES (%s, %s, CURRENT_DATE, %s,
                            (SELECT Id FROM TR_MYPAY_CATEGORY WHERE Name = 'Withdrawal'), %s)
                    """, [uuid4(), user_id, -withdrawal_amount, f"Bank: {bank_name}, Account: {bank_account_number}"])

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
            balance = Decimal(row[0]) if row else Decimal('0.0')

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
            'balance': Decimal('0.0'),
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
                WHERE o.customerId = %s
                AND o.workerId IS NOT NULL
                AND (
                    SELECT os.Status
                    FROM TR_ORDER_STATUS tos
                    JOIN ORDER_STATUS os ON tos.statusId = os.Id
                    WHERE tos.serviceTrId = o.Id
                    ORDER BY tos.date DESC
                    LIMIT 1
                ) = 'Payment Confirmed'
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
    user_id = request.session.get('user_id')

    if not user_id:
        # Redirect to login or show an error
        return redirect('login')  # Replace 'login' with your actual login URL name

    # Retrieve query parameters for filtering
    service_name = request.GET.get('service_name', '')
    service_status = request.GET.get('service_status', '')

    # Fetch service orders assigned to the worker with optional filtering
    with connection.cursor() as cursor:
        query = """
            WITH latest_status AS (
                SELECT 
                    tos.serviceTrId,
                    os.Status,
                    ROW_NUMBER() OVER (PARTITION BY tos.serviceTrId ORDER BY tos.date DESC) as rn
                FROM TR_ORDER_STATUS tos
                JOIN ORDER_STATUS os ON tos.statusId = os.Id
            )
            SELECT 
                o.Id, 
                ssc.SubcategoryName, 
                o.orderDate, 
                o.serviceDate, 
                o.Session, 
                o.TotalPrice, 
                ls.Status, 
                u.Name
            FROM TR_SERVICE_ORDER o
            JOIN SERVICE_SUBCATEGORY ssc ON o.subcategoryId = ssc.Id
            JOIN CUSTOMER c ON o.customerId = c.Id
            JOIN "USER" u ON c.Id = u.Id
            LEFT JOIN latest_status ls ON o.Id = ls.serviceTrId AND ls.rn = 1
            WHERE o.workerId = %s
        """
        params = [user_id]

        if service_name:
            query += " AND ssc.SubcategoryName ILIKE %s"
            params.append(f"%{service_name}%")

        if service_status:
            query += " AND ls.Status = %s"
            params.append(service_status)

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
            'status': stat if stat else 'No Status',
            'user_name': uname,
        })

    return render(request, 'service_job_status.html', {'service_orders': order_list})


def update_service_status(request):
    """
    Handles AJAX requests to update the status of a service order.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('new_status')

        if not order_id or not new_status:
            raise Exception("Missing order_id or new_status")

        # Define valid transitions
        valid_transitions = {
            'Waiting for Worker to Depart': 'Worker Arrived at Location',
            'Worker Arrived at Location': 'Service in Progress',
            'Service in Progress': 'Order Completed',
        }

        with connection.cursor() as cursor:
            # Fetch the latest status of the order
            cursor.execute("""
                SELECT os.Status
                FROM TR_ORDER_STATUS tos
                JOIN ORDER_STATUS os ON tos.statusId = os.Id
                WHERE tos.serviceTrId = %s
                ORDER BY tos.date DESC
                LIMIT 1
            """, [order_id])
            row = cursor.fetchone()
            if not row:
                raise Exception("Service order has no status history")
            current_status = row[0]

            expected_new_status = valid_transitions.get(current_status)
            if expected_new_status != new_status:
                raise Exception("Invalid status transition")

            # Fetch the status ID for the new status
            cursor.execute("""
                SELECT Id FROM ORDER_STATUS WHERE Status = %s
            """, [new_status])
            status_row = cursor.fetchone()
            if not status_row:
                raise Exception("New status does not exist in ORDER_STATUS")
            new_status_id = status_row[0]

            # Insert new status into TR_ORDER_STATUS
            cursor.execute("""
                INSERT INTO TR_ORDER_STATUS (serviceTrId, statusId, date)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
            """, [order_id, new_status_id])

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def service_job1(request):
    """
    Handles the service job filtering form (State 1).
    Just a form page; no queries.
    """
    if request.method == 'POST':
        # category and subcategory selected by the user
        category = request.POST.get('category')
        subcategory = request.POST.get('subcategory')
        # Redirect with GET params
        return redirect(f"/red/service_job2/?category={category}&subcategory={subcategory}")

    return render(request, 'service_job1.html')


def service_job2(request):
    """
    Displays filtered service jobs based on selected category and subcategory (State 2).
    """
    category = request.GET.get('category', '')
    subcategory = request.GET.get('subcategory', '')

    # Fetch available service orders that have no worker assigned
    # Join SERVICE_SUBCATEGORY to get subcategory name, SERVICE_CATEGORY to get category
    with connection.cursor() as cursor:
        query = """
            WITH latest_status AS (
                SELECT 
                    tos.serviceTrId,
                    os.Status,
                    ROW_NUMBER() OVER (PARTITION BY tos.serviceTrId ORDER BY tos.date DESC) as rn
                FROM TR_ORDER_STATUS tos
                JOIN ORDER_STATUS os ON tos.statusId = os.Id
            )
            SELECT 
                o.Id, 
                ssc.SubcategoryName, 
                o.orderDate, 
                o.serviceDate, 
                o.Session, 
                o.TotalPrice, 
                ls.Status, 
                u.Name
            FROM TR_SERVICE_ORDER o
            JOIN SERVICE_SUBCATEGORY ssc ON o.subcategoryId = ssc.Id
            JOIN CUSTOMER c ON o.customerId = c.Id
            JOIN "USER" u ON c.Id = u.Id
            JOIN SERVICE_CATEGORY sc ON ssc.ServiceCategoryId = sc.Id
            LEFT JOIN latest_status ls ON o.Id = ls.serviceTrId AND ls.rn = 1
            WHERE o.workerId IS NULL
        """
        params = []
        if category:
            query += " AND sc.CategoryName = %s"
            params.append(category.replace('_', ' ').title())  # Adjust naming if needed
        if subcategory:
            query += " AND ssc.SubcategoryName ILIKE %s"
            params.append(f"%{subcategory.replace('_', ' ')}%")

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
            'status': stat if stat else 'No Status',
            'user_name': uname,
        })

    return render(request, 'service_job2.html', {'service_orders': order_list})


def accept_order(request):
    """
    Handles AJAX requests to accept a service order.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        if not order_id:
            raise Exception("Order ID not provided")

        user_id = request.session.get('user_id')
        job_date = datetime.now().date()
        job_duration = job_date + timedelta(days=1)  # 1 session = 1 day as stated

        with connection.cursor() as cursor, transaction.atomic():
            # Assign worker and set initial status
            cursor.execute("""
                UPDATE TR_SERVICE_ORDER
                SET workerId = %s, serviceDate = %s, serviceTime = CURRENT_TIMESTAMP
                WHERE Id = %s AND workerId IS NULL
            """, [user_id, job_date, order_id])

            if cursor.rowcount == 0:
                raise Exception("Order not found or already taken")

            # Fetch the 'Waiting for Worker to Depart' status ID
            cursor.execute("""
                SELECT Id FROM ORDER_STATUS WHERE Status = 'Waiting for Worker to Depart'
            """)
            status_row = cursor.fetchone()
            if not status_row:
                raise Exception("Initial status 'Waiting for Worker to Depart' not found in ORDER_STATUS")
            initial_status_id = status_row[0]

            # Insert initial status into TR_ORDER_STATUS
            cursor.execute("""
                INSERT INTO TR_ORDER_STATUS (serviceTrId, statusId, date)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
            """, [order_id, initial_status_id])

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
