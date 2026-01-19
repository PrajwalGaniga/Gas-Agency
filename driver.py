from fastapi import APIRouter, Form, Depends, HTTPException, Query,Body
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from jose import jwt, JWTError
from bson import ObjectId
import math
from admin import get_current_driver
from auth import get_current_driver

# Database Imports
from app.database import (
    db, driver_collection, order_collection, customer_collection,driver_audit_collection, driver_location_collection
)
from app.utils import verify_password

driver_router = APIRouter()

# --- JWT CONFIGURATION (Driver Side) ---
# NOTE: We use the same secret key as Admin for simplicity, or can be separate.
SECRET_KEY = "your_secret_key_here"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="driver/login")

def create_driver_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7) # Drivers stay logged in longer
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_driver(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        driver_id = payload.get("sub")
        if driver_id is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return ObjectId(driver_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# PURPOSE: Distance Calculation Logic
def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return 999999.0
        
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        R = 6371.0 
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    except:
        return 999999.0

# PURPOSE: Driver Login (Returns JWT)
@driver_router.post("/driver/login")
async def driver_login(data: dict):
    phone = data.get("phone_number")
    password = data.get("password")
    
    driver = driver_collection.find_one({"phone_number": phone})
    
    if not driver:
        return {"success": False, "message": "Phone number not registered."}

    stored_hash = driver.get("password_hash")
    
    if stored_hash and verify_password(password, stored_hash):
        if not driver.get("is_active"):
            return {"success": False, "message": "Account inactive. Contact Admin."}
        
        # Generate JWT
        token = create_driver_token({"sub": str(driver["_id"])})

        return {
            "success": True,
            "access_token": token,
            "token_type": "bearer",
            "driver": {
                "id": str(driver["_id"]),
                "name": driver["name"],
                "cities": driver.get("assigned_cities", [])
            }
        }
    
    return {"success": False, "message": "Invalid password."}

# PURPOSE: Get Driver Orders (Legacy Endpoint Pattern with JWT security)
@driver_router.get("/driver/orders/{city}")
async def get_driver_orders_by_city(city: str, driver_id: ObjectId = Depends(get_current_driver)):
    # 1. Check for Active Job
    active_job = order_collection.find_one({
        "assigned_driver_id": driver_id,
        "status": "IN_PROGRESS"
    })
    
    if active_job:
        active_job["_id"] = str(active_job["_id"])
        cust = customer_collection.find_one({"_id": active_job["customer_id"]})
        active_job["customer_id"] = str(active_job["customer_id"])
        active_job["verified_lat"] = cust.get("verified_lat")
        active_job["verified_lng"] = cust.get("verified_lng")
        active_job["address"] = cust.get("landmark", "No Address")
        active_job["phone"] = cust.get("phone_number")
        active_job["customer_name"] = cust.get("name", "Unknown")
        return {"success": True, "has_active": True, "active_order": active_job}

    # 2. Fetch Pending Orders
    query = {"city": {"$regex": f"^{city.strip()}$", "$options": "i"}, "status": "PENDING"}
    orders = list(order_collection.find(query))
    
    processed = []
    for o in orders:
        o["_id"] = str(o["_id"])
        o["customer_id"] = str(o["customer_id"])
        cust = customer_collection.find_one({"_id": ObjectId(o["customer_id"])})
        if cust:
            o["address"] = cust.get("landmark", "No Address")
            o["is_verified"] = True if cust.get("verified_lat") else False
            processed.append(o)

    processed.sort(key=lambda x: x.get("is_verified", False), reverse=True)
    return {"success": True, "has_active": False, "orders": processed}

# PURPOSE: Get Driver Orders with Distance Sorting (Smart Endpoint)
@driver_router.get("/driver/orders")
async def get_driver_orders_smart(
    cities: str = Query(""), 
    lat: str = None, 
    lng: str = None, 
    driver_id: ObjectId = Depends(get_current_driver)
):
    try:
        city_list = [c.strip() for c in cities.split(",") if c.strip()]

        driver = driver_collection.find_one({"_id": driver_id})
        admin_id = driver.get("admin_id")

        active_job = order_collection.find_one({
            "assigned_driver_id": driver_id,
            "status": "IN_PROGRESS"
        })

        if active_job:
            active_job["_id"] = str(active_job["_id"])
            active_job["customer_id"] = str(active_job["customer_id"])
            active_job["admin_id"] = str(active_job.get("admin_id", ""))
            active_job["assigned_driver_id"] = str(active_job.get("assigned_driver_id", ""))

            cust = customer_collection.find_one({"_id": ObjectId(active_job["customer_id"])})
            if cust:
                active_job["verified_lat"] = cust.get("verified_lat")
                active_job["verified_lng"] = cust.get("verified_lng")
                active_job["address"] = cust.get("landmark", "No Address")
                active_job["phone"] = cust.get("phone_number")
                active_job["customer_name"] = cust.get("name", "Unknown")
            
            return {"success": True, "has_active": True, "active_order": active_job}

        query = {
            "admin_id": admin_id, 
            "city": {"$in": city_list}, 
            "status": "PENDING"
        }
        orders = list(order_collection.find(query))

        processed = []
        for o in orders:
            o["_id"] = str(o["_id"])
            o["customer_id"] = str(o["customer_id"])
            o["admin_id"] = str(o.get("admin_id", ""))

            cust = customer_collection.find_one({"_id": ObjectId(o["customer_id"])})
            if cust:
                o["address"] = cust.get("landmark", "No Address")
                o["phone"] = cust.get("phone_number")
                o["verified_lat"] = cust.get("verified_lat")
                o["verified_lng"] = cust.get("verified_lng")
                
                o["distance"] = calculate_distance(lat, lng, o["verified_lat"], o["verified_lng"])
                o["is_verified"] = True if o["verified_lat"] else False
                processed.append(o)

        processed.sort(key=lambda x: (not x["is_verified"], x["distance"]))
        
        return {"success": True, "has_active": False, "orders": processed}

    except Exception as e:
        print(f"CRITICAL BACKEND ERROR: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# PURPOSE: Complete delivery and update customer GPS
@driver_router.post("/driver/complete-delivery")
async def complete_delivery(
    order_id: str = Form(...), 
    lat: str = Form(...), 
    long: str = Form(...),
    # Token required but not strictly used for logic here (security only)
    driver_id: ObjectId = Depends(get_current_driver) 
):
    order = order_collection.find_one({"_id": ObjectId(order_id)})
    if not order:
        return {"success": False, "message": "Order not found"}

    customer_collection.update_one(
        {"_id": order["customer_id"]},
        {"$set": {"verified_lat": lat, "verified_lng": long}}
    )
    
    order_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": "DELIVERED", "delivered_at": datetime.utcnow()}}
    )
    
    customer_collection.update_one(
        {"records.order_id": ObjectId(order_id)},
        {"$set": {"records.$.status": "DELIVERED"}}
    )
    return {"success": True}

# PURPOSE: Records driver GPS ping and updates live status
@driver_router.post("/driver/location")
async def update_location(
    lat: float = Body(...), 
    lng: float = Body(...), 
    driver_id: ObjectId = Depends(get_current_driver)
):
    now = datetime.utcnow()
    # Log to history for path drawing
    driver_location_collection.insert_one({
        "driver_id": driver_id,
        "lat": lat,
        "lng": lng,
        "timestamp": now
    })
    # Update current profile for live table
    driver_collection.update_one(
        {"_id": driver_id},
        {"$set": {"last_seen": now, "current_lat": lat, "current_lng": lng}}
    )
    return {"success": True}

# PURPOSE: Explicit Driver Logout
@driver_router.post("/driver/logout")
async def driver_logout(driver_id: ObjectId = Depends(get_current_driver)):
    driver_audit_collection.insert_one({
        "driver_id": driver_id,
        "event": "LOGOUT",
        "timestamp": datetime.utcnow()
    })
    return {"success": True}