import asyncio
import unittest
from decimal import Decimal

from starter import recommend_price


class RecommendPriceTests(unittest.IsolatedAsyncioTestCase):
    async def test_calculates_price_from_eligible_offers(self):
        async def fetch_offers():
            return {
                "status": "success",
                "offers": [
                    {"seller": "OTHER", "price": Decimal("4850.00"), "delivery_days": 0},
                    {"seller": "PARTS", "price": Decimal("4800.03"), "delivery_days": 6},
                    {"seller": "MyShop", "price": Decimal("4300.00"), "delivery_days": 2},
                    {"seller": "SLOW", "price": Decimal("4700.00"), "delivery_days": 7},
                    {"seller": "UNKNOWN", "price": Decimal("4600.00"), "delivery_days": None},
                ],
            }

        result = await recommend_price(fetch_offers, Decimal("4900.00"), Decimal("4500.00"))

        self.assertIsInstance(result["price"], Decimal)
        self.assertEqual(result["price"], Decimal("4728.02"))
        self.assertEqual(result["decision"], "APPLY")
        self.assertTrue(result["reason"])

    async def test_holds_current_price_below_minimum_on_partial_result(self):
        async def fetch_offers():
            return {
                "status": "partial",
                "offers": [
                    {"seller": "PARTS", "price": Decimal("4800.00"), "delivery_days": 3},
                ],
            }

        current_price = Decimal("4400.00")
        result = await recommend_price(fetch_offers, current_price, Decimal("4500.00"))

        self.assertIsInstance(result["price"], Decimal)
        self.assertEqual(result["price"], current_price)
        self.assertEqual(result["decision"], "HOLD")
        self.assertTrue(result["reason"])

    async def test_holds_without_waiting_for_late_success(self):
        release_response = asyncio.Event()
        response_returned = asyncio.Event()

        async def fetch_offers():
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                await release_response.wait()
                response_returned.set()
                return {
                    "status": "success",
                    "offers": [
                        {"seller": "PARTS", "price": Decimal("4800.00"), "delivery_days": 3},
                    ],
                }

        current_price = Decimal("4900.00")
        recommendation = asyncio.create_task(
            recommend_price(fetch_offers, current_price, Decimal("4500.00"), timeout_s=0.01)
        )
        try:
            done, _ = await asyncio.wait((recommendation,), timeout=1)
            self.assertIn(recommendation, done, "Рекомендация ждёт запоздалый ответ")
            result = recommendation.result()
        finally:
            release_response.set()

        await asyncio.wait_for(response_returned.wait(), timeout=1)
        self.assertEqual(result["price"], current_price)
        self.assertEqual(result["decision"], "HOLD")
        self.assertTrue(result["reason"])
