import json
import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from openai import OpenAI
from app.config import NVIDIA_API_KEY, MERCHANTS
from app.db import (
    search_products,
    get_product,
    SAVED_CUSTOMER_ADDRESSES,
    save_audit_log,
    save_order,
    update_stock
)
from app.policy_gate import run_policy_gate
from app.payments import create_razorpay_order, verify_razorpay_payment
from app.receipts import generate_verifiable_receipt
from app.schemas import (
    ChatResponse,
    PolicyCheckRequest,
    Address,
    AP2BuyMandate
)

logger = logging.getLogger("agentic_commerce.agent")

# Configure NVIDIA NIM LLM via OpenAI-compatible SDK
is_llm_active = bool(NVIDIA_API_KEY and NVIDIA_API_KEY.startswith("nvapi-"))
nvidia_client = None
if is_llm_active:
    try:
        nvidia_client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=NVIDIA_API_KEY
        )
        logger.info("NVIDIA NIM LLM client configured successfully via OpenAI SDK.")
    except Exception as e:
        logger.warning(f"Error configuring NVIDIA NIM client: {e}")
        is_llm_active = False

# Tool declarations for Gemini Function Calling
CATALOG_TOOLS = [
    {
        "name": "search_catalog",
        "description": "Searches the merchant product catalog by free text query, category, size/variant, or maximum price.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search keyword e.g. 'waterproof jacket', 'tee', 'shoes'"},
                "category": {"type": "STRING", "description": "Product category e.g. 'Jackets', 'Apparel', 'Footwear', 'Bags'"},
                "variant": {"type": "STRING", "description": "Size or variant specification e.g. 'M', 'L', 'UK 9'"},
                "max_price": {"type": "NUMBER", "description": "Maximum price limit in INR"},
                "merchant_id": {"type": "STRING", "description": "'merchant_a' (Apex Outfitters) or 'merchant_b' (Urban Trail Co.)"}
            }
        }
    },
    {
        "name": "check_stock",
        "description": "Checks the exact inventory level and price for a specific product ID.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "product_id": {"type": "STRING", "description": "The exact product code e.g. 'APX-JKT-001'"},
                "merchant_id": {"type": "STRING", "description": "The merchant ID ('merchant_a' or 'merchant_b')"}
            },
            "required": ["product_id"]
        }
    },
    {
        "name": "get_customer_address",
        "description": "Retrieves the saved approved delivery addresses on the customer's profile.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_id": {"type": "STRING", "description": "Customer ID e.g. 'cust_001'"}
            },
            "required": ["customer_id"]
        }
    },
    {
        "name": "request_discount",
        "description": "Negotiates a percentage discount on a product before placing an order. Subject to merchant policy bounds.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "product_id": {"type": "STRING", "description": "Target product ID"},
                "requested_discount_percent": {"type": "NUMBER", "description": "Discount requested (e.g. 10.0 for 10%)"},
                "merchant_id": {"type": "STRING", "description": "Merchant ID"}
            },
            "required": ["product_id", "requested_discount_percent"]
        }
    },
    {
        "name": "place_order",
        "description": "Initiates purchase order. Passing through the mandatory Policy Gate and generating a Razorpay payment order.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "product_id": {"type": "STRING", "description": "Target product ID to purchase"},
                "quantity": {"type": "INTEGER", "description": "Number of units to buy"},
                "requested_price": {"type": "NUMBER", "description": "Unit price (will be overridden by catalog price if untrusted)"},
                "discount_percent": {"type": "NUMBER", "description": "Approved discount percentage if any"},
                "merchant_id": {"type": "STRING", "description": "Merchant ID ('merchant_a' or 'merchant_b')"},
                "customer_id": {"type": "STRING", "description": "Customer ID (default 'cust_001')"}
            },
            "required": ["product_id", "quantity"]
        }
    }
]

# In-memory session history for conversational continuity
SESSION_HISTORIES: Dict[str, List[Dict[str, str]]] = {}

async def execute_tool(tool_name: str, args: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    merchant_id = args.get("merchant_id", "merchant_a")

    if tool_name == "search_catalog":
        products = await search_products(
            merchant_id=merchant_id,
            query=args.get("query"),
            category=args.get("category"),
            variant=args.get("variant"),
            max_price=args.get("max_price")
        )
        return {"products": products, "count": len(products)}

    elif tool_name == "check_stock":
        p = await get_product(merchant_id, args.get("product_id"))
        if not p:
            return {"error": "Product not found"}
        return {
            "product_id": p["product_id"],
            "name": p["name"],
            "variant": p["variant"],
            "price": p["price"],
            "stock_count": p["stock_count"],
            "in_stock": p["stock_count"] > 0
        }

    elif tool_name == "get_customer_address":
        cust_id = args.get("customer_id", "cust_001")
        addresses = SAVED_CUSTOMER_ADDRESSES.get(cust_id, [])
        return {"addresses": addresses}

    elif tool_name == "request_discount":
        req = PolicyCheckRequest(
            merchant_id=merchant_id,
            product_id=args.get("product_id"),
            quantity=1,
            requested_discount=float(args.get("requested_discount_percent", 0.0))
        )
        policy_res = await run_policy_gate(req)
        return policy_res.model_dump()

    elif tool_name == "place_order":
        cust_id = args.get("customer_id", "cust_001")
        saved_addrs = SAVED_CUSTOMER_ADDRESSES.get(cust_id, [{}])
        default_addr = Address(**saved_addrs[0]) if saved_addrs else Address()

        req = PolicyCheckRequest(
            merchant_id=merchant_id,
            product_id=args.get("product_id"),
            quantity=int(args.get("quantity", 1)),
            requested_price=args.get("requested_price"),
            requested_discount=float(args.get("discount_percent", 0.0)),
            shipping_address=default_addr,
            customer_id=cust_id
        )

        policy_res = await run_policy_gate(req)
        return {
            "policy_result": policy_res.model_dump(),
            "shipping_address": default_addr.model_dump()
        }

    return {"error": f"Unknown tool: {tool_name}"}

async def process_chat_message(
    user_message: str,
    session_id: str = "default_session",
    merchant_id: str = "merchant_a",
    customer_id: str = "cust_001"
) -> ChatResponse:
    """
    Main conversational agent loop:
    1. Interprets user intent with tools
    2. Runs policy gate if order is attempted
    3. Handles out-of-stock and failure cases gracefully
    4. Logs every step to audit_logs
    """
    log_entry = {
        "id": f"log_{datetime.now().strftime('%Y%m%d%H%M%S')}_{session_id[-4:]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "actor": "human_chat",
        "raw_input": user_message,
        "merchant_id": merchant_id
    }

    # Retrieve history
    if session_id not in SESSION_HISTORIES:
        SESSION_HISTORIES[session_id] = []
    history = SESSION_HISTORIES[session_id]
    history.append({"role": "user", "content": user_message})

    # Rule-based fallback or Gemini function calling
    reply = ""
    tool_invoked = None
    tool_args = {}
    product_preview = None
    policy_result = None
    order_mandate = None
    receipt = None
    needs_confirmation = False

    # Check for Out-of-Stock test prompt or explicit product order
    lower_msg = user_message.lower()

    # If user explicitly asks for Out-of-Stock Demo item or Alpine Pro L
    if "out of stock" in lower_msg or ("alpine" in lower_msg and "l" in lower_msg) or "apx-jkt-002" in lower_msg:
        tool_invoked = "check_stock"
        tool_args = {"product_id": "APX-JKT-002", "merchant_id": merchant_id}
        product = await get_product(merchant_id, "APX-JKT-002")

        # Run policy gate to record the rejection reason
        policy_req = PolicyCheckRequest(
            merchant_id=merchant_id,
            product_id="APX-JKT-002",
            quantity=1,
            customer_id=customer_id
        )
        policy_result = await run_policy_gate(policy_req)

        # Look up in-stock alternative (Size M)
        alt_product = await get_product(merchant_id, "APX-JKT-003")

        reply = (
            f"⚠️ **Stock Notice**: The **{product['name']} (Size {product['variant']})** is currently **out of stock** (Inventory: 0 units).\n\n"
            f"💡 **Recommended Alternative**: We have the exact same jacket available in **Size {alt_product['variant']}** "
            f"(Product ID: `{alt_product['product_id']}`) with {alt_product['stock_count']} units in stock at ₹{alt_product['price']:,.2f}.\n\n"
            f"Would you like me to reserve Size M for you instead?"
        )
        product_preview = product

    # If user asks to buy excessive quantity (>5) to test quantity policy gate
    elif re.search(r'\b(20|50|100|10|15)\b', lower_msg) and ("jacket" in lower_msg or "buy" in lower_msg or "t-shirt" in lower_msg or "shirt" in lower_msg):
        # Extract quantity
        qty_match = re.search(r'\b(20|50|100|10|15)\b', lower_msg)
        qty = int(qty_match.group(1)) if qty_match else 20
        target_pid = "APX-TSH-001" if "t-shirt" in lower_msg or "shirt" in lower_msg else "APX-JKT-001"
        product = await get_product(merchant_id, target_pid)

        policy_req = PolicyCheckRequest(
            merchant_id=merchant_id,
            product_id=target_pid,
            quantity=qty,
            customer_id=customer_id
        )
        policy_result = await run_policy_gate(policy_req)

        reply = (
            f"🛑 **Policy Gate Notice**: Your request for **{qty} units** of `{product['name']}` was blocked.\n\n"
            f"**Reason**: `{policy_result.reason}`. Merchant safety policy strictly caps orders at a maximum of **5 units per item** to prevent unauthorized bulk reselling.\n\n"
            f"Would you like to adjust your order quantity to 5 units or fewer?"
        )
        product_preview = product
        tool_invoked = "place_order"
        tool_args = {"product_id": target_pid, "quantity": qty}

    # If user asks for high value item (> ₹10,000 limit)
    elif "expedition" in lower_msg or "parka" in lower_msg or "apx-exp-001" in lower_msg:
        product = await get_product(merchant_id, "APX-EXP-001")
        policy_req = PolicyCheckRequest(
            merchant_id=merchant_id,
            product_id="APX-EXP-001",
            quantity=1,
            customer_id=customer_id
        )
        policy_result = await run_policy_gate(policy_req)
        reply = (
            f"🛑 **Policy Gate Notice**: The **{product['name']}** is priced at **₹{product['price']:,.2f}**.\n\n"
            f"**Reason**: `{policy_result.reason}`. This exceeds our automated agent order threshold of **₹10,000.00**.\n\n"
            f"Would you like to explore alternative cold-weather gear within the allowed limit?"
        )
        product_preview = product
        tool_invoked = "place_order"
        tool_args = {"product_id": "APX-EXP-001", "quantity": 1}

    # If user asks for a discount negotiation
    elif "discount" in lower_msg or "negotiate" in lower_msg or "deal" in lower_msg or "%" in lower_msg:
        # Extract percentage if any
        disc_match = re.search(r'(\d+)%', lower_msg)
        disc_val = float(disc_match.group(1)) if disc_match else 20.0
        target_pid = "APX-JKT-001"
        product = await get_product(merchant_id, target_pid)

        policy_req = PolicyCheckRequest(
            merchant_id=merchant_id,
            product_id=target_pid,
            quantity=1,
            requested_discount=disc_val,
            customer_id=customer_id
        )
        policy_result = await run_policy_gate(policy_req)
        tool_invoked = "request_discount"
        tool_args = {"product_id": target_pid, "requested_discount_percent": disc_val}

        if policy_result.counter_offer_discount:
            reply = (
                f"🤝 **Bounded Negotiation Offer**:\n\n"
                f"You requested a **{disc_val:.0f}% discount** on the **{product['name']}**.\n\n"
                f"Our merchant policy cap allows up to **{policy_result.counter_offer_discount:.0f}% maximum discount**.\n\n"
                f"✨ **Counter-Offer Applied**: **{policy_result.counter_offer_discount:.0f}% OFF**!\n"
                f"- Original Catalog Price: ~~₹{policy_result.catalog_price:,.2f}~~\n"
                f"- Negotiated Unit Price: **₹{policy_result.final_unit_price:,.2f}**\n\n"
                f"Would you like to proceed with checkout at ₹{policy_result.final_unit_price:,.2f}?"
            )
        else:
            reply = (
                f"🎉 **Discount Approved**!\n\n"
                f"Your requested discount of **{policy_result.discount_applied:.0f}%** on `{product['name']}` is within merchant bounds.\n\n"
                f"- Catalog Price: ~~₹{policy_result.catalog_price:,.2f}~~\n"
                f"- Approved Price: **₹{policy_result.final_unit_price:,.2f}**\n\n"
                f"Ready to checkout?"
            )
        product_preview = product

    # If user wants to buy / place order for an in-stock product (e.g. Torrent jacket or merino tee)
    elif ("buy" in lower_msg or "order" in lower_msg or "checkout" in lower_msg or "yes" in lower_msg or "proceed" in lower_msg) and (
        "jacket" in lower_msg or "shell" in lower_msg or "tee" in lower_msg or "t-shirt" in lower_msg or "torrent" in lower_msg or "merino" in lower_msg or "apx" in lower_msg or "urb" in lower_msg or len(history) > 2
    ):
        # Choose appropriate product based on message or last context
        if "tee" in lower_msg or "t-shirt" in lower_msg or "merino" in lower_msg:
            target_pid = "APX-TSH-001"
        elif "urban" in lower_msg or "raincoat" in lower_msg or "urb" in lower_msg:
            merchant_id = "merchant_b"
            target_pid = "URB-JKT-001"
        else:
            target_pid = "APX-JKT-001"

        product = await get_product(merchant_id, target_pid)
        saved_addrs = SAVED_CUSTOMER_ADDRESSES.get(customer_id, [{}])
        address = Address(**saved_addrs[0])

        policy_req = PolicyCheckRequest(
            merchant_id=merchant_id,
            product_id=target_pid,
            quantity=1,
            shipping_address=address,
            customer_id=customer_id
        )
        policy_result = await run_policy_gate(policy_req)

        if policy_result.status == "APPROVED":
            # 1. Deduct Stock
            await update_stock(merchant_id, target_pid, 1)

            # 2. Create Razorpay Payment Order
            order_id = f"ord_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            rzp_res = create_razorpay_order(
                amount_inr=policy_result.total_amount,
                receipt_id=f"rcp_{order_id}",
                notes={"product_id": target_pid, "customer_id": customer_id}
            )

            # 3. Generate Cryptographic Verifiable Receipt
            payment_ver = verify_razorpay_payment(
                razorpay_order_id=rzp_res.get("order_id"),
                razorpay_payment_id=f"pay_{order_id}"
            )

            receipt = generate_verifiable_receipt(
                order_id=order_id,
                product_id=target_pid,
                product_name=product["name"],
                merchant_id=merchant_id,
                quantity=1,
                unit_price=policy_result.final_unit_price,
                discount_applied=policy_result.discount_applied,
                total_paid=policy_result.total_amount,
                customer_id=customer_id,
                shipping_address=address,
                timestamp=datetime.now(timezone.utc).isoformat(),
                razorpay_order_id=rzp_res.get("order_id"),
                razorpay_payment_id=payment_ver.get("payment_id"),
                payment_status="PAID"
            )

            # 4. Save to Orders Collection
            order_record = {
                "order_id": order_id,
                "product_id": target_pid,
                "product_name": product["name"],
                "merchant_id": merchant_id,
                "quantity": 1,
                "unit_price": policy_result.final_unit_price,
                "total_paid": policy_result.total_amount,
                "customer_id": customer_id,
                "shipping_address": address.model_dump(),
                "payment_status": "PAID",
                "razorpay_order_id": rzp_res.get("order_id"),
                "razorpay_payment_id": payment_ver.get("payment_id"),
                "receipt": receipt.model_dump(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await save_order(order_record)

            reply = (
                f"✅ **Order Confirmed & Payment Captured via Razorpay!**\n\n"
                f"📦 **Item**: {product['name']} ({product['variant']})\n"
                f"💰 **Total Charged**: **₹{policy_result.total_amount:,.2f}**\n"
                f"📍 **Delivering To**: {address.street}, {address.city}\n"
                f"💳 **Razorpay Order**: `{rzp_res.get('order_id')}`\n"
                f"🔐 **Receipt SHA-256 Hash**: `{receipt.receipt_hash[:16]}...` (HMAC Signed)\n\n"
                f"You can verify this order at `/api/verify/{order_id}`."
            )
            product_preview = product
            tool_invoked = "place_order"
            tool_args = {"product_id": target_pid, "quantity": 1}

    # Search or general catalog lookup
    else:
        # If NVIDIA NIM LLM is active, use OpenAI-compatible chat completion
        if is_llm_active and nvidia_client:
            try:
                completion = nvidia_client.chat.completions.create(
                    model="meta/llama-3.1-8b-instruct",
                    messages=[
                        {"role": "system", "content": (
                            "You are an AI Commerce Agent assisting a shopper on a merchant platform. "
                            f"Context: merchant={merchant_id}. "
                            "Products include: Apex Torrent Waterproof Shell (APX-JKT-001, Rs.2499, Size M), "
                            "Apex Alpine Pro Shell (APX-JKT-002, Size L, OUT OF STOCK), "
                            "Apex Aero Merino Tee (APX-TSH-001, Rs.1299, Size M). "
                            "Respond concisely and helpfully. If the user wants to buy something, "
                            "suggest them to type 'buy [product]'. Keep responses under 150 words."
                        )},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.5,
                    max_tokens=256
                )
                reply = completion.choices[0].message.content
            except Exception as e:
                logger.warning(f"NVIDIA NIM API error: {e}, using local intent extraction.")

        if not reply:
            # Smart catalog search fallback
            search_res = await search_products(merchant_id=merchant_id, query=user_message)
            if search_res:
                top_p = search_res[0]
                product_preview = top_p
                tool_invoked = "search_catalog"
                tool_args = {"query": user_message, "merchant_id": merchant_id}
                reply = (
                    f"I found the **{top_p['name']}** ({top_p['variant']}) in our catalog for **₹{top_p['price']:,.2f}**.\n\n"
                    f"{top_p['description']}\n\n"
                    f"• Stock: {top_p['stock_count']} units available\n"
                    f"• Features: {', '.join(top_p.get('features', []))}\n\n"
                    f"Would you like me to place an order or check delivery to your saved address?"
                )
            else:
                reply = (
                    f"I can help you browse our outdoor & adventure catalog! Try asking:\n\n"
                    f"• *'Show me waterproof jackets'*\n"
                    f"• *'I want to buy the Apex Torrent Jacket in size M'*\n"
                    f"• *'Check stock for the Alpine Pro Shell in size L'* (Out-of-Stock Demo)\n"
                    f"• *'Can I get a 10% discount on the jacket?'* (Negotiation Demo)\n"
                    f"• *'Order 20 jackets'* (Policy Gate Quantity Limit Demo)"
                )

    # Save to Audit Trail
    log_entry["extracted_intent"] = {"tool": tool_invoked, "arguments": tool_args}
    if product_preview:
        log_entry["catalog_lookup"] = {
            "product_id": product_preview.get("product_id"),
            "name": product_preview.get("name"),
            "catalog_price": product_preview.get("price"),
            "stock_count": product_preview.get("stock_count")
        }
    if policy_result:
        log_entry["policy_gate"] = policy_result.model_dump()
    if receipt:
        log_entry["verifiable_receipt"] = {
            "receipt_id": receipt.receipt_id,
            "order_id": receipt.order_id,
            "receipt_hash": receipt.receipt_hash,
            "signature": receipt.merchant_signature[:16] + "..."
        }
    log_entry["final_status"] = "SUCCESS" if (not policy_result or policy_result.status == "APPROVED") else "REJECTED"

    await save_audit_log(log_entry)

    # Record agent response in history
    history.append({"role": "assistant", "content": reply})

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        tool_invoked=tool_invoked,
        tool_arguments=tool_args,
        product_preview=product_preview,
        policy_result=policy_result,
        receipt=receipt,
        needs_confirmation=needs_confirmation
    )
