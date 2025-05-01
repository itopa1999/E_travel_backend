from rest_framework import serializers
from rest_framework.exceptions import ParseError

from administrator.models import IdentityInfo, User
from backendLogic.models import DriverReview, Ride, RidePassenger, RideRequest, Transaction, VehicleInfo


class DashboardRatingListSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = DriverReview
        fields = ['rating', 'comment']
        
        
        

class DashboardActiveRideListSerializer(serializers.ModelSerializer):
    departure = serializers.CharField(source="ride.departure", read_only = True)
    destination = serializers.CharField(source="ride.destination", read_only = True)
    price = serializers.CharField(source="ride.price_per_seat", read_only = True)
    class Meta:
        model = RidePassenger
        fields = ['id','departure', 'destination', 'price']
        
        

class WithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required = True)
    bank = serializers.CharField(max_length=100, required = True)
    accountNumber = serializers.IntegerField(required = True)
    
    def validate_amount(self, value):
        user = self.context['request'].user
        if value > user.wallet.balance:
            raise serializers.ValidationError(f"Insufficient balance. You have only ₦{user.wallet.balance}")
        return value
    
    

class IdVerificationSerializer(serializers.Serializer):
    ID_no = serializers.CharField()
    departure = serializers.CharField()
    destination = serializers.CharField()
    date_of_departure = serializers.DateTimeField()
    seating_capacity = serializers.IntegerField()
    price_per_seat = serializers.DecimalField(max_digits=10, decimal_places=2)
    plate_no = serializers.CharField()
    vehicle_name = serializers.CharField()
    vehicle_color = serializers.CharField()
    vehicle_type = serializers.CharField()
    
    # File fields
    driver_licenses = serializers.FileField()
    selfie = serializers.FileField()
    
    
    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        
        print(validated_data)

        # Extract identity data
        selfie = validated_data.pop('selfie')
        driver_licenses = validated_data.pop('driver_licenses')
        ID_no = validated_data.pop('ID_no')

        # Extract ride data
        departure = validated_data.pop('departure')
        destination = validated_data.pop('destination')
        date_of_departure = validated_data.pop('date_of_departure')
        price_per_seat = validated_data.pop('price_per_seat')

        # Extract vehicle data
        seating_capacity = validated_data.pop('seating_capacity')
        plate_no = validated_data.pop('plate_no')
        vehicle_name = validated_data.pop('vehicle_name')
        vehicle_color = validated_data.pop('vehicle_color')
        vehicle_type = validated_data.pop('vehicle_type')

        # Get or create IdentityInfo
        identity, created_identity = IdentityInfo.objects.get_or_create(
            user=user,
            defaults={
                'selfie': selfie,
                'driver_licenses': driver_licenses,
                'ID_no': ID_no
            }
        )
        
        # If the identity info was not created, it means it already exists, so we update it
        if not created_identity:
            identity.selfie = selfie
            identity.driver_licenses = driver_licenses
            identity.ID_no = ID_no
            
            identity.is_verified = False
            identity.save()

        # Get or create Ride
        ride, created_ride = Ride.objects.get_or_create(
            user=user,
            departure=departure,
            destination=destination,
            date_of_departure=date_of_departure,
            defaults={
                'price_per_seat': price_per_seat,
            }
        )
        
        # If the ride was not created, we update the ride fields
        if not created_ride:
            ride.departure = departure
            ride.destination = destination
            ride.date_of_departure = date_of_departure
            ride.price_per_seat = price_per_seat
            ride.save()

        # Get or create VehicleInfo
        vehicle, created_vehicle = VehicleInfo.objects.get_or_create(
            ride=ride,
            defaults={
                'vehicle_name': vehicle_name,
                'vehicle_type': vehicle_type,
                'seating_capacity': seating_capacity,
                'plate_no': plate_no,
                'vehicle_color': vehicle_color
            }
        )

        # If the vehicle info was not created, we update the vehicle fields
        if not created_vehicle:
            vehicle.vehicle_name = vehicle_name
            vehicle.vehicle_type = vehicle_type
            vehicle.seating_capacity = seating_capacity
            vehicle.plate_no = plate_no
            vehicle.vehicle_color = vehicle_color
            vehicle.save()

        return {
            'identity': identity.id,
            'ride': ride.id,
            'vehicle': vehicle.id
        }
        
        
        
class IdentityInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdentityInfo
        fields = ['id', 'ID_no', 'selfie', 'driver_licenses', 'is_verified']
        
    def get_selfie(self, obj):
        request = self.context.get('request')
        if obj.selfie and request:
            return request.build_absolute_uri(obj.selfie.url)
        return None

    def get_driver_licenses(self, obj):
        request = self.context.get('request')
        if obj.driver_licenses and request:
            return request.build_absolute_uri(obj.driver_licenses.url)
        return None

class RideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = ['id', 'departure', 'destination', 'date_of_departure', 'price_per_seat']

class VehicleInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleInfo
        fields = ['id', 'vehicle_name', 'vehicle_type', 'seating_capacity', 'plate_no', 'vehicle_color', 'ride']
        
        

class RidePassengerDetailsSerializer(serializers.ModelSerializer):
    is_actionable = serializers.SerializerMethodField()
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    profile_picture = serializers.SerializerMethodField()
    phone = serializers.CharField(source="user.phone", default=None)
    email = serializers.EmailField(source="user.email")

    class Meta:
        model = RidePassenger
        fields = [
            "id","first_name", "last_name", "phone", "email",
            "special_request", "seat_taken", "has_paid", "profile_picture",
            "is_completed", "payment_method", "status",
            "is_actionable",
        ]
        
    def get_is_actionable(self, obj):
        return obj.status in (
            RidePassenger.Status.PENDING,
            RidePassenger.Status.ONGOING
        )
        
    def get_profile_picture(self, obj):
        request = self.context.get("request")
        profile_pic = obj.user.profile_picture
        if profile_pic and hasattr(profile_pic, "url"):
            return request.build_absolute_uri(profile_pic.url)
        return None
        
        
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'description', 'tran_type', 'ref', 'date']
        
        
class UserSerializer(serializers.ModelSerializer):
    profile_picture = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'profile_picture']
        
    def get_profile_picture(self, obj):
        request = self.context.get("request")
        profile_pic = obj.profile_picture
        if profile_pic and hasattr(profile_pic, "url"):
            return request.build_absolute_uri(profile_pic.url)
        return None
        
        
class RideRequestSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = RideRequest
        fields = [
            'id',
            'user',
            'departure',
            'destination',
            'date_of_departure',
            'budget_price',
            'special_request',
            'payment_method',
        ]
        read_only_fields = ['user']