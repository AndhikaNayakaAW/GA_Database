# yellow/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import User, Worker
from django.db import IntegrityError

def iflogin_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Authenticate user
        try:
            user = User.objects.get(phone_num=username, pwd=password)  
            request.session['user_id'] = str(user.id)
            messages.success(request, 'Login successful!')
            return redirect('yellow:dashboard')
        except User.DoesNotExist:
            messages.error(request, 'Invalid phone number or password.')

    # Render the correct template
    return render(request, 'iflogin.html')



def dashboard_view(request):
    if 'user_id' not in request.session:
        messages.warning(request, "Please login first.")
        return redirect('yellow:iflogin')
    return render(request, "yellow/dashboard.html", {"user_id": request.session['user_id']})

def logout_view(request):
    if 'user_id' in request.session:
        del request.session['user_id']
    messages.info(request, "Logged out successfully.")
    return redirect('yellow:login')

# Role Selection View
def role_selection_view(request):
    return render(request, 'role_selection.html')

def user_register_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        password = request.POST.get('password')  # TODO: Hash the password in production
        sex = request.POST.get('sex')
        phone = request.POST.get('phone')
        birthdate = request.POST.get('birthdate')
        address = request.POST.get('address')

        # Validate the form
        if not all([name, password, sex, phone, birthdate, address]):
            messages.error(request, 'All fields are required.')
            return render(request, 'user_register.html')

        if len(phone) > 20:
            messages.error(request, 'Phone number must not exceed 20 characters.')
            return render(request, 'user_register.html')

        # Check if the phone number is already registered
        if User.objects.filter(phone_num=phone).exists():
            messages.error(request, 'Phone number is already registered.')
            return redirect('yellow:iflogin')

        # Create a new user
        try:
            user = User(
                name=name,
                pwd=password,  # Hash this in production
                sex=sex,
                phone_num=phone,
                dob=birthdate,
                address=address,
                my_pay_balance=0.00  # Default balance
            )
            user.save()
            messages.success(request, 'Registration successful!')
            return redirect('yellow:iflogin')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'user_register.html')

    return render(request, 'user_register.html')


# Worker Registration View
def worker_register_view(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            password = request.POST.get('password')
            sex = request.POST.get('sex')
            phone_num = request.POST.get('phone')
            dob = request.POST.get('birthdate')
            address = request.POST.get('address')
            bank_name = request.POST.get('bank')
            account_number = request.POST.get('account')
            npwp = request.POST.get('npwp')
            pic_url = request.POST.get('image')

            # Check if phone number already exists
            if User.objects.filter(phone_num=phone_num).exists():
                messages.error(request, 'Phone number already exists.')
                return redirect('yellow:worker_register')

            # Create the User instance
            user = User.objects.create(
                name=name,
                pwd=password,
                sex=sex,
                phone_num=phone_num,
                dob=dob,
                address=address,
                my_pay_balance=0.0  # Default balance for workers
            )

            # Create the Worker instance
            Worker.objects.create(
                id=user,  # Pass the User instance
                bank_name=bank_name,
                acc_number=account_number,
                npwp=npwp,
                pic_url=pic_url,
                rate=0.0,  # Default rate
                total_finish_order=0  # Default completed orders
            )

            messages.success(request, 'Worker registered successfully!')
            return redirect('yellow:iflogin')  # Redirect to login page
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            return redirect('yellow:worker_register')

    return render(request, 'worker_register.html')