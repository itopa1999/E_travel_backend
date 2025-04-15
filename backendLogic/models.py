from datetime import timedelta
from django.db import models
from django.utils import timezone
from administrator.models import User
from django.db.models import Sum, Avg


class Ride(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rides")
    departure = models.CharField(max_length=150)
    destination = models.CharField(max_length=150)
    date_of_departure = models.DateTimeField(default=timezone.now)
    available_seat = models.PositiveIntegerField(null=True, blank=True)
    price_per_seat = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    total_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    to_bal_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        vehicle_info = getattr(self, 'vehicleinfo', None)
        if vehicle_info:
            self.total_price = self.price_per_seat * vehicle_info.seating_capacity
        if self.available_seat:
            self.to_bal_price = self.available_seat * self.price_per_seat
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.first_name}'s ride from {self.departure} to {self.destination}"


class VehicleInfo(models.Model):
    ride = models.OneToOneField(Ride, on_delete=models.CASCADE, related_name='vehicleinfo')
    vehicle_name = models.CharField(max_length=150)
    vehicle_type = models.CharField(max_length=50)
    seating_capacity = models.PositiveIntegerField()
    plate_no = models.CharField(max_length=150)
    vehicle_color = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.vehicle_name} - {self.plate_no}"




class RidePassenger(models.Model):
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name='passengers', null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ride_passengers")
    special_request = models.TextField(null=True, blank=True)
    seat_taken = models.PositiveIntegerField(null=True, blank=True)
    has_paid = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    class PaymentMethod(models.TextChoices):
        ONLINE = "online", "online"
        ARRIVAL = "pay on arrival", "pay on arrival"
        PARK = "pay in car park", "pay in car park"

    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, null=True, blank=True
    )

    def __str__(self):
        return f"{self.user.first_name} - {self.seat_taken} seat(s)"
    
    
    @staticmethod
    def get_passenger_status_summary(driver):
        pending = RidePassenger.objects.filter(ride__user=driver, is_completed=False).count()
        completed = RidePassenger.objects.filter(ride__user=driver, is_completed=True).count()
        return {
            "pending": pending,
            "completed": completed
        }
    

class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['-id', "-is_active"]),
        ]

    def __str__(self):
        return f"{self.user.first_name} - {self.plan}"




class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('debit', 'debit'),
        ('credit', 'credit'),
        ('sub', 'sub'),
    ]
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, related_name="transactions")
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    description = models.CharField(max_length=500)
    tran_type = models.CharField(max_length=500, choices=TRANSACTION_TYPES, default="credit")
    ref = models.CharField(max_length=500)
    date = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['-id']),
        ]

    def __str__(self):
        return f"{self.user.first_name} - transaction on {self.date.strftime('%Y-%m-%d') if self.date else 'N/A'}"

    @staticmethod
    def get_earnings(user=None):
        
        now = timezone.localtime()

        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        filters = {'tran_type': 'credit'}
        if user:
            filters['user'] = user

        today_income = Transaction.objects.filter(date__gte=start_of_today, **filters).aggregate(total=Sum('amount'))['total'] or 0
        week_income = Transaction.objects.filter(date__gte=start_of_week, **filters).aggregate(total=Sum('amount'))['total'] or 0
        month_income = Transaction.objects.filter(date__gte=start_of_month, **filters).aggregate(total=Sum('amount'))['total'] or 0

        return {
            'today': today_income,
            'week': week_income,
            'month': month_income
        }
        
        
class DriverReview(models.Model):
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_received")
    rating = models.PositiveIntegerField(default=5)
    comment = models.TextField(max_length=1000, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"⭐️ {self.rating} - {self.comment[:30]}... for {self.driver.username}"
    
    @staticmethod
    def get_average_rating(user):
        avg = DriverReview.objects.filter(driver=user).aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(avg, 1) if avg else 0.0