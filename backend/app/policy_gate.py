import logging
from typing import Dict, Any, Tuple, Optional
from app.db import get_product, SAVED_CUSTOMER_ADDRESSES
from app.config import MERCHANTS
from app.schemas import PolicyCheckRequest, PolicyCheckResponse, PolicyCheckItem, Address

logger = logging.getLogger("agentic_commerce.policy_gate")

def normalize_addr(addr: Address) -> str:
    return f"{addr.street.strip().lower()}, {addr.city.strip().lower()}, {addr.postal_code.strip()}"

async def run_policy_gate(req: PolicyCheckRequest) -> PolicyCheckResponse:
    """
    Executes the multi-tiered Policy Gate:
    1. Product & Price Validation (anti-tamper)
    2. Stock Availability Check
    3. Quantity Ceilings Check
    4. Saved Address Verification
    5. Order Value Cap Check
    6. Bounded Negotiation / Discount Evaluation
    """
    checks = []
    merchant_config = MERCHANTS.get(req.merchant_id.lower(), MERCHANTS["merchant_a"])
    policy = merchant_config["policy"]

    # 1. Product Existence & Catalog Price Integrity Check
    product = await get_product(req.merchant_id, req.product_id)
    if not product:
        checks.append(PolicyCheckItem(
            name="Product Existence",
            passed=False,
            detail=f"Product '{req.product_id}' does not exist in catalog for {req.merchant_id}."
        ))
        return PolicyCheckResponse(
            status="REJECTED",
            reason="product_not_found",
            catalog_price=0.0,
            final_unit_price=0.0,
            total_amount=0.0,
            checks=checks
        )

    catalog_price = float(product["price"])
    checks.append(PolicyCheckItem(
        name="Product & Catalog Price Check",
        passed=True,
        detail=f"Catalog record verified. Stored catalog price is ₹{catalog_price:,.2f}."
    ))

    # Anti-Tampering: If caller passed requested_price different from catalog price and no discount was approved
    if req.requested_price is not None and abs(req.requested_price - catalog_price) > 0.01 and not req.requested_discount:
        checks.append(PolicyCheckItem(
            name="Anti-Tamper Price Check",
            passed=False,
            detail=f"Caller sent untrusted price ₹{req.requested_price:,.2f}, which does not match catalog price ₹{catalog_price:,.2f}."
        ))
        # Note: We enforce the catalog price automatically, ensuring no LLM hallucinations compromise payments.
        logger.warning(f"Price tamper/hallucination detected: requested {req.requested_price}, overriding with {catalog_price}")

    # 2. Maximum Quantity Ceiling Check
    max_qty = policy.get("max_quantity_per_item", 5)
    if req.quantity <= 0:
        checks.append(PolicyCheckItem(
            name="Quantity Sanity Check",
            passed=False,
            detail=f"Requested quantity {req.quantity} is invalid."
        ))
        return PolicyCheckResponse(
            status="REJECTED",
            reason="invalid_quantity",
            catalog_price=catalog_price,
            final_unit_price=catalog_price,
            total_amount=0.0,
            checks=checks
        )

    if req.quantity > max_qty:
        checks.append(PolicyCheckItem(
            name="Quantity Limit Check",
            passed=False,
            detail=f"Requested quantity ({req.quantity}) exceeds merchant limit of {max_qty} units per transaction."
        ))
        return PolicyCheckResponse(
            status="REJECTED",
            reason="quantity_exceeds_limit",
            catalog_price=catalog_price,
            final_unit_price=catalog_price,
            total_amount=catalog_price * req.quantity,
            checks=checks
        )

    checks.append(PolicyCheckItem(
        name="Quantity Limit Check",
        passed=True,
        detail=f"Quantity {req.quantity} is within allowed ceiling of {max_qty} units."
    ))

    # 3. Stock Availability Check
    stock_count = int(product.get("stock_count", 0))
    if stock_count <= 0:
        checks.append(PolicyCheckItem(
            name="Stock Availability",
            passed=False,
            detail=f"Product '{product['name']}' ({product['variant']}) is completely OUT OF STOCK (stock = {stock_count})."
        ))
        return PolicyCheckResponse(
            status="REJECTED",
            reason="out_of_stock",
            catalog_price=catalog_price,
            final_unit_price=catalog_price,
            total_amount=catalog_price * req.quantity,
            checks=checks
        )

    if req.quantity > stock_count:
        checks.append(PolicyCheckItem(
            name="Stock Availability",
            passed=False,
            detail=f"Requested quantity {req.quantity} exceeds available inventory of {stock_count} units."
        ))
        return PolicyCheckResponse(
            status="REJECTED",
            reason="insufficient_stock",
            catalog_price=catalog_price,
            final_unit_price=catalog_price,
            total_amount=catalog_price * req.quantity,
            checks=checks
        )

    checks.append(PolicyCheckItem(
        name="Stock Availability",
        passed=True,
        detail=f"Sufficient stock available ({stock_count} units in inventory)."
    ))

    # 4. Saved Address Verification Check
    if req.shipping_address:
        saved_addresses = SAVED_CUSTOMER_ADDRESSES.get(req.customer_id, [])
        user_norm = normalize_addr(req.shipping_address)
        matched = False
        for saved in saved_addresses:
            saved_obj = Address(**saved)
            if normalize_addr(saved_obj) in user_norm or user_norm in normalize_addr(saved_obj):
                matched = True
                break

        if not matched:
            checks.append(PolicyCheckItem(
                name="Address Whitelist Check",
                passed=False,
                detail=f"Shipping destination '{req.shipping_address.street}, {req.shipping_address.city}' does not match any verified addresses on customer profile '{req.customer_id}'."
            ))
            return PolicyCheckResponse(
                status="REJECTED",
                reason="unrecognized_address",
                catalog_price=catalog_price,
                final_unit_price=catalog_price,
                total_amount=catalog_price * req.quantity,
                checks=checks
            )

        checks.append(PolicyCheckItem(
            name="Address Whitelist Check",
            passed=True,
            detail="Destination matched verified customer profile address."
        ))

    # 5. Bounded Negotiation / Discount Evaluation
    max_disc = policy.get("max_discount_percent", 15.0)
    applied_disc_percent = 0.0
    counter_offer = None

    if req.requested_discount and req.requested_discount > 0:
        if req.requested_discount <= max_disc:
            applied_disc_percent = req.requested_discount
            checks.append(PolicyCheckItem(
                name="Discount Negotiation Check",
                passed=True,
                detail=f"Requested discount of {req.requested_discount:.1f}% is approved (within merchant cap of {max_disc:.1f}%)."
            ))
        else:
            # Bounded negotiation counter-offer: Grant the maximum allowed policy discount
            applied_disc_percent = max_disc
            counter_offer = max_disc
            checks.append(PolicyCheckItem(
                name="Discount Negotiation Check",
                passed=True,
                detail=f"Requested discount {req.requested_discount:.1f}% exceeds merchant limit ({max_disc:.1f}%). Counter-offered maximum policy discount of {max_disc:.1f}%."
            ))
    else:
        checks.append(PolicyCheckItem(
            name="Discount Negotiation Check",
            passed=True,
            detail="Standard catalog pricing applied (no discount requested)."
        ))

    final_unit_price = round(catalog_price * (1.0 - (applied_disc_percent / 100.0)), 2)
    total_amount = round(final_unit_price * req.quantity, 2)

    # 6. Maximum Order Value Cap Check
    max_order_val = policy.get("max_order_value", 10000.0)
    if total_amount > max_order_val:
        checks.append(PolicyCheckItem(
            name="Max Order Value Ceiling",
            passed=False,
            detail=f"Total calculated order amount ₹{total_amount:,.2f} exceeds merchant threshold of ₹{max_order_val:,.2f}."
        ))
        return PolicyCheckResponse(
            status="REJECTED",
            reason="order_value_exceeds_limit",
            catalog_price=catalog_price,
            final_unit_price=final_unit_price,
            total_amount=total_amount,
            discount_applied=applied_disc_percent,
            counter_offer_discount=counter_offer,
            checks=checks
        )

    checks.append(PolicyCheckItem(
        name="Max Order Value Ceiling",
        passed=True,
        detail=f"Order total ₹{total_amount:,.2f} is within permitted limit of ₹{max_order_val:,.2f}."
    ))

    # All safety gates cleared!
    return PolicyCheckResponse(
        status="APPROVED",
        reason=None,
        catalog_price=catalog_price,
        final_unit_price=final_unit_price,
        total_amount=total_amount,
        discount_applied=applied_disc_percent,
        counter_offer_discount=counter_offer,
        checks=checks
    )
