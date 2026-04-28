from django.urls import path
from .views import get_balance

urlpatterns = [
    path("merchant/<int:merchant_id>/balance", get_balance),
]