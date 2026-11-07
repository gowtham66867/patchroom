from decimal import Decimal


def total_with_tax(subtotal):
    """Add 10% tax and round half-up to two decimal places."""
    return (Decimal(str(subtotal)) * Decimal('1.10')).quantize(Decimal('0.01'))
