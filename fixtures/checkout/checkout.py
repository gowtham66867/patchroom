from decimal import Decimal


def shipping_cost(subtotal):
    """Shipping is free on orders of $100 or more; otherwise $5."""
    amount = Decimal(str(subtotal))
    if not amount.is_finite() or amount < 0:
        raise ValueError("subtotal must be finite and nonnegative")
    return Decimal("0.00") if amount > Decimal("100.00") else Decimal("5.00")
