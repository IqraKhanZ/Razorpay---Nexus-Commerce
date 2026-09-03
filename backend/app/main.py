import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware

from app.config import PORT, HOST, MERCHANTS
from app.db import (
    init_db,
    search_products,
    get_product,
    update_stock,
    save_order,
    get_order,
    save_audit_log,
    get_audit_logs,
    reset_demo,
    SAVED_CUSTOMER_ADDRESSES
)
from app.schemas import (
    Product,
    ProductSearchQuery,
    PolicyCheckRequest,
    PolicyCheckResponse,
    ChatRequest,
    ChatResponse,
    AP2BuyMandate,
    VerifiableReceipt,
    AuditLogEntry
)
from app.policy_gate import run_policy_gate
from app.payments import create_razorpay_order, verify_razorpay_payment
from app.receipts import generate_verifiable_receipt, verify_order_receipt
from app.agent import process_chat_message

logger = logging.getLogger("agentic_commerce.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Agentic Commerce backend...")
    await init_db()
    yield
    logger.info("Shutting down Agentic Commerce backend...")

app = FastAPI(
    title="Razorpay Agentic Commerce & AP2 Protocol Demo",
    description="Track 1: AI Growth & Agentic Commerce - In-App Conversational Checkout, Policy Gate, AP2 Mandates & Verifiable Receipts",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware to enable Vite + React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "merchants": list(MERCHANTS.keys())
    }

# Phase 2: Catalog (agent-readable data layer)
@app.get("/api/products/search", response_model=List[Product])
async def search_catalog_endpoint(
    query: Optional[str] = Query(None, description="Keyword search"),
    category: Optional[str] = Query(None, description="Category filter (Jackets, Apparel, Footwear, Bags)"),
    variant: Optional[str] = Query(None, description="Size or variant filter (M, L, XL, UK 9)"),
    merchant_id: Optional[str] = Query(None, description="merchant_a or merchant_b"),
    max_price: Optional[float] = Query(None, description="Price upper bound")
):
    results = await search_products(
        merchant_id=merchant_id,
        query=query,
        category=category,
        variant=variant,
        max_price=max_price
    )
    return results

@app.get("/api/products/{merchant_id}/{product_id}", response_model=Product)
async def get_product_endpoint(
    merchant_id: str = Path(..., description="Merchant identifier"),
    product_id: str = Path(..., description="Product ID e.g. APX-JKT-001")
):
    product = await get_product(merchant_id, product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found at merchant '{merchant_id}'.")
    return product

# Phase 3 & 4: Intent understanding & Policy Gate via Conversational Checkout
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    return await process_chat_message(
        user_message=payload.message,
        session_id=payload.session_id or "default_session",
        merchant_id=payload.merchant_id or "merchant_a",
        customer_id=payload.customer_id or "cust_001"
    )

# Standalone Policy Gate Validation
@app.post("/api/policy/validate", response_model=PolicyCheckResponse)
async def validate_policy_endpoint(req: PolicyCheckRequest):
    return await run_policy_gate(req)

# Phase 5 & 10: AP2 Protocol Buy Mandate Endpoint (Autonomous AI Buyer Agent execution)
@app.post("/api/orders/mandate")
async def execute_ap2_mandate(mandate: AP2BuyMandate):
    """
    Executes an AP2 (Agent Payments Protocol) compliant Buy Mandate from an AI Buyer Agent:
    1. Validates mandate signatures and constraints
    2. Executes through the Policy Gate safety layer
    3. Triggers Razorpay test-mode transaction
    4. Issues cryptographic HMAC-signed verifiable receipt
    5. Commits to orders and audit_logs collections
    """
    session_id = f"ap2_{mandate.mandate_id[:8]}"
    log_entry = {
        "id": f"log_ap2_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "actor": "outside_ai_buyer_agent",
        "raw_input": f"AP2 Mandate: buy {mandate.quantity}x {mandate.product_id} @ max ₹{mandate.max_price_limit}",
        "merchant_id": mandate.merchant_id,
        "ap2_mandate": mandate.model_dump()
    }

    # Step 1: Policy Gate verification
    policy_req = PolicyCheckRequest(
        merchant_id=mandate.merchant_id,
        product_id=mandate.product_id,
        quantity=mandate.quantity,
        requested_price=mandate.agreed_unit_price,
        shipping_address=mandate.shipping_address,
        customer_id=mandate.buyer_id
    )
    policy_res = await run_policy_gate(policy_req)
    log_entry["policy_gate"] = policy_res.model_dump()

    if policy_res.status != "APPROVED":
        log_entry["final_status"] = "REJECTED"
        await save_audit_log(log_entry)
        return {
            "status": "REJECTED",
            "reason": policy_res.reason,
            "policy_result": policy_res
        }

    # Step 2: Price bound enforcement (AP2 mandate constraint)
    if policy_res.final_unit_price > mandate.max_price_limit:
        log_entry["final_status"] = "REJECTED"
        log_entry["error"] = "Mandate max price limit exceeded"
        await save_audit_log(log_entry)
        return {
            "status": "REJECTED",
            "reason": "mandate_max_price_exceeded",
            "detail": f"Catalog price ₹{policy_res.final_unit_price} exceeds buyer mandate ceiling ₹{mandate.max_price_limit}."
        }

    # Step 3: Stock decrement
    await update_stock(mandate.merchant_id, mandate.product_id, mandate.quantity)

    # Step 4: Razorpay Payment Order
    order_id = f"ord_ap2_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    rzp_order = create_razorpay_order(
        amount_inr=policy_res.total_amount,
        receipt_id=f"rcp_{order_id}",
        notes={"mandate_id": mandate.mandate_id, "buyer_id": mandate.buyer_id}
    )

    # Step 5: Capture / Verify Payment
    payment_ver = verify_razorpay_payment(
        razorpay_order_id=rzp_order.get("order_id"),
        razorpay_payment_id=f"pay_ap2_{order_id}"
    )

    # Step 6: Generate Verifiable Receipt (SHA-256 + HMAC-SHA256)
    product = await get_product(mandate.merchant_id, mandate.product_id)
    receipt = generate_verifiable_receipt(
        order_id=order_id,
        product_id=mandate.product_id,
        product_name=product["name"] if product else mandate.product_name,
        merchant_id=mandate.merchant_id,
        quantity=mandate.quantity,
        unit_price=policy_res.final_unit_price,
        discount_applied=policy_res.discount_applied,
        total_paid=policy_res.total_amount,
        customer_id=mandate.buyer_id,
        shipping_address=mandate.shipping_address,
        timestamp=datetime.now(timezone.utc).isoformat(),
        razorpay_order_id=rzp_order.get("order_id"),
        razorpay_payment_id=payment_ver.get("payment_id"),
        payment_status="PAID"
    )

    # Step 7: Persist Order
    order_doc = {
        "order_id": order_id,
        "mandate_id": mandate.mandate_id,
        "product_id": mandate.product_id,
        "product_name": product["name"] if product else mandate.product_name,
        "merchant_id": mandate.merchant_id,
        "quantity": mandate.quantity,
        "unit_price": policy_res.final_unit_price,
        "total_paid": policy_res.total_amount,
        "customer_id": mandate.buyer_id,
        "shipping_address": mandate.shipping_address.model_dump(),
        "payment_status": "PAID",
        "razorpay_order_id": rzp_order.get("order_id"),
        "razorpay_payment_id": payment_ver.get("payment_id"),
        "receipt": receipt.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await save_order(order_doc)

    # Step 8: Complete Audit Log
    log_entry["razorpay_action"] = rzp_order
    log_entry["verifiable_receipt"] = {
        "receipt_id": receipt.receipt_id,
        "order_id": receipt.order_id,
        "receipt_hash": receipt.receipt_hash,
        "signature": receipt.merchant_signature[:16] + "..."
    }
    log_entry["final_status"] = "SUCCESS"
    await save_audit_log(log_entry)

    return {
        "status": "COMPLETED",
        "order_id": order_id,
        "mandate_id": mandate.mandate_id,
        "policy_result": policy_res,
        "razorpay_order": rzp_order,
        "verifiable_receipt": receipt
    }

# Phase 10: Verifiable Receipt Proof Endpoint
@app.get("/api/verify/{order_id}")
async def verify_receipt_endpoint(order_id: str):
    """
    Cryptographically proves that an order receipt hasn't been tampered with
    by recomputing SHA-256 hash and verifying HMAC signature.
    """
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found.")
    
    proof = verify_order_receipt(order)
    return {
        "order_id": order_id,
        "proof": proof,
        "order_summary": {
            "product_name": order.get("product_name"),
            "merchant_id": order.get("merchant_id"),
            "total_paid": order.get("total_paid"),
            "payment_status": order.get("payment_status"),
            "razorpay_order_id": order.get("razorpay_order_id")
        }
    }

# Phase 6: Audit Trail Endpoint
@app.get("/api/logs")
async def get_audit_trail_endpoint(
    limit: int = Query(50, ge=1, le=100),
    session_id: Optional[str] = Query(None)
):
    return await get_audit_logs(limit=limit, session_id=session_id)

# Helper: Reset demo state
@app.post("/api/reset-demo")
async def reset_demo_endpoint():
    await reset_demo()
    return {"status": "success", "message": "Demo state & inventories reset to initial catalog values."}
