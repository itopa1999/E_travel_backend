from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(Subscription)
admin.site.register(Transaction)
admin.site.register(Ride)
admin.site.register(RidePassenger)
admin.site.register(DriverReview)
admin.site.register(VehicleInfo)