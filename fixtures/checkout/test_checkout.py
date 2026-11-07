import unittest
from decimal import Decimal
from checkout import shipping_cost


class ShippingContract(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(shipping_cost("0.00"), Decimal("5.00"))

    def test_below_threshold(self):
        self.assertEqual(shipping_cost("99.99"), Decimal("5.00"))

    def test_exact_threshold(self):
        self.assertEqual(shipping_cost("100.00"), Decimal("0.00"))

    def test_above_threshold(self):
        self.assertEqual(shipping_cost("100.01"), Decimal("0.00"))

    def test_decimal_input(self):
        self.assertEqual(shipping_cost(Decimal("100")), Decimal("0.00"))

    def test_invalid_amounts(self):
        for value in ["-1", "NaN", "Infinity", "-Infinity"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                shipping_cost(value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
