from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .models import UserBalance, Transaction, ServiceOrder
from .forms import MyPayTransactionForm

# MyPay View
def mypay_view(request):
    balance = UserBalance.objects.get(user=request.user).balance
    transactions = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'mypay.html', {'balance': balance, 'transactions': transactions})

# MyPay Transaction View
def mypay_transaction_view(request):
    if request.method == 'POST':
        form = MyPayTransactionForm(request.POST)
        if form.is_valid():
            # Process transaction logic here
            form.save()
            return redirect('mypay')  # Redirect to MyPay
    else:
        form = MyPayTransactionForm()
    return render(request, 'mypay_transaction.html', {'form': form})

# Service Job View
def service_job_view(request):
    category = request.GET.get('category', '')
    subcategory = request.GET.get('subcategory', '')
    orders = ServiceOrder.objects.filter(status="Looking for Nearby Worker")
    if category:
        orders = orders.filter(category=category)
    if subcategory:
        orders = orders.filter(subcategory=subcategory)
    return render(request, 'service_job.html', {'orders': orders})

def accept_order(request, order_id):
    order = get_object_or_404(ServiceOrder, id=order_id, status="Looking for Nearby Worker")
    order.status = "Waiting for Worker to Depart"
    order.worker = request.user
    order.save()
    return JsonResponse({'message': 'Order accepted'})

# Service Job Status View
def service_job_status_view(request):
    worker_orders = ServiceOrder.objects.filter(worker=request.user).exclude(status__in=['Order Completed', 'Order Canceled'])
    return render(request, 'service_job_status.html', {'orders': worker_orders})

def update_status(request, order_id):
    order = get_object_or_404(ServiceOrder, id=order_id, worker=request.user)
    if order.status == "Waiting for Worker to Depart":
        order.status = "Worker Arrived at Location"
    elif order.status == "Worker Arrived at Location":
        order.status = "Service in Progress"
    elif order.status == "Service in Progress":
        order.status = "Order Completed"
    order.save()
    return redirect('service_job_status')
