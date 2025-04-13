from rest_framework import serializers
from rest_framework.exceptions import ParseError

from .models import User



class RegUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(required = True)
    subscription_plan = serializers.CharField(required=False, allow_blank=True)
    subscription_price = serializers.CharField(required=False, allow_blank=True)
    class Meta:
        model = User
        fields = ['email','phone', 'full_name','password', "is_driver","is_client",
                  'subscription_plan', 'subscription_price']
        
    def validate_password(self, value):
        if len(value) < 8:
            raise ParseError("Password must be at least 8 characters long.")
        return value
    
    def create(self, validated_data):
        subscription_plan = validated_data.pop('subscription_plan', None)
        subscription_price = validated_data.pop('subscription_price', None)
        
        full_name = validated_data.pop('full_name')
        name_parts = full_name.split()

        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else first_name

        user = User.objects.create(
            first_name=first_name,
            last_name=last_name,
            **validated_data
        )
        
        user.subscription_plan = subscription_plan
        user.subscription_price = subscription_price
        
        
        return user
    
    

class UserVerificationSerializer(serializers.Serializer):
    token = serializers.IntegerField(required = True)
    
    def validate_token(self, value):
        if not (100000 <= value <= 999999):
            raise ParseError("Token must be exactly 6 digits long.")
        return value
    
    

class ResendVerificationTokenSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)



class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)
    
    def validate_password(self, value):
        if len(value) < 8:
            raise ParseError("Password must be at least 8 characters long.")
        return value
    
    
class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    
    
    
class ForgetPasswordVerificationTokenSerializer(serializers.Serializer):
    token = serializers.IntegerField(required=True)
    password = serializers.CharField(required=True)
    
    def validate_password(self, value):
        if len(value) < 8:
            raise ParseError("Password must be at least 8 characters long.")
        return value
    
    def validate_token(self, value):
        if not (100000 <= value <= 999999):
            raise ParseError("Token must be exactly 6 digits long.")
        return value
    
    
    
class ChangePasswordSerializer(serializers.Serializer):
    password = serializers.CharField(required=True)
    password1 = serializers.CharField(required=True)
    password2 = serializers.CharField(required=True)
    
    def validate(self, data):
        password = data.get("password")
        password1 = data.get("password1")
        password2 = data.get("password2")

        if len(password) < 8:
            raise ParseError("Current password must be at least 8 characters long.")

        if len(password1) < 8:
            raise ParseError("New password must be at least 8 characters long.")

        if password1 != password2:
            raise ParseError("New passwords do not match.")

        if password == password1:
            raise ParseError("New password must be different from the current password.")

        return data