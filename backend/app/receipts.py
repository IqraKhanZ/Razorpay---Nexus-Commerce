import hashlib
import hmac
import json
from typing import Dict, Any, Tuple
from app.config import RECEIPT_SIGNING_KEY
from app.schemas import VerifiableReceipt, Address

def serialize_receipt_payload(payload: Dict[str, Any]) -> str:
    """
    Standardizes canonical serialization of key receipt fields so hashing is deterministic.
    """
    canonical_dict = {
        "order_id": str(payload.get("order_id", "")),
        "product_id": str(payload.get("product_id", "")),
        "merchant_id": str(payload.get("merchant_id", "")),
        "quantity": int(payload.get("quantity", 1)),
        "unit_price": f"{float(payload.get('unit_price', 0.0)):.2f}",
        "total_paid": f"{float(payload.get('total_paid', 0.0)):.2f}",
        "customer_id": str(payload.get("customer_id", "")),
        "payment_status": str(payload.get("payment_status", "")),
        "razorpay_order_id": str(payload.get("razorpay_order_id", "")),
        "timestamp": str(payload.get("timestamp", ""))
    }
    return json.dumps(canonical_dict, sort_keys=True)

def generate_verifiable_receipt(
    order_id: str,
    product_id: str,
    product_name: str,
    merchant_id: str,
    quantity: int,
    unit_price: float,
    discount_applied: float,
    total_paid: float,
    customer_id: str,
    shipping_address: Address,
    timestamp: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    payment_status: str = "PAID"
) -> VerifiableReceipt:
    payload_data = {
        "order_id": order_id,
        "product_id": product_id,
        "merchant_id": merchant_id,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_paid": total_paid,
        "customer_id": customer_id,
        "payment_status": payment_status,
        "razorpay_order_id": razorpay_order_id,
        "timestamp": timestamp
    }

    canonical_str = serialize_receipt_payload(payload_data)
    receipt_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    signature = hmac.new(
        RECEIPT_SIGNING_KEY.encode("utf-8"),
        receipt_hash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return VerifiableReceipt(
        receipt_id=f"RCP-{order_id}",
        order_id=order_id,
        product_id=product_id,
        product_name=product_name,
        merchant_id=merchant_id,
        quantity=quantity,
        unit_price=unit_price,
        discount_applied=discount_applied,
        total_paid=total_paid,
        currency="INR",
        customer_id=customer_id,
        shipping_address=shipping_address,
        timestamp=timestamp,
        payment_status=payment_status,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        receipt_hash=receipt_hash,
        merchant_signature=signature
    )

def verify_order_receipt(order_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recomputes the cryptographic hash from current record fields and verifies HMAC signature.
    Detects if any field (like price, status, or quantity) was tampered with in storage.
    """
    receipt_data = order_record.get("receipt", {})
    stored_hash = receipt_data.get("receipt_hash")
    stored_sig = receipt_data.get("merchant_signature")

    if not stored_hash or not stored_sig:
        return {
            "verified": False,
            "error": "No cryptographic receipt found on order record.",
            "tamper_detected": True
        }

    canonical_str = serialize_receipt_payload({
        "order_id": order_record.get("order_id"),
        "product_id": order_record.get("product_id"),
        "merchant_id": order_record.get("merchant_id"),
        "quantity": order_record.get("quantity"),
        "unit_price": order_record.get("unit_price"),
        "total_paid": order_record.get("total_paid"),
        "customer_id": order_record.get("customer_id"),
        "payment_status": order_record.get("payment_status"),
        "razorpay_order_id": order_record.get("razorpay_order_id"),
        "timestamp": receipt_data.get("timestamp")
    })

    recomputed_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    expected_sig = hmac.new(
        RECEIPT_SIGNING_KEY.encode("utf-8"),
        recomputed_hash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    hash_matches = (recomputed_hash == stored_hash)
    sig_matches = hmac.compare_digest(expected_sig, stored_sig)

    return {
        "verified": hash_matches and sig_matches,
        "order_id": order_record.get("order_id"),
        "stored_hash": stored_hash,
        "recomputed_hash": recomputed_hash,
        "signature_valid": sig_matches,
        "tamper_detected": not (hash_matches and sig_matches),
        "algorithm": "HMAC-SHA256",
        "verified_at": receipt_data.get("timestamp")
    }
