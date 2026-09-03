import asyncio
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
from app.db import init_db, get_product, search_products
from app.policy_gate import run_policy_gate
from app.schemas import PolicyCheckRequest, Address
from app.payments import create_razorpay_order, verify_razorpay_payment
from app.receipts import generate_verifiable_receipt, verify_order_receipt

async def run_tests():
    print("=== Testing Database Initialization & Catalog ===")
    await init_db()

    # Test product lookup
    p_a = await get_product("merchant_a", "APX-JKT-001")
    assert p_a is not None, "Failed to get APX-JKT-001"
    print(f"✅ Merchant A product found: {p_a['name']} (Price: ₹{p_a['price']})")

    p_b = await get_product("merchant_b", "URB-JKT-001")
    assert p_b is not None, "Failed to get URB-JKT-001"
    print(f"✅ Merchant B product found: {p_b['name']} (Price: ₹{p_b['price']})")

    # Test search
    search_res = await search_products(query="waterproof", max_price=3000)
    print(f"✅ Search found {len(search_res)} waterproof items under ₹3000")
    assert len(search_res) >= 2, "Expected at least 2 items"

    print("\n=== Testing Policy Gate (Safety Layer) ===")

    # 1. Normal Valid Order
    valid_addr = Address()
    req_valid = PolicyCheckRequest(
        merchant_id="merchant_a",
        product_id="APX-JKT-001",
        quantity=1,
        shipping_address=valid_addr,
        customer_id="cust_001"
    )
    res_valid = await run_policy_gate(req_valid)
    assert res_valid.status == "APPROVED", f"Expected APPROVED, got {res_valid.status}"
    print("✅ Valid Order: APPROVED")

    # 2. Out of Stock Rejection (APX-JKT-002)
    req_oos = PolicyCheckRequest(
        merchant_id="merchant_a",
        product_id="APX-JKT-002",
        quantity=1,
        customer_id="cust_001"
    )
    res_oos = await run_policy_gate(req_oos)
    assert res_oos.status == "REJECTED" and res_oos.reason == "out_of_stock", f"Expected out_of_stock, got {res_oos}"
    print(f"✅ Out of Stock Check: REJECTED with reason '{res_oos.reason}'")

    # 3. Quantity Ceiling Rejection (>5 units)
    req_qty = PolicyCheckRequest(
        merchant_id="merchant_a",
        product_id="APX-JKT-001",
        quantity=20,
        customer_id="cust_001"
    )
    res_qty = await run_policy_gate(req_qty)
    assert res_qty.status == "REJECTED" and res_qty.reason == "quantity_exceeds_limit"
    print(f"✅ Quantity Ceiling (>5) Check: REJECTED with reason '{res_qty.reason}'")

    # 4. Max Order Value Ceiling (>10,000 INR)
    req_val = PolicyCheckRequest(
        merchant_id="merchant_a",
        product_id="APX-EXP-001",
        quantity=1,
        customer_id="cust_001"
    )
    res_val = await run_policy_gate(req_val)
    assert res_val.status == "REJECTED" and res_val.reason == "order_value_exceeds_limit"
    print(f"✅ Order Value Cap (>₹10k) Check: REJECTED with reason '{res_val.reason}'")

    # 5. Bounded Negotiation (Requested 20%, max allowed 15%)
    req_disc = PolicyCheckRequest(
        merchant_id="merchant_a",
        product_id="APX-JKT-001",
        quantity=1,
        requested_discount=20.0,
        customer_id="cust_001"
    )
    res_disc = await run_policy_gate(req_disc)
    assert res_disc.status == "APPROVED" and res_disc.counter_offer_discount == 15.0
    print(f"✅ Bounded Negotiation: Requested 20%, Counter-offered policy cap {res_disc.counter_offer_discount}%")

    # 6. Unrecognized Address Rejection
    fake_addr = Address(street="Unknown Alien Base 99", city="Mars City", postal_code="000000")
    req_addr = PolicyCheckRequest(
        merchant_id="merchant_a",
        product_id="APX-JKT-001",
        quantity=1,
        shipping_address=fake_addr,
        customer_id="cust_001"
    )
    res_addr = await run_policy_gate(req_addr)
    assert res_addr.status == "REJECTED" and res_addr.reason == "unrecognized_address"
    print(f"✅ Unrecognized Address Check: REJECTED with reason '{res_addr.reason}'")

    print("\n=== Testing Razorpay Payments & Verifiable Receipts ===")
    rzp_res = create_razorpay_order(amount_inr=2499.0, receipt_id="rcp_test_001")
    assert rzp_res["success"] is True
    print(f"✅ Razorpay Order Created: {rzp_res['order_id']}")

    rzp_ver = verify_razorpay_payment(rzp_res["order_id"], "pay_test_001")
    assert rzp_ver["verified"] is True
    print(f"✅ Razorpay Payment Verified: {rzp_ver['payment_id']}")

    receipt = generate_verifiable_receipt(
        order_id="ord_test_001",
        product_id="APX-JKT-001",
        product_name="Apex Torrent Shell",
        merchant_id="merchant_a",
        quantity=1,
        unit_price=2499.0,
        discount_applied=0.0,
        total_paid=2499.0,
        customer_id="cust_001",
        shipping_address=valid_addr,
        timestamp="2026-09-02T12:00:00Z",
        razorpay_order_id=rzp_res["order_id"],
        razorpay_payment_id=rzp_ver["payment_id"]
    )
    print(f"✅ Verifiable Receipt Generated: SHA-256={receipt.receipt_hash[:16]}...")

    # Verify receipt proof
    order_record = {
        "order_id": "ord_test_001",
        "product_id": "APX-JKT-001",
        "merchant_id": "merchant_a",
        "quantity": 1,
        "unit_price": 2499.0,
        "total_paid": 2499.0,
        "customer_id": "cust_001",
        "payment_status": "PAID",
        "razorpay_order_id": rzp_res["order_id"],
        "receipt": receipt.model_dump()
    }
    proof = verify_order_receipt(order_record)
    assert proof["verified"] is True
    assert proof["tamper_detected"] is False
    print("✅ Receipt Cryptographic Verification: AUTHENTIC (0% tampering)")

    # Tamper test: modify total_paid and verify tamper is detected!
    tampered_record = dict(order_record)
    tampered_record["total_paid"] = 99.0  # maliciously modified
    tamper_proof = verify_order_receipt(tampered_record)
    assert tamper_proof["verified"] is False
    assert tamper_proof["tamper_detected"] is True
    print("✅ Tamper Detection Test: Successfully caught unauthorized price modification!")

    print("\n🎉 ALL BACKEND UNIT & POLICY GATE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(run_tests())
