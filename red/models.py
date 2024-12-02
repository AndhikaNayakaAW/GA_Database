from django.db import models
from django.contrib.auth.models import User
import uuid

# User Balance Model
class UserBalance(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user.username} - Balance: {self.balance}"

# Transaction Model
class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('topup', 'Top-Up'),
        ('service_payment', 'Service Payment'),
        ('transfer', 'Transfer'),
        ('withdrawal', 'Withdrawal'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    bank_name = models.CharField(max_length=50, blank=True, null=True)
    bank_account = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"

# Service Order Model
class ServiceOrder(models.Model):
    STATUS_CHOICES = [
        ('Looking for Nearby Worker', 'Looking for Nearby Worker'),
        ('Waiting for Worker to Depart', 'Waiting for Worker to Depart'),
        ('Worker Arrived at Location', 'Worker Arrived at Location'),
        ('Service in Progress', 'Service in Progress'),
        ('Order Completed', 'Order Completed'),
        ('Order Canceled', 'Order Canceled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_orders')
    worker = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_orders')
    category = models.CharField(max_length=50)
    subcategory = models.CharField(max_length=50)
    order_date = models.DateField()
    working_date = models.DateField()
    session = models.CharField(max_length=20)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Looking for Nearby Worker')

    def __str__(self):
        return f"{self.id} - {self.category} - {self.status}"
