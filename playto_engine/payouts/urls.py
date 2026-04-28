from django.urls import path
from .views import get_balance, create_payout

urlpatterns = [
    path("merchant/<int:merchant_id>/balance", get_balance),
    path("payouts", create_payout),
]