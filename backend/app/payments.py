import logging
import uuid
from typing import Dict, Any, Optional
import razorpay
from app.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

logger = logging.getLogger("agentic_commerce.payments")

is_live_razorpay = (
    bool(RAZORPAY_KEY_ID) and
    not RAZORPAY_KEY_ID.startswith("rzp_test_placeholder") and
    bool(RAZORPAY_KEY_SECRET) and
    not RAZORPAY_KEY_SECRET.startswith("rzp_test_placeholder")
)

client = None
if is_live_razorpay:
    try:
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        logger.info("Razorpay client initialized with live test credentials.")
    except Exception as e:
        logger.warning(f"Failed to initialize Razorpay client: {e}. Falling back to simulation mode.")
        is_live_razorpay = False
else:
    logger.info("Razorpay running in local test simulation mode (using official format order IDs).")

def create_razorpay_order(
    amount_inr: float,
    receipt_id: str,
    currency: str = "INR",
    notes: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Creates a Razorpay order with amount in paise (1 INR = 100 paise).
    """
    amount_in_paise = int(round(amount_inr * 100))

    if is_live_razorpay and client:
        try:
            order_payload = {
                "amount": amount_in_paise,
                "currency": currency,
                "receipt": receipt_id,
                "notes": notes or {}
            }
            rzp_order = client.order.create(data=order_payload)
            logger.info(f"Razorpay live test order created: {rzp_order.get('id')}")
            return {
                "success": True,
                "order_id": rzp_order.get("id"),
                "amount": rzp_order.get("amount"),
                "currency": rzp_order.get("currency"),
                "status": rzp_order.get("status"),
                "raw": rzp_order
            }
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "reason": "razorpay_gateway_error"
            }

    # High-fidelity Razorpay Order Simulation for Hackathon Sandbox Testing
    simulated_order_id = f"order_{uuid.uuid4().hex[:14]}"
    return {
        "success": True,
        "order_id": simulated_order_id,
        "amount": amount_in_paise,
        "currency": currency,
        "status": "created",
        "key_id": RAZORPAY_KEY_ID,
        "simulated": True,
        "notes": notes or {}
    }

def verify_razorpay_payment(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates Razorpay payment signature.
    Also handles payment failure test cases (e.g. simulated card decline).
    """
    # Check for intentional failure test flag in payment ID
    if "fail" in razorpay_payment_id.lower() or "decline" in razorpay_payment_id.lower():
        logger.warning(f"Payment declined intentionally for test case: {razorpay_payment_id}")
        return {
            "verified": False,
            "status": "FAILED",
            "reason": "payment_declined_by_bank",
            "detail": "Customer payment method declined due to insufficient funds or security policy."
        }

    if is_live_razorpay and client and razorpay_signature:
        try:
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            client.utility.verify_payment_signature(params_dict)
            return {
                "verified": True,
                "status": "PAID",
                "payment_id": razorpay_payment_id,
                "order_id": razorpay_order_id
            }
        except Exception as e:
            logger.error(f"Razorpay payment verification failed: {e}")
            return {
                "verified": False,
                "status": "FAILED",
                "reason": "signature_mismatch",
                "detail": str(e)
            }

    # Simulation validation
    return {
        "verified": True,
        "status": "PAID",
        "payment_id": razorpay_payment_id or f"pay_{uuid.uuid4().hex[:14]}",
        "order_id": razorpay_order_id,
        "simulated": True
    }
