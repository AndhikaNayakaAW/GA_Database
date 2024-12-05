# red/views.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from uuid import uuid4
from datetime import datetime, timedelta
import json

# Home Page View
@login_required
def order_status(request):
    """
    Redirects users to the appropriate page based on their role.
    """
    if request.user.role == 'Worker':
        return redirect('red:service_job_status')
    elif request.user.role == 'User':
        return redirect('red:mypay')
    else:
        return render(request, 'access_denied.html', status=403)

# MyPay Overview View
@login_required
def mypay(request):
    """
    Displays the user's MyPay balance and transaction history.
    """
    user_id = request.user.id

    with connection.cursor() as cursor:
        # Fetch MyPay balance
        cursor.execute("SELECT balance FROM MyPay WHERE user_id = %s", [user_id])
        row = cursor.fetchone()
        balance = row[0] if row else 0.0

        # Fetch Transactions
        cursor.execute("""
            SELECT transaction_id, transaction_type, amount, timestamp, details
            FROM Transactions
            WHERE mypay_id = (SELECT mypay_id FROM MyPay WHERE user_id = %s)
            ORDER BY timestamp DESC
        """, [user_id])
        transactions = cursor.fetchall()

    # Process transactions for template
    transaction_list = []
    for txn in transactions:
        transaction_id, transaction_type, amount, timestamp, details = txn
        transaction_list.append({
            'transaction_id': transaction_id,
            'transaction_type': transaction_type,
            'amount': float(amount),
            'timestamp': timestamp,
            'details': json.loads(details) if details else {},
        })

    context = {
        'phone_number': request.user.phone_number,  # Ensure 'phone_number' exists in User model
        'balance': balance,
        'transactions': transaction_list,
    }

    return render(request, 'mypay.html', context)

# MyPay Transaction View
@login_required
def mypay_transaction(request):
    """
    Handles MyPay transactions: Top-Up, Service Payment, Transfer, Withdrawal.
    """
    user_id = request.user.id

    if request.method == 'POST':
        try:
            transaction_type = request.POST.get('transaction_category')
            with connection.cursor() as cursor:
                # Begin atomic transaction
                with transaction.atomic():
                    # Fetch MyPay info
                    cursor.execute("SELECT mypay_id, balance FROM MyPay WHERE user_id = %s FOR UPDATE", [user_id])
                    mypay = cursor.fetchone()
                    if not mypay:
                        raise Exception("MyPay account not found")
                    mypay_id, balance = mypay

                    details = {}
                    if transaction_type == 'Top-Up':
                        amount = float(request.POST.get('amount', 0))
                        if amount <= 0:
                            raise Exception("Invalid top-up amount")

                        # Update balance
                        new_balance = balance + amount
                        cursor.execute("UPDATE MyPay SET balance = %s WHERE mypay_id = %s", [new_balance, mypay_id])

                        # Insert transaction
                        details = {'method': 'Manual Top-Up'}
                        cursor.execute("""
                            INSERT INTO Transactions (transaction_id, mypay_id, transaction_type, amount, timestamp, details)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, [str(uuid4()), mypay_id, 'TopUp', amount, datetime.now(), json.dumps(details)])

                    elif transaction_type == 'Service Payment':
                        service_session_id = request.POST.get('service_session')
                        order_id = request.POST.get('order_id')  # Ensure 'order_id' is provided in the form
                        if not service_session_id or not order_id:
                            raise Exception("Service session or order ID not provided")

                        # Fetch service price
                        cursor.execute("SELECT price FROM Services WHERE service_id = %s", [service_session_id])
                        service = cursor.fetchone()
                        if not service:
                            raise Exception("Service not found")
                        service_price = float(service[0])

                        if balance < service_price:
                            raise Exception("Insufficient balance for service payment")

                        # Update balance
                        new_balance = balance - service_price
                        cursor.execute("UPDATE MyPay SET balance = %s WHERE mypay_id = %s", [new_balance, mypay_id])

                        # Insert transaction
                        details = {'service_session_id': service_session_id}
                        cursor.execute("""
                            INSERT INTO Transactions (transaction_id, mypay_id, transaction_type, amount, timestamp, details)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, [str(uuid4()), mypay_id, 'ServicePayment', -service_price, datetime.now(), json.dumps(details)])

                        # Update Service Order Status to 'Paid'
                        cursor.execute("""
                            UPDATE ServiceOrders
                            SET status = 'Paid'
                            WHERE order_id = %s AND user_id = %s
                        """, [order_id, user_id])

                    elif transaction_type == 'Transfer':
                        recipient_phone = request.POST.get('recipient_phone')
                        transfer_amount = float(request.POST.get('transfer_amount', 0))
                        if not recipient_phone or transfer_amount <= 0:
                            raise Exception("Recipient phone number and valid transfer amount required")
                        if balance < transfer_amount:
                            raise Exception("Insufficient balance for transfer")

                        # Fetch recipient user_id and mypay_id
                        cursor.execute("SELECT user_id FROM Users WHERE phone_number = %s", [recipient_phone])
                        recipient = cursor.fetchone()
                        if not recipient:
                            raise Exception("Recipient not found")
                        recipient_id = recipient[0]

                        cursor.execute("SELECT mypay_id, balance FROM MyPay WHERE user_id = %s FOR UPDATE", [recipient_id])
                        recipient_mypay = cursor.fetchone()
                        if not recipient_mypay:
                            raise Exception("Recipient MyPay account not found")
                        recipient_mypay_id, recipient_balance = recipient_mypay

                        # Update sender's balance
                        new_balance = balance - transfer_amount
                        cursor.execute("UPDATE MyPay SET balance = %s WHERE mypay_id = %s", [new_balance, mypay_id])

                        # Update recipient's balance
                        new_recipient_balance = recipient_balance + transfer_amount
                        cursor.execute("UPDATE MyPay SET balance = %s WHERE mypay_id = %s", [new_recipient_balance, recipient_mypay_id])

                        # Insert transaction for sender
                        sender_details = {'recipient_phone': recipient_phone}
                        cursor.execute("""
                            INSERT INTO Transactions (transaction_id, mypay_id, transaction_type, amount, timestamp, details)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, [str(uuid4()), mypay_id, 'Transfer', -transfer_amount, datetime.now(), json.dumps(sender_details)])

                        # Insert transaction for recipient
                        recipient_details = {'sender_id': user_id}
                        cursor.execute("""
                            INSERT INTO Transactions (transaction_id, mypay_id, transaction_type, amount, timestamp, details)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, [str(uuid4()), recipient_mypay_id, 'Transfer', transfer_amount, datetime.now(), json.dumps(recipient_details)])

                    elif transaction_type == 'Withdrawal':
                        bank_name = request.POST.get('bank_name')
                        bank_account = request.POST.get('bank_account')
                        withdrawal_amount = float(request.POST.get('withdrawal_amount', 0))
                        if not bank_name or not bank_account or withdrawal_amount <= 0:
                            raise Exception("Bank name, account number, and valid withdrawal amount required")
                        if balance < withdrawal_amount:
                            raise Exception("Insufficient balance for withdrawal")

                        # Update balance
                        new_balance = balance - withdrawal_amount
                        cursor.execute("UPDATE MyPay SET balance = %s WHERE mypay_id = %s", [new_balance, mypay_id])

                        # Insert transaction
                        details = {'bank_name': bank_name, 'bank_account': bank_account}
                        cursor.execute("""
                            INSERT INTO Transactions (transaction_id, mypay_id, transaction_type, amount, timestamp, details)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, [str(uuid4()), mypay_id, 'Withdrawal', -withdrawal_amount, datetime.now(), json.dumps(details)])

                        # Note: Assume external API call here for processing withdrawal

                    else:
                        raise Exception("Invalid transaction type")

            # Commit transaction
            transaction.commit()
            return redirect('red:mypay')

        except Exception as e:
            # Rollback transaction in case of error
            transaction.rollback()

            # Fetch service sessions again for rendering
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT sb.service_booking_id, s.service_name, s.price 
                    FROM ServiceBookings sb 
                    JOIN Services s ON sb.service_id = s.service_id 
                    WHERE sb.user_id = %s AND sb.status = 'Booked'
                """, [user_id])
                service_sessions = cursor.fetchall()

            context = {
                'error': str(e),
                'service_sessions': service_sessions,
            }
            return render(request, 'mypay_transaction.html', context)

    else:
        # GET request: Display transaction form
        with connection.cursor() as cursor:
            # Fetch service sessions for the user to pay for
            cursor.execute("""
                SELECT sb.service_booking_id, s.service_name, s.price 
                FROM ServiceBookings sb 
                JOIN Services s ON sb.service_id = s.service_id 
                WHERE sb.user_id = %s AND sb.status = 'Booked'
            """, [user_id])
            service_sessions = cursor.fetchall()

        context = {
            'service_sessions': service_sessions,
        }
        return render(request, 'mypay_transaction.html', context)

# Service Job Status View
@login_required
def service_job_status(request):
    """
    Displays the service orders assigned to the worker and allows updating their status.
    """
    if request.user.role != 'Worker':
        return render(request, 'access_denied.html', status=403)

    user_id = request.user.id

    with connection.cursor() as cursor:
        # Fetch service orders assigned to the worker
        cursor.execute("""
            SELECT so.order_id, so.service_subcategory, so.order_date, so.working_date, so.session, so.total_amount, so.status, u.name AS user_name
            FROM ServiceOrders so
            JOIN Users u ON so.user_id = u.user_id
            WHERE so.worker_id = %s
            ORDER BY so.order_date DESC
        """, [user_id])
        service_orders = cursor.fetchall()

    # Process service orders for template
    order_list = []
    for order in service_orders:
        order_id, service_subcategory, order_date, working_date, session, total_amount, status, user_name = order
        order_list.append({
            'order_id': order_id,
            'service_subcategory': service_subcategory,
            'order_date': order_date,
            'working_date': working_date,
            'session': session,
            'total_amount': float(total_amount),
            'status': status,
            'user_name': user_name,
        })

    context = {
        'service_orders': order_list,
    }

    return render(request, 'service_job_status.html', context)

# AJAX View to Update Service Order Status
@login_required
def update_service_status(request):
    """
    Handles AJAX requests to update the status of a service order.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    if request.user.role != 'Worker':
        return JsonResponse({'error': 'Access Denied'}, status=403)

    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('new_status')

        if not order_id or not new_status:
            raise Exception("Missing order_id or new_status")

        # Define valid status transitions
        valid_transitions = {
            'Waiting for Worker to Depart': 'Worker Arrived at Location',
            'Worker Arrived at Location': 'Service in Progress',
            'Service in Progress': 'Order Completed',
        }

        with connection.cursor() as cursor:
            # Fetch current status
            cursor.execute("""
                SELECT status FROM ServiceOrders WHERE order_id = %s AND worker_id = %s
            """, [order_id, request.user.id])
            row = cursor.fetchone()
            if not row:
                raise Exception("Service order not found or access denied")
            current_status = row[0]

            # Check if transition is valid
            expected_new_status = valid_transitions.get(current_status)
            if expected_new_status != new_status:
                raise Exception("Invalid status transition")

            # Update status
            cursor.execute("""
                UPDATE ServiceOrders
                SET status = %s
                WHERE order_id = %s AND worker_id = %s
            """, [new_status, order_id, request.user.id])

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

# Service Job Filter State 1 View
@login_required
def service_job1(request):
    """
    Handles the service job filtering form (State 1).
    """
    if request.user.role != 'Worker':
        return render(request, 'access_denied.html', status=403)

    if request.method == 'POST':
        # Retrieve filter parameters
        category = request.POST.get('category')
        subcategory = request.POST.get('subcategory')

        # Redirect to service_job2 with filter parameters
        return redirect('red:service_job2')  # You can pass parameters via GET if needed

    return render(request, 'service_job1.html')

# Service Job Filter State 2 View
@login_required
def service_job2(request):
    """
    Displays filtered service jobs based on selected category and subcategory (State 2).
    """
    if request.user.role != 'Worker':
        return render(request, 'access_denied.html', status=403)

    # Fetch filter parameters (assuming passed via GET or session)
    category = request.GET.get('category', '')
    subcategory = request.GET.get('subcategory', '')

    with connection.cursor() as cursor:
        # Fetch available service orders based on filters
        query = """
            SELECT so.order_id, so.service_subcategory, so.order_date, so.working_date, so.session, so.total_amount, so.status, u.name AS user_name
            FROM ServiceOrders so
            JOIN Users u ON so.user_id = u.user_id
            WHERE so.worker_id IS NULL  # Only orders not yet assigned
        """
        params = []
        if category:
            query += " AND so.service_category = %s"
            params.append(category)
        if subcategory:
            query += " AND so.service_subcategory = %s"
            params.append(subcategory)

        query += " ORDER BY so.order_date DESC"

        cursor.execute(query, params)
        service_orders = cursor.fetchall()

    # Process service orders for template
    order_list = []
    for order in service_orders:
        order_id, service_subcategory, order_date, working_date, session, total_amount, status, user_name = order
        order_list.append({
            'order_id': order_id,
            'service_subcategory': service_subcategory,
            'order_date': order_date,
            'working_date': working_date,
            'session': session,
            'total_amount': float(total_amount),
            'status': status,
            'user_name': user_name,
        })

    context = {
        'service_orders': order_list,
    }

    return render(request, 'service_job2.html', context)

# AJAX View to Accept an Order
@login_required
def accept_order(request):
    """
    Handles AJAX requests to accept a service order.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    if request.user.role != 'Worker':
        return JsonResponse({'error': 'Access Denied'}, status=403)

    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')

        if not order_id:
            raise Exception("Order ID not provided")

        user_id = request.user.id
        job_date = datetime.now().date()
        job_duration = job_date + timedelta(days=1)  # Assuming session=1 day

        with connection.cursor() as cursor:
            # Assign worker and update status
            cursor.execute("""
                UPDATE ServiceOrders
                SET worker_id = %s, status = 'Waiting for Worker to Depart', job_date = %s, job_duration = %s
                WHERE order_id = %s AND worker_id IS NULL
            """, [user_id, job_date, job_duration, order_id])

            if cursor.rowcount == 0:
                raise Exception("Order not found or already taken")

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
