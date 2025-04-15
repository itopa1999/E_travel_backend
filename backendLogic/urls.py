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
                
            ]
        )
    ),
]