import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import motor.motor_asyncio
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from app.config import MONGODB_URI

logger = logging.getLogger("agentic_commerce.db")
logging.basicConfig(level=logging.INFO)

# Initial Seed Data for Merchant A (Apex Outfitters)
INITIAL_PRODUCTS_MERCHANT_A = [
    {
        "product_id": "APX-JKT-001",
        "name": "Apex Torrent Waterproof Shell",
        "category": "Jackets",
        "variant": "M",
        "price": 2499.0,
        "stock_count": 8,
        "description": "3-layer breathable waterproof hiking jacket with sealed seams and storm hood.",
        "merchant_id": "merchant_a",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1548883354-7622d03aca27?w=500&q=80",
        "features": ["Waterproof 20,000mm", "Underarm Vents", "YKK Aquaguard Zippers"]
    },
    {
        "product_id": "APX-JKT-002",
        "name": "Apex Alpine Pro Shell (Out-of-Stock Demo)",
        "category": "Jackets",
        "variant": "L",
        "price": 3299.0,
        "stock_count": 0,  # INTENTIONALLY 0 FOR FAILURE DEMO
        "description": "Ultralight GORE-TEX alpine storm jacket for extreme weather.",
        "merchant_id": "merchant_a",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&q=80",
        "features": ["GORE-TEX Pro", "Helmet Compatible", "Zero Stock Demo Item"]
    },
    {
        "product_id": "APX-JKT-003",
        "name": "Apex Alpine Pro Shell",
        "category": "Jackets",
        "variant": "M",
        "price": 3299.0,
        "stock_count": 4,
        "description": "Ultralight GORE-TEX alpine storm jacket for extreme weather in Size M.",
        "merchant_id": "merchant_a",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&q=80",
        "features": ["GORE-TEX Pro", "Available in M", "In Stock Alternative"]
    },
    {
        "product_id": "APX-TSH-001",
        "name": "Apex Aero Merino Wool Tee",
        "category": "Apparel",
        "variant": "M",
        "price": 1299.0,
        "stock_count": 15,
        "description": "100% natural Merino wool anti-odor active tee for trekking and daily commute.",
        "merchant_id": "merchant_a",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500&q=80",
        "features": ["Odor Resistant", "Moisture Wicking", "Temperature Regulating"]
    },
    {
        "product_id": "APX-TSH-002",
        "name": "Apex Aero Merino Wool Tee",
        "category": "Apparel",
        "variant": "L",
        "price": 1299.0,
        "stock_count": 6,
        "description": "100% natural Merino wool anti-odor active tee in Size L.",
        "merchant_id": "merchant_a",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500&q=80",
        "features": ["Odor Resistant", "Size L", "Moisture Wicking"]
    },
    {
        "product_id": "APX-SHO-001",
        "name": "Apex TerraGrip Trail Runners",
        "category": "Footwear",
        "variant": "UK 9",
        "price": 4499.0,
        "stock_count": 5,
        "description": "Vibram outsole trail running shoes with rock plate and reinforced toe cap.",
        "merchant_id": "merchant_a",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&q=80",
        "features": ["Vibram Megagrip", "Quick-lace System", "Breathable Mesh"]
    },
    {
        "product_id": "APX-BAG-001",
        "name": "Apex Summit 35L Daypack",
        "category": "Bags",
        "variant": "35L",
        "price": 2899.0,
        "stock_count": 7,
        "description": "Ergonomic technical daypack with hydration bladder compartment and rain cover.",
        "merchant_id": "merchant_a",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&q=80",
        "features": ["Hydration Compatible", "Built-in Rain Cover", "Air-mesh Backpanel"]
    },
    {
        "product_id": "APX-EXP-001",
        "name": "Apex Expedition 8000 Parka",
        "category": "Jackets",
        "variant": "XL",
        "price": 14999.0,  # EXCEEDS 10K MAX ORDER VALUE CHECK
        "stock_count": 2,
        "description": "Sub-zero 900-fill down expedition parka rated down to -40°C.",
        "merchant_id": "merchant_a",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1544923246-77307dd654cb?w=500&q=80",
        "features": ["900 Fill Power", "High Value Test Item", "Pertex Quantum Shell"]
    }
]

# Initial Seed Data for Merchant B (Urban Trail Co.)
INITIAL_PRODUCTS_MERCHANT_B = [
    {
        "product_id": "URB-JKT-001",
        "name": "Urban Shield Waterproof Raincoat",
        "category": "Jackets",
        "variant": "M",
        "price": 1899.0,  # Lower price than Merchant A for comparison demo!
        "stock_count": 12,
        "description": "Sleek matte finish waterproof jacket tailored for city rain and cycling.",
        "merchant_id": "merchant_b",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1544022613-e87ca75a784a?w=500&q=80",
        "features": ["Reflective Strips", "Waterproof 15,000mm", "Packable Pocket"]
    },
    {
        "product_id": "URB-JKT-002",
        "name": "Urban Commute Windbreaker",
        "category": "Jackets",
        "variant": "L",
        "price": 1599.0,
        "stock_count": 9,
        "description": "Windproof and water-resistant ultralight jacket with magnetic closures.",
        "merchant_id": "merchant_b",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1548883354-7622d03aca27?w=500&q=80",
        "features": ["Magnetic Storm Flap", "Packable", "Under 300g"]
    },
    {
        "product_id": "URB-BAG-001",
        "name": "Urban Roll-top Commuter 24L",
        "category": "Bags",
        "variant": "24L",
        "price": 2199.0,
        "stock_count": 14,
        "description": "Waterproof TPU roll-top backpack with dedicated 16-inch padded laptop sleeve.",
        "merchant_id": "merchant_b",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1622560480605-d83c853bc5c3?w=500&q=80",
        "features": ["100% Waterproof TPU", "16-inch Laptop Sleeve", "Magnetic Fidlock Buckles"]
    },
    {
        "product_id": "URB-TSH-001",
        "name": "Urban Tech Everyday Tee",
        "category": "Apparel",
        "variant": "M",
        "price": 899.0,
        "stock_count": 20,
        "description": "Bamboo-cotton blend quick-dry crewneck tee for city comfort.",
        "merchant_id": "merchant_b",
        "currency": "INR",
        "image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500&q=80",
        "features": ["Eco-friendly Bamboo", "UV 50+ Protection", "Anti-wrinkle"]
    }
]

# Saved approved addresses for customer cust_001
SAVED_CUSTOMER_ADDRESSES = {
    "cust_001": [
        {
            "name": "Rahul Sharma",
            "street": "402, Green Glen Layout, Bellandur",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560103",
            "country": "India"
        },
        {
            "name": "Rahul Sharma (Office)",
            "street": "7th Floor, Prestige Tech Park, Marathahalli-Sarjapur Ring Rd",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560103",
            "country": "India"
        }
    ]
}

# In-Memory Database Fallback for High Availability & Sandbox Testing
class InMemoryStore:
    def __init__(self):
        self.products_merchant_a: Dict[str, Dict[str, Any]] = {p["product_id"]: dict(p) for p in INITIAL_PRODUCTS_MERCHANT_A}
        self.products_merchant_b: Dict[str, Dict[str, Any]] = {p["product_id"]: dict(p) for p in INITIAL_PRODUCTS_MERCHANT_B}
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.audit_logs: List[Dict[str, Any]] = []

    def reset(self):
        self.products_merchant_a = {p["product_id"]: dict(p) for p in INITIAL_PRODUCTS_MERCHANT_A}
        self.products_merchant_b = {p["product_id"]: dict(p) for p in INITIAL_PRODUCTS_MERCHANT_B}
        self.orders = {}
        self.audit_logs = []

in_memory_db = InMemoryStore()
use_mongo = False
mongo_client = None
mongo_db = None

async def init_db():
    global use_mongo, mongo_client, mongo_db
    if MONGODB_URI and MONGODB_URI.strip() and not MONGODB_URI.startswith("mongodb://localhost"):
        try:
            logger.info("Connecting to MongoDB Atlas...")
            mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000
            )
            # Test connection
            await mongo_client.admin.command('ping')
            logger.info("MongoDB Atlas ping successful!")
            mongo_db = mongo_client["agentic_commerce"]
            use_mongo = True
            logger.info("Connected to MongoDB Atlas database 'agentic_commerce'.")
            await seed_mongo_if_empty()
            return
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"MongoDB Atlas connection failed: {e}. Falling back to In-Memory Database.")
            use_mongo = False
        except Exception as e:
            logger.warning(f"MongoDB Atlas setup error: {e}. Falling back to In-Memory Database.")
            use_mongo = False
    else:
        logger.info("No external MongoDB Atlas URI configured. Using In-Memory Database with live seed catalog.")

async def seed_mongo_if_empty():
    global mongo_db
    if mongo_db is None:
        return
    try:
        col_a = mongo_db["products_merchant_a"]
        count_a = await col_a.count_documents({})
        if count_a == 0:
            await col_a.insert_many(INITIAL_PRODUCTS_MERCHANT_A)
            logger.info("Seeded products_merchant_a in MongoDB Atlas.")

        col_b = mongo_db["products_merchant_b"]
        count_b = await col_b.count_documents({})
        if count_b == 0:
            await col_b.insert_many(INITIAL_PRODUCTS_MERCHANT_B)
            logger.info("Seeded products_merchant_b in MongoDB Atlas.")
    except Exception as e:
        logger.error(f"Error seeding MongoDB Atlas: {e}")

async def get_product(merchant_id: str, product_id: str) -> Optional[Dict[str, Any]]:
    merchant_id = merchant_id.lower()
    collection_name = "products_merchant_b" if "merchant_b" in merchant_id else "products_merchant_a"

    if use_mongo and mongo_db is not None:
        doc = await mongo_db[collection_name].find_one({"product_id": product_id}, {"_id": 0})
        return doc

    store = in_memory_db.products_merchant_b if "merchant_b" in merchant_id else in_memory_db.products_merchant_a
    item = store.get(product_id)
    return dict(item) if item else None

async def search_products(
    merchant_id: Optional[str] = None,
    query: Optional[str] = None,
    category: Optional[str] = None,
    variant: Optional[str] = None,
    max_price: Optional[float] = None
) -> List[Dict[str, Any]]:
    # If merchant_id is specified, search that merchant; if "all", search both
    results = []
    merchants_to_query = []
    if merchant_id in ["merchant_a", "merchant_b"]:
        merchants_to_query.append(merchant_id)
    else:
        merchants_to_query = ["merchant_a", "merchant_b"]

    for m_id in merchants_to_query:
        collection_name = "products_merchant_b" if m_id == "merchant_b" else "products_merchant_a"
        if use_mongo and mongo_db is not None:
            filter_doc = {}
            if category:
                filter_doc["category"] = {"$regex": f"^{category}$", "$options": "i"}
            if variant:
                filter_doc["variant"] = {"$regex": f"^{variant}$", "$options": "i"}
            if max_price:
                filter_doc["price"] = {"$lte": max_price}
            if query:
                filter_doc["$or"] = [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"category": {"$regex": query, "$options": "i"}}
                ]
            cursor = mongo_db[collection_name].find(filter_doc, {"_id": 0})
            docs = await cursor.to_list(length=50)
            results.extend(docs)
        else:
            store = in_memory_db.products_merchant_b if m_id == "merchant_b" else in_memory_db.products_merchant_a
            for p in store.values():
                if category and category.lower() != p.get("category", "").lower():
                    continue
                if variant and variant.lower() != p.get("variant", "").lower():
                    continue
                if max_price and p.get("price", 0) > max_price:
                    continue
                if query:
                    q = query.lower()
                    matched = (
                        q in p.get("name", "").lower() or
                        q in p.get("description", "").lower() or
                        q in p.get("category", "").lower() or
                        q in p.get("product_id", "").lower()
                    )
                    if not matched:
                        continue
                results.append(dict(p))

    return results

async def update_stock(merchant_id: str, product_id: str, quantity: int) -> bool:
    collection_name = "products_merchant_b" if "merchant_b" in merchant_id else "products_merchant_a"
    if use_mongo and mongo_db is not None:
        res = await mongo_db[collection_name].update_one(
            {"product_id": product_id, "stock_count": {"$gte": quantity}},
            {"$inc": {"stock_count": -quantity}}
        )
        return res.modified_count > 0

    store = in_memory_db.products_merchant_b if "merchant_b" in merchant_id else in_memory_db.products_merchant_a
    item = store.get(product_id)
    if item and item.get("stock_count", 0) >= quantity:
        item["stock_count"] -= quantity
        return True
    return False

async def save_order(order_data: Dict[str, Any]) -> str:
    order_id = order_data.get("order_id")
    if use_mongo and mongo_db is not None:
        await mongo_db["orders"].insert_one(dict(order_data))
    else:
        in_memory_db.orders[order_id] = dict(order_data)
    return order_id

async def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    if use_mongo and mongo_db is not None:
        return await mongo_db["orders"].find_one({"order_id": order_id}, {"_id": 0})
    return in_memory_db.orders.get(order_id)

async def save_audit_log(entry: Dict[str, Any]) -> str:
    if "timestamp" not in entry:
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    if use_mongo and mongo_db is not None:
        await mongo_db["audit_logs"].insert_one(dict(entry))
    else:
        in_memory_db.audit_logs.insert(0, dict(entry))
    return entry.get("id", "")

async def get_audit_logs(limit: int = 50, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if use_mongo and mongo_db is not None:
        filter_doc = {"session_id": session_id} if session_id else {}
        cursor = mongo_db["audit_logs"].find(filter_doc, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
    if session_id:
        return [log for log in in_memory_db.audit_logs if log.get("session_id") == session_id][:limit]
    return in_memory_db.audit_logs[:limit]

async def reset_demo():
    in_memory_db.reset()
    if use_mongo and mongo_db is not None:
        await mongo_db["products_merchant_a"].delete_many({})
        await mongo_db["products_merchant_b"].delete_many({})
        await mongo_db["orders"].delete_many({})
        await mongo_db["audit_logs"].delete_many({})
        await seed_mongo_if_empty()
    logger.info("Demo state reset to initial catalog.")
