from django.urls import path, include
from .views import *

urlpatterns = [
    path(
        "driver/",
        include(
            [
                path("dashboard/", DashboardView.as_view()),
                path("update/availability/", UpdateAvailabilityView.as_view()),
                path("withdrawal/process/", WithdrawalProcessView.as_view()),
                path("id/verification/process/", IdVerificationView.as_view()),
                path('info/', GetAllUserInfoView.as_view()),
                path("ride/passenger/details/<str:request_ride_id>/", RidePassengerDetailAPIView.as_view()),
                path("earning/summary/", DriverEarningSummaryAPIView.as_view()),
                path('ride/requests/', RideRequestAPIView.as_view()),
            ]
        )
    ),
    path(
        "client/",
        include(
                [
                    path("dashboard/", ClientDashboardView.as_view()),
                    path("car-type/lists/", CarTypeListView.as_view()),
                    path('ride/requests/', RideRequestCreateView.as_view(), name='ride-request-create'),
                    # path("id/verification/process/", IdVerificationView.as_view()),
                    # path('info/', GetAllUserInfoView.as_view()),
                    # path("ride/passenger/details/<str:request_ride_id>/", RidePassengerDetailAPIView.as_view()),
                    # path("earning/summary/", DriverEarningSummaryAPIView.as_view()),
                    # path('ride/requests/', RideRequestAPIView.as_view()),
            ]
        )
    ),
]