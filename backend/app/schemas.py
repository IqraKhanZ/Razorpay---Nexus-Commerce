from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class Address(BaseModel):
    name: str = "Rahul Sharma"
    street: str = "402, Green Glen Layout, Bellandur"
    city: str = "Bengaluru"
    state: str = "Karnataka"
    postal_code: str = "560103"
    country: str = "India"

class Product(BaseModel):
    product_id: str
    name: str
    category: str
    variant: str = Field(description="Size, color, or variant specifier e.g., 'M', 'L', 'Black'")
    price: float
    stock_count: int
    description: str
    merchant_id: str = "merchant_a"
    currency: str = "INR"
    image_url: Optional[str] = None
    features: List[str] = []

class ProductSearchQuery(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    variant: Optional[str] = None
    merchant_id: Optional[str] = "merchant_a"
    max_price: Optional[float] = None

class PolicyCheckRequest(BaseModel):
    merchant_id: str = "merchant_a"
    product_id: str
    quantity: int = 1
    requested_price: Optional[float] = None
    requested_discount: Optional[float] = 0.0
    shipping_address: Optional[Address] = None
    customer_id: str = "cust_001"

class PolicyCheckItem(BaseModel):
    name: str
    passed: bool
    detail: str

class PolicyCheckResponse(BaseModel):
    status: str  # "APPROVED" | "REJECTED"
    reason: Optional[str] = None
    catalog_price: float
    final_unit_price: float
    total_amount: float
    discount_applied: float = 0.0
    counter_offer_discount: Optional[float] = None
    checks: List[PolicyCheckItem] = []

# AP2 (Agent Payments Protocol) Aligned Mandate Structure
class AP2BuyMandate(BaseModel):
    mandate_id: str
    buyer_id: str
    merchant_id: str
    product_id: str
    product_name: str
    variant: str
    quantity: int
    currency: str = "INR"
    max_price_limit: float
    agreed_unit_price: float
    total_authorized_amount: float
    shipping_address: Address
    mandate_signature: str  # HMAC or RSA signature of authorization payload
    expiry_timestamp: str

class VerifiableReceipt(BaseModel):
    receipt_id: str
    order_id: str
    product_id: str
    product_name: str
    merchant_id: str
    quantity: int
    unit_price: float
    discount_applied: float
    total_paid: float
    currency: str = "INR"
    customer_id: str
    shipping_address: Address
    timestamp: str
    payment_status: str
    razorpay_order_id: str
    razorpay_payment_id: Optional[str] = None
    receipt_hash: str  # SHA-256 of serialized core fields
    merchant_signature: str  # HMAC signature of receipt_hash

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_session"
    merchant_id: Optional[str] = "merchant_a"
    customer_id: Optional[str] = "cust_001"

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tool_invoked: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    product_preview: Optional[Product] = None
    policy_result: Optional[PolicyCheckResponse] = None
    order_mandate: Optional[AP2BuyMandate] = None
    receipt: Optional[VerifiableReceipt] = None
    needs_confirmation: bool = False

class AuditLogEntry(BaseModel):
    id: Optional[str] = None
    timestamp: str
    session_id: str
    actor: str  # "human_chat" | "outside_ai_buyer_agent"
    raw_input: str
    extracted_intent: Optional[Dict[str, Any]] = None
    catalog_lookup: Optional[Dict[str, Any]] = None
    policy_gate: Optional[Dict[str, Any]] = None
    negotiation: Optional[Dict[str, Any]] = None
    razorpay_action: Optional[Dict[str, Any]] = None
    verifiable_receipt: Optional[Dict[str, Any]] = None
    final_status: str
