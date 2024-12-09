import uuid
from django.shortcuts import render, redirect
from django.db import connection
from django.http import HttpResponseRedirect, JsonResponse
from uuid import uuid4
from datetime import datetime
from django.contrib.auth import logout
from django.contrib.auth.models import User
from green.views import homepage as green_homepage

def login_view(request):
    return render(request, 'login.html')

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
            return redirect(green_homepage)

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
    
    # Render the homepage template from the 'green' app
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
    Handle the worker registration process and redirect to login page upon success.
    """
    if request.method == 'POST':
        # Retrieve form data
        phone_number = request.POST.get('phoneNum')
        bank_name = request.POST.get('bankName')
        acc_number = request.POST.get('accNumber')

        # Check phone number and bank account uniqueness
        if not check_phone_uniqueness(phone_number):
            return render(request, 'worker_register.html', {
                'messages': [f'Phone number {phone_number} is already registered.']
            })

        if not check_bank_account_uniqueness(bank_name, acc_number):
            return render(request, 'worker_register.html', {
                'messages': [f'Bank name "{bank_name}" and account number "{acc_number}" combination is already registered.']
            })

        # Additional worker data
        name = request.POST.get('name')
        sex = request.POST.get('sex')
        pwd = request.POST.get('pwd')
        dob = request.POST.get('dob')
        address = request.POST.get('address')
        npwp = request.POST.get('npwp')
        pic_url = request.POST.get('picUrl')

        # Insert into database
        with connection.cursor() as cursor:
            user_id = str(uuid4())  # Generate unique user ID
            # Insert into "USER" table
            cursor.execute("""
                INSERT INTO "USER" (Name, Pwd, Sex, PhoneNum, DoB, Address, MyPayBalance)
                VALUES (%s, %s, %s, %s, %s, %s, 0)
            """, [name, pwd, sex, phone_number, dob, address])

            # Insert into "worker" table
            cursor.execute("""
                INSERT INTO "WORKER" (id, bankname, accnumber, npwp, picurl, rate, totalfinishorder)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [user_id, bank_name, acc_number, npwp, pic_url, 0.0, 0])

        # Redirect to login page with success message
        return redirect('yellow:iflogin')

    # Render the worker registration form for GET requests
    return render(request, 'worker_register.html')



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
    'SELECT 1 FROM "worker" WHERE bankname = %s AND accnumber = %s',
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

def logout_view(request):
    """
    Handle the logout functionality.
    """
    # Clear the session data
    logout(request)
    # Redirect to the login page
    return redirect('yellow:login')

def user_profile(request):
    if not request.session.get('is_authenticated'):
        return redirect('yellow:iflogin')  # User must be logged in

    user_id = request.session.get('user_id')
    
    # Query the database for the user's details
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, phonenum, dob, address
            FROM "USER"
            WHERE id = %s
        """, [user_id])
        user_data = cursor.fetchone()
    
    if user_data:
        # Map the tuple result to a context dictionary
        context = {
            'name': user_data[0],
            'phone_number': user_data[1],
            'birth_date': user_data[2],
            'address': user_data[3],
        }
        return render(request, 'user-profile.html', context)
    else:
        # If no user found, handle it gracefully (e.g., redirect to login)
        return redirect('yellow:iflogin')
