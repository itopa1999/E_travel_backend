from decimal import Decimal
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from datetime import datetime
from django.db.models import Q
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode
import secrets
import requests as req
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken



from backendLogic.models import Subscription, Transaction
from .models import User, UserVerification
from .serializers import *
from .swagger import TaggedAutoSchema

# Create your views here.





class RegisterUser(generics.GenericAPIView):
    swagger_schema = TaggedAutoSchema
    serializer_class = RegUserSerializer
    def post(self, request, *args, **kwargs):
        data = request.data
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
                    
        is_driver = serializer.validated_data.get("is_driver", False)
        is_client = serializer.validated_data.get("is_client", False)
        email = serializer.validated_data.get("email")
        phone = serializer.validated_data.get("phone")
        
        if is_client:
            user = serializer.save(password=make_password(data["password"]))
            self.send_verification(user, request)
            return Response({"message": "Account created. A verification email has been sent.",
                             "email": user.email}, status=status.HTTP_201_CREATED)

        elif is_driver:
            if User.objects.filter(email=email).exists():
                return Response({"error": "Email already exists."}, status=status.HTTP_400_BAD_REQUEST)
            if User.objects.filter(phone=phone).exists():
                return Response({"error": "Phone already exists."}, status=status.HTTP_400_BAD_REQUEST)
            
            plan = serializer.validated_data.get("subscription_plan")
            price = serializer.validated_data.get("subscription_price")

            ref = secrets.token_urlsafe(15)
            amount = int(float(price)) * 100  # Convert to Kobo
            redirect_url = request.build_absolute_uri(
                reverse('paystack-confirm-driver-sub', kwargs={"reference": ref})
            )

            metadata = dict(serializer.validated_data)
            metadata["password"] = data["password"]

            paystack_data = {
                "email": email,
                "amount": amount,
                "reference": ref,
                "metadata": metadata,
                "callback_url": redirect_url,
            }

            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            }

            paystack_url = "https://api.paystack.co/transaction/initialize"
            response = req.post(paystack_url, headers=headers, json=paystack_data)

            if response.status_code == 200:
                link = response.json()["data"]["authorization_url"]
                return Response({"checkout_url": link}, status=status.HTTP_200_OK)

            return Response({"error": "Could not initialize payment."}, status=response.status_code)

        else:
            return Response({"error": "Please select Driver or Client."}, status=400)

            
    def send_verification(self, user, request):
        verification = UserVerification(user=user)
        verification.generate_token()
        verification.save()
        
        user.is_active = False
        user.save()
        
        token = verification.token
        uidb64 = urlsafe_base64_encode(force_bytes(user.id))
        verification_link = request.build_absolute_uri(
            reverse('verify-email', kwargs={'uidb64': uidb64, 'token': token})
        )

        # Send the verification email with the token
        send_mail(
            "Your Verification Code",
            f"Use this code: {verification.token} (expires in 10 minutes)\n"
            f"Or click the link to verify your email: {verification_link} ",
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )




class PaystackDriverConfirmSubscriptionView(APIView):
    swagger_schema = TaggedAutoSchema

    def get(self, request, reference, *args, **kwargs):
        if not reference:
            return Response({"error": "Reference is required"}, status=400)

        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }

        response = req.get(url, headers=headers)
        data = response.json()

        if data['status'] and data['data']['status'] == 'success':
            metadata = data['data']['metadata']
            password = metadata.get("password")

            serializer = RegUserSerializer(data={**metadata, "password": password})
            serializer.is_valid(raise_exception=True)

            user = serializer.save(password=make_password(password))
            Subscription.objects.create(
                user=user,
                plan=metadata["subscription_plan"],
                price=metadata["subscription_price"]
            )
            
            Transaction.objects.create(
                user = user,
                ref= reference,
                amount = Decimal(metadata["subscription_price"]),
                description = f"payment of {metadata["subscription_plan"]} subscription registration",
                date = timezone.now()
            )

            # Send verification
            verification = UserVerification(user=user)
            verification.generate_token()
            verification.save()

            user.is_active = False
            user.save()
            
            token = verification.token
            uidb64 = urlsafe_base64_encode(force_bytes(user.id))
            verification_link = request.build_absolute_uri(
                reverse('verify-email', kwargs={'uidb64': uidb64, 'token': token})
            )

            # Send the verification email with the token
            send_mail(
                "Your Verification Code",
                f"Use this code: {verification.token} (expires in 10 minutes)\n"
                f"Or click the link to verify your email: {verification_link} ",
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False,
            )

            verification_link = f"http://127.0.0.1:5500/verify-token.html?message=1&email={user.email}"
            return HttpResponseRedirect(verification_link)

        return Response({"error": "Transaction verification failed."}, status=400)




User = get_user_model()



class VerifyEmailView(APIView):
    swagger_schema = TaggedAutoSchema
    def get(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = get_object_or_404(User, id=uid)
            verification = get_object_or_404(UserVerification, user=user, token=token)
            
            if verification.is_token_expired():
                    return Response({'error': 'Link has expired'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the user has already been verified
            if verification.is_verified:
                return Response({'error': 'Link is already verified'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Activate user
            user.is_active = True
            user.save()

            verification.is_verified = True
            verification.save()

            return Response({"message": "Your email has been verified successfully! please go back to login"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Invalid or expired link."}, status=status.HTTP_400_BAD_REQUEST)
        
        

class UserVerificationView(generics.GenericAPIView):
    swagger_schema = TaggedAutoSchema
    serializer_class = UserVerificationSerializer
    def post(self, request, *args, **kwargs):
        serializer = UserVerificationSerializer(data=request.data)

        if serializer.is_valid():
            token = serializer.validated_data['token']

            try:
                user_verification = UserVerification.objects.get(token=token)

                # Check if the token has expired
                if user_verification.is_token_expired():
                    return Response({'error': 'Token has expired'}, status=status.HTTP_400_BAD_REQUEST)

                # Check if the user has already been verified
                if user_verification.is_verified:
                    return Response({'error': 'User is already verified'}, status=status.HTTP_400_BAD_REQUEST)

                user = user_verification.user
                
                user.is_active = True
                user.save()

                user_verification.is_verified = True
                user_verification.save()
                
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                expiration_time = datetime.fromtimestamp(AccessToken(access_token)["exp"])
                profile_pic_url = request.build_absolute_uri(user.profile_picture.url) if user.profile_picture else None
                return Response(
                    {   "message":"your account has been verified",
                        "id": user.id,
                        "is_driver": user.is_driver,
                        "is_client": user.is_client,
                        "first_name":user.first_name,
                        "profile_pic":profile_pic_url,
                        "refresh": str(refresh),
                        "access": access_token,
                        "expiry": expiration_time,
                    },
                    status=status.HTTP_200_OK,
                )

            except UserVerification.DoesNotExist:
                return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({"error":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)




class ResendVerificationTokenView(generics.GenericAPIView):
    swagger_schema = TaggedAutoSchema
    serializer_class = ResendVerificationTokenSerializer
    def post(self, request, *args, **kwargs):
        serializer = ResendVerificationTokenSerializer(data=request.data)

        if serializer.is_valid():
            email = serializer.validated_data['email']
            if not email:
                return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                # Get the user by email
                user = User.objects.get(email=email)
                user_verification, created = UserVerification.objects.get_or_create(user=user)

                # If the user is already verified, inform the user
                if user.is_active:
                    return Response({"error": "User is already verified"}, status=status.HTTP_400_BAD_REQUEST)

                # If the token is expired or not verified, generate a new token
                if user_verification.is_token_expired() or user_verification.is_verified == False:
                    user_verification.generate_token()  # Regenerate token
                    user_verification.is_verified = False  # Reset verification status
                    user_verification.save()
                    
                    token = user_verification.token
                    uidb64 = urlsafe_base64_encode(force_bytes(user.id))
                    verification_link = request.build_absolute_uri(
                        reverse('verify-email', kwargs={'uidb64': uidb64, 'token': token})
                    )

                    # Send the token via email
                    send_mail(
                        "Your Verification Code",
                        f"Use this code: {user_verification.token} (expires in 10 minutes)\n"
                        f"Or click the link to verify your email: {verification_link} ",
                        settings.EMAIL_HOST_USER,
                        [user.email],
                        fail_silently=False,
                    )
                    
                    return Response({"message": "A new verification token has been sent to your email."}, status=status.HTTP_200_OK)
                
                return Response({"error": "Token is still valid. Please check your email for the verification."}, status=status.HTTP_400_BAD_REQUEST)
            
            except User.DoesNotExist:
                return Response({"error": "User with this email does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    



class LoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    swagger_schema = TaggedAutoSchema
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data.get("email")
        password = serializer.validated_data.get("password")
         
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(password):
            return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        if not user.is_active:
            return Response({"error": "Account is inactive"}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        expiration_time = datetime.fromtimestamp(AccessToken(access_token)["exp"])
        profile_pic_url = request.build_absolute_uri(user.profile_picture.url) if user.profile_picture else None
        return Response(
            {
                "id": user.id,
                "first_name":user.first_name,
                "is_driver": user.is_driver,
                "is_client": user.is_client,
                "profile_pic": profile_pic_url, 
                "refresh": str(refresh),
                "access": access_token,
                "expiry": expiration_time,
            },
            status=status.HTTP_200_OK,
        )
            


class ForgetPasswordView(generics.GenericAPIView):
    serializer_class = ForgetPasswordSerializer
    swagger_schema = TaggedAutoSchema
    def post(self, request, *args, **kwargs):
        serializer = ForgetPasswordSerializer(data=request.data)

        if serializer.is_valid():
            email = serializer.validated_data['email']
            if not email:
                return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                user = User.objects.get(email=email)
                user_verification, created = UserVerification.objects.get_or_create(user=user)

                # If the token is expired or not verified, generate a new token
                if user_verification.is_token_expired() or user_verification.is_verified == False:
                    user_verification.generate_token()
                    user_verification.is_verified = False 
                    user_verification.save()

                    # Send the token via email
                    send_mail(
                        'Your Verification Token',
                        f'Your verification token is {user_verification.token}, It expires in 10 minutes.',
                        settings.EMAIL_HOST_USER,
                        [user.email],
                        fail_silently=False,
                    )
                    
                    return Response({"message": "A verification token has been sent to your email."}, status=status.HTTP_200_OK)
                
                return Response({"error": "Token is still valid. Please check your email for the verification."}, status=status.HTTP_400_BAD_REQUEST)
            
            except User.DoesNotExist:
                return Response({"error": "User with this email does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    


class ForgetPasswordVerificationView(generics.GenericAPIView):
    serializer_class = ForgetPasswordVerificationTokenSerializer
    swagger_schema = TaggedAutoSchema
    def post(self, request, *args, **kwargs):
        
        serializer = ForgetPasswordVerificationTokenSerializer(data=request.data)

        if serializer.is_valid():
            token = serializer.validated_data['token']
            password = serializer.validated_data['password']
            
            if token == 6:
                return Response({'error': 'Token must be 6 numbers'}, status=status.HTTP_400_BAD_REQUEST)    

            try:
                user_verification = UserVerification.objects.get(token=token)

                # Check if the token has expired
                if user_verification.is_token_expired():
                    return Response({'error': 'Token has expired'}, status=status.HTTP_400_BAD_REQUEST)

                # Check if the user has already been verified
                if user_verification.is_verified:
                    return Response({'error': 'Token has been already verified'}, status=status.HTTP_400_BAD_REQUEST)

                user = user_verification.user
                user.password = make_password(password)
                user.save()
            
                user_verification.is_verified = True
                user_verification.save()
                
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                expiration_time = datetime.fromtimestamp(AccessToken(access_token)["exp"])
                profile_pic_url = request.build_absolute_uri(user.profile_picture.url) if user.profile_picture else None
                return Response(
                    {   "message":"Password has been changed successfully",
                        "id": user.id,
                        "is_driver": user.is_driver,
                        "is_client": user.is_client,
                        "first_name":user.first_name,
                        "profile_pic":profile_pic_url,
                        "refresh": str(refresh),
                        "access": access_token,
                        "expiry": expiration_time,
                    },
                    status=status.HTTP_200_OK,
                )

            except UserVerification.DoesNotExist:
                return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({"error":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)



class ChangePasswordView(generics.GenericAPIView):
    swagger_schema = TaggedAutoSchema
    serializer_class = ChangePasswordSerializer
    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            password = serializer.validated_data['password']
            password1 = serializer.validated_data['password1']
            password2 = serializer.validated_data['password2']
            
            if len(password) < 8 or len(password1) < 8 or len(password2) < 8:
                return Response({'error': 'Password must be at least 8 characters long.'}, status=status.HTTP_400_BAD_REQUEST)

            # Ensure new password matches confirmation
            if password1 != password2:
                return Response({'error': 'New password and confirm password do not match.'}, status=status.HTTP_400_BAD_REQUEST)
            
            user = request.user
            if not user.check_password(password):
                return Response({"error": "Old Password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

            user.password = make_password(password1)
            user.save()
                
            
            return Response({'message': 'Password Changed'}, status=status.HTTP_200_OK)
    
        return Response({"error":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)





# class LOGECPaystackCashDepositView(generics.GenericAPIView):
#     serializer_class = DepositSerializer
#     swagger_schema = TaggedAutoSchema
#     def post(self, request, *args, **kwargs):
#         serializer = self.serializer_class(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         title = serializer.validated_data.get('title')
#         name = serializer.validated_data.get('name')
#         amount = serializer.validated_data["amount"]
#         percentage = 1.5 / 100
#         additionalAmount = 100
#         modifiedAmount = (amount * percentage) + amount + additionalAmount
#         amount = int(modifiedAmount) * 100
#         ref = secrets.token_urlsafe(15)
#         if serializer.is_valid():
#             url="https://api.paystack.co/transaction/initialize"
#             headers = {
#                     'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
#                     'Content-Type': 'application/json',
#                 }
#             redirect_url = request.build_absolute_uri(reverse('paystack-confirm-deposit', kwargs={"reference":ref}))
#             data = { 
#             "email": "LOGEC@gmail.com", 
#             "amount": amount,
#             "reference":ref,
#             "metadata":{
#                 "name" : name,
#                 "title":title
#             },
#             "callback_url": redirect_url
#             }
#             print(data)
#             response = req.post(url, headers=headers, json=data)
#             if response.status_code == 200:
#                 response_data = response.json()
#                 return Response(
#                     {
#                         "link": response_data["data"]["authorization_url"],
#                     },
#                     status=response.status_code,
#                 )
#             else:
#                 return Response({"details":response.json()}, status=response.status_code)
#         else:
#                 return Response({"details":"Invalid Amount"}, status=response.status_code)




# class LOGECPaystackConfirmDepositView(APIView):
#     swagger_schema = TaggedAutoSchema
#     def get(self, request,reference, *args, **kwargs):
#         if not reference:
#             return Response({"error": "Transaction reference required."}, status=status.HTTP_400_BAD_REQUEST)
        
#         verification_url = f"https://api.paystack.co/transaction/verify/{reference}"
#         headers = {
#             "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
#         }
#         response = req.get(verification_url, headers=headers)
#         verification_data = response.json()
#         if verification_data['status'] == True and verification_data['data']['status'] == 'success':
#             amount = int(verification_data['data']['amount'])/100
#             title = verification_data['data']['metadata']['title']
#             name = verification_data['data']['metadata']['name']
#             ref = reference

#             try:
#                 offering = LOGECDonation.objects.create(
#                     amount = amount,
#                     title = title,
#                     name = name,
#                     ref = ref
#                 )
#                 return Response(status=status.HTTP_204_NO_CONTENT)
#             except:
#                 return Response({"error": "Payment successful, but can not complete request."}, status=status.HTTP_404_NOT_FOUND)
#         return Response({"error": "Transaction verification failed."}, status=status.HTTP_400_BAD_REQUEST)


