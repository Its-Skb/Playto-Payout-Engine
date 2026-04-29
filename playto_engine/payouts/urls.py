from django.urls import path
from .views import get_balance, create_payout
from django.http import JsonResponse

def home(request):
    return JsonResponse({"message": "API is running"})

urlpatterns = [
    path("", home),
    path("merchant/<int:merchant_id>/balance", get_balance),
    path("payouts", create_payout),
]