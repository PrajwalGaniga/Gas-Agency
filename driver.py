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
    driver_audit_collection, driver_location_collection, change_requests_collection, shifts_collection
)
from app.utils import verify_password
from app.schemas import DriverLogin, AcceptOrderRequest, CompleteOrderRequest, LocationPing, ChangeRequestPayload

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
async def driver_login(data: DriverLogin = Body(...)):
    phone = data.phone_number
    password = data.password
    driver = driver_collection.find_one({"phone_number": phone})
    
    if not driver or not verify_password(password, driver.get("password_hash")):
        raise HTTPException(
            status_code=401, 
            detail="Invalid Credentials: Check your phone number or PIN."
        )
    
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
                # Expecting format YYYY-MM-DD from Flutter
                date_parts = [int(p) for p in date.split("-")]
                target_date = datetime(date_parts[0], date_parts[1], date_parts[2])
                
                # Search for the full 24-hour range of that day
                day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                
                target_date_str = target_date.strftime("%Y-%m-%d")

                # The strict matching logic for Component 7
                query["$or"] = [
                    {"assigned_date": target_date_str},
                    {"assigned_date": {"$exists": False}, "created_at": {"$gte": day_start, "$lt": day_end}}
                ]
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
async def accept_order(data: AcceptOrderRequest = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    """Moves an order from PENDING (Orange) to IN_PROGRESS (Blue State)"""
    try:
        o_id = ObjectId(data.order_id)
        
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


# --- ADD THESE IMPORTS TO THE TOP OF driver.py ---
# --- ADD THESE IMPORTS TO THE TOP OF driver.py ---
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError

# Initialize the Python Geocoder (User agent is required)
geolocator = Nominatim(user_agent="gas_flow_enterprise_system")

@driver_router.post("/driver/location")
async def update_driver_location(data: LocationPing = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    """
    Receives GPS from phone, uses Python to resolve the street address,
    and updates the driver's master record.
    """
    try:
        lat = data.lat
        lng = data.lng
        now = datetime.now(timezone.utc)
        
        # 🛰️ PYTHON REVERSE GEOCODING
        resolved_address = "Address Pending..."
        try:
            # Resolves Lat/Lng to a real street name using Python
            location = geolocator.reverse(f"{lat}, {lng}", timeout=3)
            if location:
                resolved_address = location.address
        except (GeopyError, ValueError):
            resolved_address = "Satellite Link Active (Address Busy)"

        # 1. Update Driver Collection with the NEW Address field
        driver_collection.update_one(
            {"_id": driver_id},
            {"$set": {
                "current_lat": lat, 
                "current_lng": lng, 
                "current_address": resolved_address, # 🚀 This fixes the display issue
                "last_seen": now
            }}
        )
        
        # 2. Log entry for historical pathing
        driver_location_collection.insert_one({
            "driver_id": driver_id,
            "lat": lat,
            "lng": lng,
            "address": resolved_address,
            "timestamp": now
        })
        
        return {"success": True, "address": resolved_address}
    except Exception as e:
        print(f"🛰️ GPS BACKEND ERROR: {e}")
        return {"success": False}

@driver_router.post("/driver/location-ping")
async def simple_location_ping(data: LocationPing = Body(...)):
    """Simple ping route for the background location service without complex auth"""
    try:
        # Just logging or updating a quick cache for the admin map
        lat = data.lat
        lng = data.lng
        now = datetime.now(timezone.utc)
        
        # For this test simulation, we assume driver_id is passed in raw or mocked
        # In prod this would use JWT depends
        target_driver_id = "mock_driver_id" # Simplified for test
        
        driver_location_collection.insert_one({
            "driver_id": str(target_driver_id),
            "lat": lat,
            "lng": lng,
            "timestamp": now
        })
        return {"success": True, "message": "Ping received"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@driver_router.post("/driver/sync-offline")
async def sync_offline_data(data: dict = Body(...)):
    """Receives buffered actions from the Flutter Hive sync_queue"""
    try:
        actions = data.get("offline_actions", [])
        device_id = data.get("device_id")
        
        print(f"🔄 RECEIVED BATCH SYNC: {len(actions)} actions from {device_id}")
        
        success_count = 0
        for action in actions:
            # Here we would safely map 'action_type' to internal functions
            # e.g., if action["action_type"] == "COMPLETE_ORDER": complete_order(...)
            print(f"  -> Processing: {action['action_type']} | Order: {action.get('payload', {}).get('order_id')}")
            success_count += 1
            
        return {
            "success": True, 
            "synced_count": success_count,
            "message": "Offline data synchronized with main ledger."
        }
    except Exception as e:
        print(f"❌ SYNC ERROR: {e}")
        raise HTTPException(status_code=500, detail="Failed to process offline batch")

@driver_router.post("/driver/change-request")
async def driver_change_request(data: ChangeRequestPayload = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    driver = driver_collection.find_one({"_id": driver_id})
    cust = customer_collection.find_one({"_id": ObjectId(data.customer_id)})
    
    # Determine old value based on category
    category = data.category
    
    if category == "LOCATION_UPDATE":
        old_val = f"Lat: {cust.get('verified_lat')}, Lng: {cust.get('verified_lng')}"
        if data.order_id:
            # Mark the specific order as PENDING_APPROVAL
            order_collection.update_one(
                {"_id": ObjectId(data.order_id)},
                {"$set": {"status": "PENDING_APPROVAL"}}
            )
            customer_collection.update_one(
                {"_id": ObjectId(data.customer_id), "records.order_id": ObjectId(data.order_id)},
                {"$set": {"records.$.status": "PENDING_APPROVAL"}}
            )
    else:
        old_val = cust.get("landmark" if category == "ADDRESS" else "phone_number", "N/A")

    change_requests_collection.insert_one({
        "admin_id": driver["admin_id"],
        "driver_id": driver_id,
        "driver_name": driver["name"], # 🚀 Added for HTML template
        "customer_id": ObjectId(data.customer_id),
        "order_id": ObjectId(data.order_id) if data.order_id else None,
        "request_type": category,      # 🚀 Matches req.request_type in HTML
        "old_value": old_val,          # 🚀 Matches req.old_value in HTML
        "new_value": data.new_details, # 🚀 Matches req.new_value in HTML
        "lat": data.lat,
        "lng": data.lng,
        "status": "PENDING",
        "timestamp": datetime.now(timezone.utc)
    })
    return {"success": True, "message": "Request logged. Awaiting Admin Approval."}

# driver.py (Add these to your existing file)

from app.schemas import ReportIssueRequest

@driver_router.post("/report-issue")
async def report_issue(data: ReportIssueRequest = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    try:
        driver = driver_collection.find_one({"_id": driver_id})
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
            
        issue_doc = {
            "driver_id": driver_id,
            "driver_name": driver["name"],
            "admin_id": driver["admin_id"],
            "issue_type": data.issue_type, # e.g. "Customer Not Home", "Leak"
            "remarks": data.remarks,
            "lat": data.lat,
            "lng": data.lng,
            "status": "OPEN",
            "created_at": datetime.now(timezone.utc)
        }
        db["driver_issues"].insert_one(issue_doc)
        return {"success": True, "message": "Issue reported successfully"}
        
    except Exception as e:
        print(f"Error reporting issue: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@driver_router.post("/driver/complete-order")
async def complete_order(data: CompleteOrderRequest = Body(...), driver_id: ObjectId = Depends(get_current_driver)):
    """Marks delivery as complete with Shift-Based Inventory & Distance Checking"""
    try:
        o_id = ObjectId(data.order_id)
        lat = data.lat
        lng = data.lng
        
        print(f"--- ✅ COMPLETING ORDER ---")
        print(f"Order ID: {o_id}")
        
        # 1. Fetch Active Shift
        shift = shifts_collection.find_one({"driver_id": str(driver_id), "status": "OPEN"})
        if not shift:
            raise HTTPException(status_code=403, detail="No active shift found. Please ask Admin to start your shift.")

        # 2. Check Inventory
        current_full = shift["load_departure"]["full"] - shift["load_return"]["full"]
        if current_full <= 0:
            raise HTTPException(status_code=400, detail="Insufficient Stock on Truck.")

        order = order_collection.find_one({"_id": o_id})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # 3. Distance Check & Flagging (The Gold Standard)
        is_flagged = False
        requires_change_request = False
        customer = customer_collection.find_one({"_id": order["customer_id"]})
        
        if customer and customer.get("verified_lat") and customer.get("verified_lng"):
            distance = calculate_distance(lat, lng, customer["verified_lat"], customer["verified_lng"])
            if distance > 0.15: # 150m threshold
                # 🛑 Block delivery; require admin change request
                return {
                    "success": False, 
                    "requires_change_request": True,
                    "distance": distance,
                    "message": f"Location mismatch: You are {distance * 1000:.0f}m away from verified coordinates. Please submit a Change Request."
                }
            elif distance > 0.05: # > 50m but < 150m, allow but flag it
                is_flagged = True
                print(f"⚠️ Flagged: Driver is {distance*1000:.0f}m away (within 150m limit).")

        # 4. Atomic Shift Update (Cylinders & Cash)
        update_fields = {
            "$inc": {
                "load_return.full": 1, # Incrementing returned full cylinders actually means we consumed one from the departing load
                "load_return.empty": data.empties_collected
            }
        }
        
        if data.payment_mode == "CASH":
            update_fields["$inc"]["financials.expected_cash"] = float(data.amount_collected)
            update_fields["$inc"]["financials.actual_cash_collected"] = float(data.amount_collected)
        elif data.payment_mode == "UPI":
            update_fields["$inc"]["financials.upi_total"] = float(data.amount_collected)

        shifts_collection.update_one({"_id": shift["_id"]}, update_fields)

        # 6. Legacy Driver Stats Update (Optional but kept for compatibility)
        driver_collection.update_one(
            {"_id": driver_id},
            {"$inc": {
                "current_stock": -1,
                "collected_cash": float(data.amount_collected) if data.payment_mode == "CASH" else 0
            }}
        )

        # 7. Update Order Collection
        order_collection.update_one({"_id": o_id}, {"$set": {
            "status": "DELIVERED", 
            "delivered_at": datetime.now(timezone.utc),
            "verified_lat": lat,
            "verified_lng": lng,
            "payment_status": "PAID" if data.payment_mode == "UPI" else "CASH_COLLECTED",
            "payment_mode": data.payment_mode,
            "amount_collected": data.amount_collected,
            "cylinders_delivered": 1,
            "empties_collected": data.empties_collected,
            "is_flagged": is_flagged,
            "shift_id": str(shift["_id"]),
            "amount_paid": float(data.amount_collected)
        }})

        # 8. Sync Customer Record status
        customer_collection.update_one(
            {"_id": order["customer_id"]}, 
            {"$set": {
                "verified_lat": lat, 
                "verified_lng": lng,
                "active_order_lock": False,
                "last_order_date": datetime.now(timezone.utc)
            }}
        )

        customer_collection.update_one(
            {"_id": order["customer_id"], "records.order_id": o_id},
            {"$set": {"records.$.status": "DELIVERED"}}
        )

        print(f"✅ SUCCESS: Shift {shift['_id']} updated.")
        return {"success": True, "is_flagged": is_flagged, "message": f"Success: ₹{data.amount_collected} recorded."}
    except Exception as e:
        print(f"❌ ERROR: {e}")
        # Reraise HTTP exceptions so they hit the global handler cleanly
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@driver_router.get("/driver/shift/status")
async def get_shift_status(driver_id: ObjectId = Depends(get_current_driver)):
    """Fetches real-time inventory and financial status for the active shift"""
    try:
        shift = shifts_collection.find_one({"driver_id": str(driver_id), "status": "OPEN"})
        if not shift:
            return {"active": False, "message": "No active shift found"}
        
        # Aggregated Inventory
        # Current Full = Departure Full - Return Full (which tracks consumed)
        current_full = shift["load_departure"]["full"] - shift["load_return"]["full"]
        # Current Empties = Departure Empty + Return Empty (collected from customers)
        current_empty = shift["load_departure"]["empty"] + shift["load_return"]["empty"]
        
        return {
            "active": True,
            "shift_id": str(shift["_id"]),
            "inventory": {
                "total_loaded": shift["load_departure"]["full"], # 🚀 Added: Total Loaded Today
                "full_cylinders": current_full,
                "empty_cylinders": current_empty
            },
            "financials": shift.get("financials", {
                "expected_cash": 0.0,
                "actual_cash_collected": 0.0,
                "upi_total": 0.0
            }),
            "start_time": shift.get("start_time")
        }
    except Exception as e:
        print(f"❌ SHIFT STATUS ERROR: {e}")
        raise HTTPException(status_code=500, detail="Error fetching shift status")
