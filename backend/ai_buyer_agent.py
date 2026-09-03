#!/usr/bin/env python3
"""
Independent Outside AI Buyer Agent (Simulating an external autonomous agent)
Compliant with Google's Agent Payments Protocol (AP2) concepts:
- Discovers products across multi-merchant endpoints
- Evaluates goal constraints ("waterproof jacket under ₹2000")
- Compares Merchant A vs Merchant B offers
- Negotiates bounded discounts
- Constructs and signs an AP2 Buy Mandate
- Dispatches purchase order through Policy Gate and Razorpay Test API
- Verifies cryptographic receipt proof
"""

import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
import time
import json
import uuid
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
import httpx

BASE_URL = "http://127.0.0.1:8000/api"

# AP2 Buyer Signing Secret (simulating buyer client keypair / HMAC)
BUYER_SECRET_KEY = "ap2_autonomous_buyer_private_key_2026"

def print_banner():
    print("\n" + "=" * 80)
    print(" 🤖  INDEPENDENT AUTONOMOUS AI BUYER AGENT (AP2 PROTOCOL DEMO)")
    print("     Goal: Find a waterproof jacket under ₹2,000, negotiate best price & buy")
    print("=" * 80 + "\n")

def sign_ap2_mandate(payload: dict, secret: str) -> str:
    serialized = json.dumps(payload, sort_keys=True)
    return hmac.new(secret.encode("utf-8"), serialized.encode("utf-8"), hashlib.sha256).hexdigest()

def run_buyer_agent():
    print_banner()

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # Check backend health
    try:
        res = client.get("/health")
        if res.status_code != 200:
            print("❌ Backend is not running on http://127.0.0.1:8000. Please start the backend first!")
            return False
        print("✅ Connected to Agentic Commerce Backend API\n")
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("👉 Please start the FastAPI backend server first (python run_backend.py)")
        return False

    # Step 1: Multi-Merchant Catalog Discovery
    print("🔍 [STEP 1: DISCOVERY] Querying catalogs across both Merchant A and Merchant B...")
    time.sleep(1)

    # Search Merchant A (Apex Outfitters)
    res_a = client.get("/products/search", params={"query": "waterproof jacket", "merchant_id": "merchant_a"})
    products_a = res_a.json()

    # Search Merchant B (Urban Trail Co.)
    res_b = client.get("/products/search", params={"query": "waterproof jacket", "merchant_id": "merchant_b"})
    products_b = res_b.json()

    print(f"   • Merchant A (Apex Outfitters): Found {len(products_a)} matching items")
    for p in products_a:
        print(f"     - [{p['product_id']}] {p['name']} ({p['variant']}) | ₹{p['price']:,.2f} | Stock: {p['stock_count']}")

    print(f"   • Merchant B (Urban Trail Co.): Found {len(products_b)} matching items")
    for p in products_b:
        print(f"     - [{p['product_id']}] {p['name']} ({p['variant']}) | ₹{p['price']:,.2f} | Stock: {p['stock_count']}")

    # Step 2: Multi-Merchant Evaluation & Comparison
    print("\n⚖️  [STEP 2: AGENT EVALUATION & COMPARISON]")
    goal_max_price = 2000.0
    all_candidates = []

    for p in products_a:
        all_candidates.append({"merchant": "merchant_a", "product": p})
    for p in products_b:
        all_candidates.append({"merchant": "merchant_b", "product": p})

    # Filter by in-stock and price constraints
    qualified = [
        c for c in all_candidates
        if c["product"]["stock_count"] > 0 and c["product"]["price"] <= goal_max_price
    ]

    if not qualified:
        # If no product is directly <= 2000, check if negotiation could bring it down
        negotiable = [
            c for c in all_candidates
            if c["product"]["stock_count"] > 0 and (c["product"]["price"] * 0.85) <= goal_max_price
        ]
        if negotiable:
            chosen = min(negotiable, key=lambda x: x["product"]["price"])
            print(f"   ℹ️  No product directly under ₹{goal_max_price}. Selecting closest candidate for negotiation:")
            print(f"      Selected {chosen['product']['name']} from {chosen['merchant']} at ₹{chosen['product']['price']}")
        else:
            print("   ❌ No candidates meet the buyer's criteria.")
            return False
    else:
        # Select best priced option that meets goal
        chosen = min(qualified, key=lambda x: x["product"]["price"])

    selected_product = chosen["product"]
    selected_merchant = chosen["merchant"]

    print(f"   🏆 WINNER: '{selected_product['name']}' from '{selected_merchant.upper()}'")
    print(f"      Price: ₹{selected_product['price']:,.2f} (Under budget constraint of ₹{goal_max_price:,.2f})")
    print(f"      Inventory Status: {selected_product['stock_count']} units available (PASSED)")

    # Step 3: Bounded Negotiation (External Agent requests 10% promotional discount)
    print("\n💬 [STEP 3: BOUNDED NEGOTIATION]")
    requested_discount = 10.0
    print(f"   Agent requesting {requested_discount}% discount on {selected_product['product_id']}...")
    time.sleep(1)

    policy_payload = {
        "merchant_id": selected_merchant,
        "product_id": selected_product["product_id"],
        "quantity": 1,
        "requested_discount": requested_discount,
        "customer_id": "ai_buyer_agent_99"
    }
    policy_res = client.post("/policy/validate", json=policy_payload).json()

    final_unit_price = policy_res.get("final_unit_price", selected_product["price"])
    print(f"   ✅ Policy Gate Response: {policy_res.get('status')}")
    print(f"   🏷️  Catalog Price: ₹{policy_res.get('catalog_price'):,.2f}")
    print(f"   🎉 Final Negotiated Price: ₹{final_unit_price:,.2f} (Discount: {policy_res.get('discount_applied')}%)")

    # Step 4: Construct AP2 (Agent Payments Protocol) Buy Mandate
    print("\n📜 [STEP 4: AP2 MANDATE CREATION & CRYPTOGRAPHIC SIGNING]")
    mandate_id = f"mandate_{uuid.uuid4().hex[:12]}"
    expiry_time = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

    buyer_address = {
        "name": "Rahul Sharma",
        "street": "402, Green Glen Layout, Bellandur",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560103",
        "country": "India"
    }

    mandate_payload = {
        "mandate_id": mandate_id,
        "buyer_id": "cust_001",
        "merchant_id": selected_merchant,
        "product_id": selected_product["product_id"],
        "product_name": selected_product["name"],
        "variant": selected_product["variant"],
        "quantity": 1,
        "currency": "INR",
        "max_price_limit": goal_max_price,
        "agreed_unit_price": final_unit_price,
        "total_authorized_amount": final_unit_price,
        "shipping_address": buyer_address,
        "expiry_timestamp": expiry_time
    }

    # Generate cryptographic signature of mandate
    mandate_signature = sign_ap2_mandate(mandate_payload, BUYER_SECRET_KEY)
    mandate_payload["mandate_signature"] = mandate_signature

    print(f"   • Mandate ID: {mandate_id}")
    print(f"   • Protocol: AP2 (Agent Payments Protocol v1)")
    print(f"   • Max Price Ceiling Bound: ₹{goal_max_price:,.2f}")
    print(f"   • Authorized Amount: ₹{final_unit_price:,.2f}")
    print(f"   • Buyer Cryptographic Signature: {mandate_signature[:24]}...")

    # Step 5: Execute Purchase Mandate
    print("\n⚡ [STEP 5: DISPATCHING ORDER TO MERCHANT GATEWAY]")
    time.sleep(1)
    order_res = client.post("/orders/mandate", json=mandate_payload)

    if order_res.status_code != 200:
        print(f"   ❌ Order execution failed: {order_res.text}")
        return False

    order_data = order_res.json()
    if order_data.get("status") != "COMPLETED":
        print(f"   ❌ Order rejected by merchant: {order_data}")
        return False

    order_id = order_data["order_id"]
    receipt = order_data["verifiable_receipt"]
    rzp_order = order_data["razorpay_order"]

    print(f"   ✅ ORDER COMPLETED SUCCESSFULLY!")
    print(f"   📦 Merchant Order ID: {order_id}")
    print(f"   💳 Razorpay Test Order ID: {rzp_order.get('order_id')}")
    print(f"   🧾 Verifiable Receipt ID: {receipt.get('receipt_id')}")
    print(f"   🔐 Receipt Hash (SHA-256): {receipt.get('receipt_hash')}")
    print(f"   ✍️  Merchant HMAC Signature: {receipt.get('merchant_signature')[:24]}...")

    # Step 6: Verifiable Receipt Proof Verification
    print("\n🛡️  [STEP 6: VERIFYING RECEIPT CRYPTOGRAPHIC AUTHENTICITY]")
    time.sleep(1)
    verify_res = client.get(f"/verify/{order_id}").json()
    proof = verify_res.get("proof", {})

    if proof.get("verified"):
        print("   ✅ CRYPTOGRAPHIC PROOF VERIFIED!")
        print(f"   • Recomputed SHA-256 Hash matches stored hash: {proof.get('stored_hash') == proof.get('recomputed_hash')}")
        print(f"   • Merchant Signature Authenticated: {proof.get('signature_valid')}")
        print(f"   • Tamper Detected: {proof.get('tamper_detected')} (0% tampering)")
    else:
        print(f"   ❌ Verification failed: {proof}")
        return False

    print("\n" + "=" * 80)
    print(" 🎉  AUTONOMOUS TRANSACTION CYCLE COMPLETED WITH 100% SUCCESS!")
    print("     Zero human intervention required.")
    print("=" * 80 + "\n")
    return True

if __name__ == "__main__":
    success = run_buyer_agent()
    sys.exit(0 if success else 1)
