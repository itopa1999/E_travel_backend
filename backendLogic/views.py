from decimal import Decimal
import secrets
from django.shortcuts import render
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings


from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.parsers import MultiPartParser, FormParser


from backend.permissions import IsClientPermission, IsDriverPermission
from backendLogic.serializers import DashboardActiveRideListSerializer, DashboardRatingListSerializer, IdVerificationSerializer, WithdrawalSerializer
from .models import DriverReview, RidePassenger, Transaction



# Create your views here.

class DashboardView(APIView):
    permission_classes = [IsAuthenticated, IsDriverPermission]
    def get(self, request, *args, **kwargs):
        user = self.request.user
        summary = Transaction.get_earnings(user)
        ride_summary = RidePassenger.get_passenger_status_summary(user)
        avg_rating = DriverReview.get_average_rating(user)
        
        active_rides = RidePassenger.objects.filter(ride__user = user, is_completed=False)[:5]
        serialize_active_rides = DashboardActiveRideListSerializer(active_rides, many = True).data
        
        ratings = DriverReview.objects.filter(driver = user)[:5]
        serialize_ratings = DashboardRatingListSerializer(ratings, many = True).data
        
        availability = user.is_available
        
        
        response = {
            "ride_summary" : ride_summary,
            "trans_summary" : summary,
            "average_rating": avg_rating,
            "active_rides" : serialize_active_rides,
            "ratings" : serialize_ratings,
            "wallet_balance" : user.wallet.balance,
            "isIdVerified" : user.identityinfo.is_verified,
            "availability" : availability
            
        }
        return Response(response, status=status.HTTP_200_OK)
    



class UpdateAvailabilityView(APIView):
    permission_classes = [IsAuthenticated, IsDriverPermission]
    def post(self, request, *args, **kwargs):
        user = request.user
        user.is_available = not user.is_available
        user.save()
        return Response({"is_available": user.is_available}, status=status.HTTP_200_OK)
    
    
class WithdrawalProcessView(generics.GenericAPIView):
    serializer_class = WithdrawalSerializer
    permission_classes = [IsAuthenticated, IsDriverPermission]
    def post(self, request, *args, **kwargs):
        serializer = WithdrawalSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            bank = serializer.validated_data['bank']
            account_number = serializer.validated_data['accountNumber']

            # Process withdrawal
            user = request.user

            dummy_account_name = "John salawu" 
            full_name = f"{user.first_name} {user.last_name}".lower()

            if not any(name.lower() in dummy_account_name.lower() for name in full_name.split()):
                return Response({
                    "detail": "Account name doesn't match your profile name. Please use a valid bank account."
                }, status=status.HTTP_400_BAD_REQUEST)

            # Deduct balance
            user.wallet.balance -= amount
            user.wallet.save()

            # Create transaction
            Transaction.objects.create(
                user=user,
                ref=secrets.token_urlsafe(15),
                tran_type="debit",
                amount=amount,
                description="withdrawal",
                date=timezone.now()
            )

            # Notify user (agent) via email
            send_mail(
                subject="💸 Withdrawal Request Processed",
                message=(
                    f"Hi {user.first_name},\n\n"
                    f"Your withdrawal request of ₦{amount} to {bank} ({account_number}) has been submitted successfully.\n"
                    f"It may take up to 24 hours to reflect in your bank account.\n\n"
                    f"Thanks for using TravelHub!"
                ),
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                fail_silently=False,
            )

            return Response({"detail": "Withdrawal request submitted successfully."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    
class IdVerificationView(generics.GenericAPIView):
    serializer_class = IdVerificationSerializer
    permission_classes = [IsAuthenticated, IsDriverPermission]
    parser_classes = [MultiPartParser, FormParser]  # Add this line

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            result = serializer.save()
            
            send_mail(
            subject="🔍 ID Verification Under Review",
            message=(
                f"Hi {request.user.first_name},\n\n"
                f"Your ID verification request is currently under review.\n"
                f"Our team will provide feedback once the review process is complete.\n\n"
                f"Thank you for your patience and for using TravelHub!\n\n"
                f"Best regards,\n"
                f"The TravelHub Team"
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[request.user.email],
            fail_silently=False,
        )
            
            return Response({'detail': 'ID verification submitted successfully.', 'data': result})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)