import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from backend root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_placeholder_key").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "rzp_test_placeholder_secret").strip()
RECEIPT_SIGNING_KEY = os.getenv("RECEIPT_SIGNING_KEY", "secret_merchant_agent_hmac_signing_key_2026").strip()
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")

# Merchant Profiles for Multi-Merchant Interoperability
MERCHANTS = {
    "merchant_a": {
        "id": "merchant_a",
        "name": "Apex Outfitters (Merchant A)",
        "currency": "INR",
        "collection": "products_merchant_a",
        "description": "Premium Outdoor & Adventure Gear",
        "policy": {
            "max_order_value": 10000.0,
            "max_quantity_per_item": 5,
            "max_discount_percent": 15.0,
            "min_discount_percent": 5.0
        }
    },
    "merchant_b": {
        "id": "merchant_b",
        "name": "Urban Trail Co. (Merchant B)",
        "currency": "INR",
        "collection": "products_merchant_b",
        "description": "Urban Commute & All-Weather Apparel",
        "policy": {
            "max_order_value": 12000.0,
            "max_quantity_per_item": 5,
            "max_discount_percent": 18.0,
            "min_discount_percent": 5.0
        }
    }
}
