from django.shortcuts import render, redirect
from django.db import connection
from django.http import JsonResponse
from uuid import uuid4
from datetime import datetime

def iflogin_view(request):
    """
    Render the iflogin.html template for login functionality and handle login.
    """
    if request.method == 'POST':
        phone_number = request.POST.get('phoneNum')
        password = request.POST.get('pwd')
        
        # Check user credentials
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM "USER" WHERE phonenum = %s AND pwd = %s
            """, [phone_number, password])
            user = cursor.fetchone()

        if user:
            # Login successful: render the homepage template or redirect to a named URL
            return render(request, 'homepage.html')
        else:
            # Login failed, show error message
            return render(request, 'iflogin.html', {'error': 'Invalid phone number or password.'})

    return render(request, 'iflogin.html')

def dashboard_view(request):
    """
    Render the dashboard view for the user.
    """
    return render(request, 'dashboard.html')

def logout_view(request):
    """
    Handle the user logout process.
    """
    return JsonResponse({'message': 'Logout successful', 'success': True})

def role_selection_view(request):
    """
    Render the role selection page for the user.
    """
    return render(request, 'role_selection.html')

def user_register_view(request):
    """
    Validates phone number uniqueness and registers a new user.
    """
    if request.method == 'POST':
        phone_number = request.POST.get('phoneNum')
        if not check_phone_uniqueness(phone_number):
            return JsonResponse({'message': f'Phone number {phone_number} is already registered.', 'success': False})

        name = request.POST.get('name')
        sex = request.POST.get('sex')
        pwd = request.POST.get('pwd')
        dob = request.POST.get('dob')
        address = request.POST.get('address')

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO "USER" (id, name, sex, phonenum, pwd, dob, address, mypaybalance)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, [str(uuid4()), name, sex, phone_number, pwd, dob, address, 0.00])

        return JsonResponse({'message': 'User registered successfully!', 'success': True})

    return JsonResponse({'message': 'Invalid request method', 'success': False})

def worker_register_view(request):
    """
    Validates phone number and bank account uniqueness, then registers a new worker.
    """
    if request.method == 'POST':
        phone_number = request.POST.get('phoneNum')
        bank_name = request.POST.get('bankName')
        acc_number = request.POST.get('accNumber')

        if not check_phone_uniqueness(phone_number):
            return JsonResponse({'message': f'Phone number {phone_number} is already registered.', 'success': False})

        if not check_bank_account_uniqueness(bank_name, acc_number):
            return JsonResponse({
                'message': f'Bank name "{bank_name}" and account number "{acc_number}" combination is already registered.',
                'success': False
            })

        name = request.POST.get('name')
        sex = request.POST.get('sex')
        pwd = request.POST.get('pwd')
        dob = request.POST.get('dob')
        address = request.POST.get('address')
        npwp = request.POST.get('npwp')
        pic_url = request.POST.get('picUrl')

        with connection.cursor() as cursor:
            user_id = str(uuid4())
            cursor.execute("""
                INSERT INTO "USER" (id, name, sex, phonenum, pwd, dob, address, mypaybalance)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, [user_id, name, sex, phone_number, pwd, dob, address, 0.00])

            cursor.execute("""
                INSERT INTO "WORKER" (id, bankname, accnumber, npwp, picurl, rate, totalfinishorder)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [user_id, bank_name, acc_number, npwp, pic_url, 0.0, 0])

        return JsonResponse({'message': 'Worker registered successfully!', 'success': True})

    return JsonResponse({'message': 'Invalid request method', 'success': False})


# Helper Functions
def check_phone_uniqueness(phone_number):
    """
    Verifies if the phone number is unique in the USER table.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM \"USER\" WHERE phonenum = %s", [phone_number])
        result = cursor.fetchone()
    return result is None

def check_bank_account_uniqueness(bank_name, acc_number):
    """
    Verifies if the combination of bank name and account number is unique in the WORKER table.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM \"WORKER\" WHERE bankname = %s AND accnumber = %s",
            [bank_name, acc_number]
        )
        result = cursor.fetchone()
    return result is None