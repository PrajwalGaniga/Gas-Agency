# driver.py
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from datetime import datetime, timedelta, timezone
from jose import jwt
from bson import ObjectId
import math

# Internal Imports
from auth import get_current_driver, SECRET_KEY, ALGORITHM
from app.database import (
    driver_collection, order_collection, customer_collection,
    driver_audit_collection, driver_location_collection, change_requests_collection
)
from app.utils import verify_password

driver_router = APIRouter()

# --- 🛠️ SENIOR UTILS ---

def stringify_doc(doc):
    """Recursively converts all ObjectIds in a MongoDB document to strings"""
    if not doc: return doc
    doc["_id"] = str(doc["_id"])
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            # Ensure dates are JSON serializable
            doc[key] = value.isoformat()
    return doc

def create_driver_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7) 
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        if not all([lat1, lon1, lat2, lon2]): return 999.0
        R = 6371.0 
        phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
        dphi, dlambda = math.radians(float(lat2)-float(lat1)), math.radians(float(lon2)-float(lon1))
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    except: return 999.0

# --- 🚀 ROUTES ---

@driver_router.post("/driver/login")
async def driver_login(data: dict = Body(...)):
    phone = data.get("phone_number")
    password = data.get("password")
    driver = driver_collection.find_one({"phone_number": phone})
    
    if not driver or not verify_password(password, driver.get("password_hash")):
        return {"success": False, "message": "Invalid credentials"}
    
    token = create_driver_token({"sub": str(driver["_id"])})
    driver_audit_collection.insert_one({
        "driver_id": driver["_id"], "event": "LOGIN", "timestamp": datetime.now(timezone.utc)
    })

    return {
        "success": True, 
        "access_token": token,
        "driver": {"id": str(driver["_id"]), "name": driver["name"], "cities": driver.get("assigned_cities", [])}
    }

@driver_router.post("/driver/accept-order")
async def accept_order(data: dict = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    """Moves order from PENDING to IN_PROGRESS"""
    o_id = ObjectId(data.get("order_id"))
    order_collection.update_one(
        {"_id": o_id, "assigned_driver_id": driver_id},
        {"$set": {"status": "IN_PROGRESS", "started_at": datetime.now(timezone.utc)}}
    )
    return {"success": True}

@driver_router.get("/driver/orders")
async def get_driver_worklist(
    cities: str = Query(""), lat: str = "0.0", lng: str = "0.0", 
    date: str = Query(None), 
    driver_id: ObjectId = Depends(get_current_driver)
):
    """Fetches ALL assigned orders for a specific date to maintain a persistent checklist"""
    try:
        # 🟢 TERMINAL DEBUG 1: Request Details
        print(f"\n--- 🛰️  CHECKLIST REQUEST ---")
        print(f"Driver: {driver_id} | Date Filter: {date}")

        # 1. Build the Base Query: Orders assigned to THIS driver
        query = {
            "assigned_driver_id": driver_id,
            "status": {"$in": ["PENDING", "IN_PROGRESS", "DELIVERED"]}
        }

        # 2. Add Date Filtering logic (Parses date from Flutter)
        if date:
            try:
                # Expecting format YYYY-M-D from Flutter
                date_parts = [int(p) for p in date.split("-")]
                target_date = datetime(date_parts[0], date_parts[1], date_parts[2])
                
                # Search for the full 24-hour range of that day
                day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                
                query["created_at"] = {"$gte": day_start, "$lt": day_end}
            except Exception as e:
                print(f"⚠️ Date Parsing Error: {e}")

        # 3. Fetch from MongoDB and group by Status (Active first)
        # Sorting priority: IN_PROGRESS -> PENDING -> DELIVERED
        orders_cursor = order_collection.find(query)
        raw_orders = list(orders_cursor)

        # 🟢 TERMINAL DEBUG 2: MongoDB Findings
        print(f"📦 DATABASE RESULT: Found {len(raw_orders)} total orders for checklist.")

        processed = []
        for o in raw_orders:
            o = stringify_doc(o) # Recursive ObjectId to String conversion
            
            # Fetch linked customer details for the UI
            cust = customer_collection.find_one({"_id": ObjectId(o["customer_id"])})
            if cust:
                o["address"] = cust.get("landmark", "No Address")
                o["phone"] = cust.get("phone_number")
                o["verified_lat"] = cust.get("verified_lat")
                o["verified_lng"] = cust.get("verified_lng")
                # Calculate real-time distance for sorting
                o["distance"] = calculate_distance(lat, lng, o["verified_lat"], o["verified_lng"])
                processed.append(o)

        # 4. Final Business Logic Sort
        # Keeps Active (Blue) at the top, then Pending (Orange), then Delivered (Green)
        status_priority = {"IN_PROGRESS": 0, "PENDING": 1, "DELIVERED": 2}
        processed.sort(key=lambda x: (status_priority.get(x["status"], 3), x["distance"]))

        print(f"✅ SUCCESS: Returning {len(processed)} checklist items.")
        print(f"--- 🛰️  END REQUEST ---\n")
        
        return {"success": True, "orders": processed}
    
    except Exception as e:
        print(f"❌ CRITICAL CHECKLIST ERROR: {e}")
        raise HTTPException(status_code=500, detail="Internal Checklist Error")
    
# --- 🚀 LIFECYCLE & TRACKING ROUTES ---

@driver_router.post("/driver/accept-order")
async def accept_order(data: dict = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    """Moves an order from PENDING (Orange) to IN_PROGRESS (Blue State)"""
    try:
        o_id = ObjectId(data.get("order_id"))
        
        # 🟢 TERMINAL DEBUG: Acceptance Signal
        print(f"🚛 DRIVER STARTING JOB: {o_id}")

        # 1. Update the Order status and set 'started_at' timestamp
        result = order_collection.update_one(
            {"_id": o_id, "assigned_driver_id": driver_id},
            {"$set": {
                "status": "IN_PROGRESS", 
                "started_at": datetime.now(timezone.utc)
            }}
        )

        if result.modified_count == 0:
            return {"success": False, "message": "Order already started or not assigned to you."}

        # 2. 🛡️ SENIOR SYNC: Update Customer's record history
        # This ensures the Admin Dashboard 'Audit' and 'Customer Info' both show 'Ongoing'
        customer_collection.update_one(
            {"records.order_id": o_id},
            {"$set": {"records.$.status": "IN_PROGRESS"}}
        )

        print(f"✅ SUCCESS: Order {o_id} transitioned to IN_PROGRESS")
        return {"success": True}
        
    except Exception as e:
        print(f"❌ ACCEPT ERROR: {e}")
        return {"success": False, "message": str(e)}


@driver_router.post("/driver/location")
async def update_driver_location(data: dict = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    """Receives 5-min GPS Heartbeat to feed 'Work Hours' and 'Live Tracking'"""
    try:
        lat = data.get("lat")
        lng = data.get("lng")
        now = datetime.now(timezone.utc)
        
        # 1. Update Driver's 'Last Seen' for the Dashboard Pulse
        driver_collection.update_one(
            {"_id": driver_id},
            {"$set": {
                "current_lat": lat, 
                "current_lng": lng, 
                "last_seen": now
            }}
        )
        
        # 2. Log entry in Audit Collection to calculate work duration
        # Your 'calculate_work_time' function in admin.py relies on these logs
        driver_location_collection.insert_one({
            "driver_id": driver_id,
            "lat": lat,
            "lng": lng,
            "timestamp": now
        })
        
        return {"success": True}
    except Exception as e:
        print(f"🛰️ GPS PING ERROR: {e}")
        return {"success": False}

@driver_router.post("/driver/change-request")
async def driver_change_request(data: dict = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    driver = driver_collection.find_one({"_id": driver_id})
    cust = customer_collection.find_one({"_id": ObjectId(data.get("customer_id"))})
    
    # Determine old value based on category
    category = data.get("category")
    old_val = cust.get("landmark" if category == "ADDRESS" else "phone_number", "N/A")

    change_requests_collection.insert_one({
        "admin_id": driver["admin_id"],
        "driver_id": driver_id,
        "driver_name": driver["name"], # 🚀 Added for HTML template
        "customer_id": ObjectId(data.get("customer_id")),
        "request_type": category,      # 🚀 Matches req.request_type in HTML
        "old_value": old_val,          # 🚀 Matches req.old_value in HTML
        "new_value": data.get("new_details"), # 🚀 Matches req.new_value in HTML
        "status": "PENDING",
        "timestamp": datetime.now(timezone.utc)
    })
    return {"success": True, "message": "Request logged"}

# driver.py (Add these to your existing file)

@driver_router.post("/driver/complete-order")
async def complete_order(data: dict = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    """Marks delivery as complete and verifies the EXACT GPS received from the phone"""
    try:
        o_id = ObjectId(data.get("order_id"))
        lat = data.get("lat")
        lng = data.get("lng")
        
        # 🟢 TERMINAL DEBUG: Verify what the phone actually sent
        print(f"--- ✅ COMPLETING ORDER ---")
        print(f"Order ID: {o_id}")
        print(f"Captured GPS: {lat}, {lng}")

        order = order_collection.find_one({"_id": o_id})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # 1. Update Order Collection
        order_collection.update_one({"_id": o_id}, {"$set": {
            "status": "DELIVERED", 
            "delivered_at": datetime.now(timezone.utc),
            "verified_lat": lat,
            "verified_lng": lng
        }})

        # 2. Update Customer Record (Permanent Verification)
        customer_collection.update_one(
            {"_id": order["customer_id"]}, 
            {"$set": {"verified_lat": lat, "verified_lng": lng}}
        )

        # 3. Sync to Customer's 'records' array for Admin History
        customer_collection.update_one(
            {"_id": order["customer_id"], "records.order_id": o_id},
            {"$set": {"records.$.status": "DELIVERED"}}
        )

        print(f"✅ SUCCESS: Database updated with GPS: {lat}, {lng}")
        return {"success": True}
    except Exception as e:
        print(f"❌ ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))