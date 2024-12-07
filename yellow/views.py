import uuid
from django.shortcuts import render, redirect
from django.db import connection
from django.http import HttpResponseRedirect, JsonResponse
from uuid import uuid4
from datetime import datetime
from django.contrib.auth import logout

def iflogin_view(request):
    """
    Handle login functionality and redirect to homepage upon successful login.
    """
    if request.method == 'POST':
        username = request.POST.get('phoneNum')  # Using phoneNum as username
        password = request.POST.get('pwd')
        
        # Check user credentials
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, name FROM "USER" WHERE phonenum = %s AND pwd = %s
            """, [username, password])
            user = cursor.fetchone()

        if user:
            user_id = str(user[0])
            user_name = user[1]  # Fetch the user's name from the database

            # Check if the user is a worker
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM worker WHERE id = %s
                """, [user_id])
                is_worker = cursor.fetchone()

            # Set role based on whether the user is a worker
            role = 'worker' if is_worker else 'user'

            # Store session data
            request.session['user_id'] = user_id
            request.session['username'] = username  
            request.session['user_name'] = user_name  
            request.session['role'] = role
            request.session['is_authenticated'] = True

            # Redirect to homepage
            return redirect('yellow:homepage')

        else:
            # Login failed: show error message
            return render(request, 'iflogin.html', {'messages': ['Invalid username or password.']})

    # Render login page for GET requests
    return render(request, 'iflogin.html')

def homepage_view(request):
    """
    Render the homepage with dynamic user information.
    """
    if not request.session.get('is_authenticated'):
        return redirect('yellow:iflogin')  # Redirect to login if not authenticated

    # Retrieve data from session
    user_name = request.session.get('user_name', 'Unknown User')
    role = request.session.get('role', 'user')  # Default role is 'user'

    context = {
        'role': role,
        'name': user_name,
    }
    return render(request, 'homepage.html', context)


def user_register_view(request):
    """
    Handle the user registration process and redirect to login page upon success.
    """
    if request.method == 'POST':
        # Retrieve form data
        name = request.POST.get('name')
        password = request.POST.get('password')
        sex = request.POST.get('sex')
        phone = request.POST.get('phone')
        birthdate = request.POST.get('birthdate')
        address = request.POST.get('address')

        # Check if phone number already exists
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM \"USER\" WHERE phonenum = %s", [phone])
            if cursor.fetchone():
                # Return error message if phone number exists
                return render(request, 'user_register.html', {
                    'messages': ['Phone number already registered. Please use a different one.']
                })

        # Insert the new user into the database
        with connection.cursor() as cursor:
            cursor.execute("""
                    INSERT INTO "USER" (Name, Pwd, Sex, PhoneNum, DoB, Address, MyPayBalance)
                    VALUES (%s, %s, %s, %s, %s, %s, 0)
                """, [name, password, sex, phone, birthdate, address])

        # Redirect to login page with a success message
        return redirect('yellow:iflogin')  

    # Render the registration form for GET requests
    return render(request, 'user_register.html')



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



def role_selection_view(request):
    """
    Render the role selection page and render appropriate registration pages on form submission.
    """
    if request.method == 'POST':
        # Check which button was clicked
        if 'user_register' in request.POST:
            # Render the user registration page
            return render(request, 'user_register.html')
        elif 'worker_register' in request.POST:
            # Render the worker registration page
            return render(request, 'worker_register.html')

    # Render the role selection page for GET requests
    return render(request, 'role_selection.html')