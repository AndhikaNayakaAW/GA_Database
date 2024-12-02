from django.db import models
import uuid

class User(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    sex = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female')])
    phone_num = models.CharField(max_length=20, unique=True)
    pwd = models.CharField(max_length=255)  # You can hash this with Django's authentication later
    dob = models.DateField()
    address = models.CharField(max_length=255)
    my_pay_balance = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return self.name


class Worker(models.Model):
    id = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    bank_name = models.CharField(max_length=100)
    acc_number = models.CharField(max_length=50, unique=True)
    npwp = models.CharField(max_length=50, unique=True)  # Unique tax ID
    pic_url = models.URLField(blank=True, null=True)  # Optional profile picture URL
    rate = models.FloatField(default=0.0)  # Default rating
    total_finish_order = models.IntegerField(default=0)  # Total completed orders

    def __str__(self):
        return f"Worker: {self.id.name} ({self.bank_name})"