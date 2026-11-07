# PatchRoom review: live-dev-001 / p001

Status: awaiting_human_review

Report (untrusted input):

Automated development report: an order of exactly $100 is incorrectly charged $5 shipping. Expected: free shipping at $100 or more.

Explanation: Root cause: strict > excludes exactly $100. Change > to >= so shipping is free at the inclusive $100 threshold, consistent with the report and protected contract.

Baseline: assertion failure reproduced. Candidate: configured checks pass.

Source SHA-256: `aee43e9c3ba5c5e0d00cbe2a7c7e9674ddb110d397d58badedcdf25c74992bdb`

Contract SHA-256: `a6e7cdc43bc12fee240658a04292976ecbacf9bcfe8c52c382e428f30851f8a7`

```diff
--- a/checkout.py
+++ b/checkout.py
@@ -6,4 +6,4 @@
     amount = Decimal(str(subtotal))
     if not amount.is_finite() or amount < 0:
         raise ValueError("subtotal must be finite and nonnegative")
-    return Decimal("0.00") if amount > Decimal("100.00") else Decimal("5.00")
+    return Decimal("0.00") if amount >= Decimal("100.00") else Decimal("5.00")
```

## Verification output

```text
test_above_threshold (test_checkout.ShippingContract) ... ok
test_below_threshold (test_checkout.ShippingContract) ... ok
test_decimal_input (test_checkout.ShippingContract) ... ok
test_exact_threshold (test_checkout.ShippingContract) ... ok
test_invalid_amounts (test_checkout.ShippingContract) ... ok
test_zero (test_checkout.ShippingContract) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.000s

OK
```

Tests establish configured behavior only. No merge or deployment is performed.
Human review must refer to this proposal and full source hash.
