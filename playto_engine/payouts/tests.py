from django.test import TransactionTestCase
from rest_framework.test import APIClient
from payouts.models import Merchant, LedgerEntry
import threading

# Create your tests here.
class BaseTestCase(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()

        # Create merchant
        self.merchant = Merchant.objects.create(name="Test Merchant")

        # Add balance
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100000,
            entry_type="credit"
        )


class IdempotencyTest(BaseTestCase):

    def test_same_key_returns_same_response(self):
        headers = {"HTTP_IDEMPOTENCY_KEY": "test-key-123"}

        data = {
            "amount_paise": 10000,
            "bank_account_id": 1
        }

        # First request
        response1 = self.client.post(
            "/api/v1/payouts",
            data,
            format="json",
            **headers
        )

        # Second request (same key)
        response2 = self.client.post(
            "/api/v1/payouts",
            data,
            format="json",
            **headers
        )

        # ✅ Should return same response
        self.assertEqual(response1.data, response2.data)


class ConcurrencyTest(BaseTestCase):

    def test_concurrent_requests(self):

        data = {
            "amount_paise": 80000,
            "bank_account_id": 1
        }

        results = []

        def make_request(key):
            response = self.client.post(
                "/api/v1/payouts",
                data,
                format="json",
                HTTP_IDEMPOTENCY_KEY=key
            )
            results.append(response.status_code)

        # Create two parallel requests with DIFFERENT keys
        t1 = threading.Thread(target=make_request, args=("key1",))
        t2 = threading.Thread(target=make_request, args=("key2",))

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # ✅ Only one should succeed
        self.assertIn(201, results)
        self.assertIn(400, results)