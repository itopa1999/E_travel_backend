from datetime import timedelta
import random
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import re
from django.core.exceptions import ValidationError
from administrator.manager import UserManager

# Create your models here.

def validate_phone(value):
    """ Validates Nigerian phone numbers (08012345678 or +2348012345678) """
    pattern = re.compile(r'^(?:\+234|0)[789][01]\d{8}$')
    if not pattern.match(value):
        raise ValidationError("Enter a valid Nigerian phone number (e.g., 08012345678 or +2348012345678).")

class User(AbstractUser):
    username = None
    email = models.EmailField(max_length=40, unique=True)
    phone = models.CharField(
        max_length=17,
        unique=True,
        validators=[validate_phone]
    )
    is_driver = models.BooleanField(default=False)
    is_client = models.BooleanField(default=False)
    is_available = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_picture/', null=True, blank=True)
    
    def save(self, *args, **kwargs):
        
        if not self.profile_picture:
            import os
            import random
            from django.conf import settings
            
            profile_pictures_path = os.path.join(settings.MEDIA_ROOT, 'profile_picture')
            profile_pictures = os.listdir(profile_pictures_path)

            random_picture = random.choice(profile_pictures)

            self.profile_picture = f"profile_picture/{random_picture}"
        super().save(*args, **kwargs)

    objects=UserManager( )
    USERNAME_FIELD ='email'
    REQUIRED_FIELDS=[]

    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['-id']),
        ]
    
    def __str__(self):
        return f"{self.email}"
    
    

class UserVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def generate_token(self):
        """Generate a 6-digit token"""
        self.token = str(random.randint(100000, 999999))
        self.created_at = timezone.now()

    def is_token_expired(self):
        """Check if token is expired (valid for 10 minutes)"""
        return timezone.now() > self.created_at + timedelta(minutes=10)

    def __str__(self):
        return f"Verification for {self.user.email}"
    
    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['-user', "-token"]),
        ]
    
    def __str__(self):
        return f"{self.email}"
    
    
    

class IdentityInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    selfie = models.ImageField(null=True, blank=True)
    driver_licenses = models.ImageField(null=True, blank=True)
    ID_no = models.CharField(max_length=16, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    
    
    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['-id']),
        ]
    
    def __str__(self):
        return f"{self.user.first_name} identity info"
    
    
    
class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(decimal_places=2, max_digits=80)
    
    def __str__(self):
        return f"{self.user.first_name} - wallet balance {self.balance}"
    
    
    
class ProfileUpdateRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    field = models.CharField(max_length=160, null=True, blank=True)
    value = models.CharField(max_length=160, null=True, blank=True)
    reason = models.CharField(max_length=1600, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.first_name} - wallet balance {self.balance}"