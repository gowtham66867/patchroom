import unittest
from decimal import Decimal
from tax import total_with_tax


class TaxContract(unittest.TestCase):
    def test_round_half_up(self):
        self.assertEqual(total_with_tax('0.15'), Decimal('0.17'))

    def test_whole_amount(self):
        self.assertEqual(total_with_tax('10'), Decimal('11.00'))

    def test_zero(self):
        self.assertEqual(total_with_tax('0'), Decimal('0.00'))
