from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query, Body
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime
from bson import ObjectId
from typing import List

# --- IMPORTS ---
# Fix: Import auth from auth.py to avoid circular dependency with admin.py
from auth import get_current_admin
from app.database import (
    db, customer_collection, order_collection, 
    cities_collection, driver_collection
)

customer_router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.add_extension('jinja2.ext.do')
# --- HELPER FUNCTIONS ---

def get_optimal_driver(admin_id: ObjectId, city: str):
    """
    Finds the best driver for a specific city based on:
    1. Active Status
    2. Assigned City
    3. Lowest number of PENDING/IN_PROGRESS orders (Load Balancing)
    """
    # 1. Find all active drivers for this admin in this city
    drivers = list(driver_collection.find({
        "admin_id": admin_id,
        "is_active": True,
        "assigned_cities": city
    }))
    
    if not drivers:
        return None
        
    # 2. Find driver with least load
    best_driver = None
    min_load = float('inf')
    
    for driver in drivers:
        # Count active orders for this driver
        load = order_collection.count_documents({
            "assigned_driver_id": driver["_id"],
            "status": {"$in": ["PENDING", "IN_PROGRESS"]}
        })
        
        if load < min_load:
            min_load = load
            best_driver = driver
            
    return best_driver

# --- ROUTES ---
# customer.py

# customer.py

# customer.py

@customer_router.get("/customers")
async def customer_management(
    request: Request, 
    filter_type: str = "all", 
    search: str = Query(None),
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    # 1. Fetch Customers
    query = {"admin_id": admin_id}
    if search:
        query["$and"] = [
            {"admin_id": admin_id},
            {"$or": [ 
                {"name": {"$regex": search, "$options": "i"}},
                {"phone_number": {"$regex": search, "$options": "i"}},
                {"city": {"$regex": search, "$options": "i"}}
            ]}
        ]
    
    all_matching_customers = list(customer_collection.find(query).sort("created_at", -1))
    stats = {
        "pending": order_collection.count_documents({
            "admin_id": admin_id, 
            "status": "PENDING"
        })
    }

    # 2. Optimization: Fetch ALL active orders for this admin once
    active_orders = list(order_collection.find({
        "admin_id": admin_id,
        "status": {"$in": ["PENDING", "IN_PROGRESS"]}
    }))
    
    active_order_map = {}
    for order in active_orders:
        cust_id = str(order["customer_id"])
        active_order_map[cust_id] = {
            "order_id": str(order["_id"]),
            "driver_id": str(order.get("assigned_driver_id", "")),
            "status": order["status"]
        }

    # 3. Fetch Drivers and FIX: Convert ALL non-serializable objects (ObjectId & datetime)
    drivers = list(driver_collection.find({"admin_id": admin_id, "is_active": True}))
    for d in drivers:
        # Convert IDs to strings
        d["_id"] = str(d["_id"])
        if "admin_id" in d:
            d["admin_id"] = str(d["admin_id"])
            
        # FIX: Convert ALL datetime objects to ISO strings for JSON compatibility
        for key, value in d.items():
            if isinstance(value, datetime):
                d[key] = value.isoformat()
    
    processed_customers = []
    for c in all_matching_customers:
        c_id = str(c["_id"])
        c["_id"] = c_id
        
        # Determine Status
        order_info = active_order_map.get(c_id)
        if order_info:
            c["current_status"] = order_info["status"]
            c["active_order_id"] = order_info["order_id"]
            c["assigned_driver_id"] = order_info["driver_id"]
        else:
            if c.get("records") and len(c["records"]) > 0:
                c["current_status"] = c["records"][-1].get("status", "No Orders")
            else:
                c["current_status"] = "No Orders"
            c["active_order_id"] = None
            c["assigned_driver_id"] = None

        # Safe GPS Float Conversion
        lat = c.get("verified_lat")
        lng = c.get("verified_lng")
        if lat is not None and lng is not None:
            try:
                c["verified_lat"] = float(lat)
                c["verified_lng"] = float(lng)
                c["is_verified"] = True
            except (ValueError, TypeError):
                c["is_verified"] = False
        else:
            c["is_verified"] = False

        # Apply Filters
        current_status_lower = c["current_status"].lower()
        if filter_type == "all":
            processed_customers.append(c)
        elif filter_type == current_status_lower:
            processed_customers.append(c)

    cities = list(cities_collection.find().sort("name", 1))
    
    return templates.TemplateResponse("customers.html", {
        "request": request, 
        "customers": processed_customers,
        "cities": cities,
        "drivers": drivers,
        "active_filter": filter_type,
        "search_query": search or "",
        "stats": stats  # 👈 This line fixes the UndefinedError
    })

@customer_router.post("/add-city")
async def add_city(city_name: str = Form(...)):
    try:
        db["cities"].update_one(
            {"name": city_name}, 
            {"$set": {"name": city_name}}, 
            upsert=True
        )
        return RedirectResponse(url="/customers", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database error")

@customer_router.post("/add-customer")
async def add_customer(
    request: Request, 
    name: str = Form(...), 
    phone: str = Form(...), 
    city: str = Form(...), 
    landmark: str = Form(...),
    pincode: str = Form(""),
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)

    customer_collection.insert_one({
        "admin_id": admin_id,
        "name": name, 
        "phone_number": phone, 
        "city": city, 
        "landmark": landmark,
        "pincode": pincode,
        "verified_lat": None, 
        "verified_lng": None, 
        "records": [], 
        "created_at": datetime.utcnow()
    })
    return RedirectResponse(url="/customers", status_code=303)

# customer.py

# customer.py

@customer_router.post("/create-order")
async def create_order(
    request: Request, 
    customer_id: str = Form(...), 
    driver_id: str = Form(None), # Can be 'auto', 'later', or a specific ID
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    cust = customer_collection.find_one({"_id": ObjectId(customer_id), "admin_id": admin_id})
    if not cust:
        raise HTTPException(status_code=403, detail="Customer not found")

    # Prevent double ordering
    active_exists = order_collection.find_one({
        "customer_id": cust["_id"],
        "status": {"$in": ["PENDING", "IN_PROGRESS"]}
    })
    if active_exists:
        return RedirectResponse(url="/customers?error=Active order already exists", status_code=303)

    # --- SMART ASSIGNMENT LOGIC ---
    final_driver_id = None
    final_driver_name = "Unassigned"

    # Use .strip() and .casefold() to ensure matching works regardless of spacing/case
    target_city = cust["city"].strip()

    if driver_id == "auto":
        # Load Balancing: Find active driver in this city with the fewest pending tasks
        assigned_driver = get_optimal_driver(admin_id, target_city)
        if assigned_driver:
            final_driver_id = assigned_driver["_id"]
            final_driver_name = assigned_driver["name"]
    elif driver_id and driver_id != "later":
        # Specific driver selected by admin
        driver = driver_collection.find_one({"_id": ObjectId(driver_id)})
        if driver:
            final_driver_id = driver["_id"]
            final_driver_name = driver["name"]

    order_data = {
        "admin_id": admin_id,
        "customer_id": cust["_id"],
        "customer_name": cust["name"],
        "city": target_city,
        "status": "PENDING",
        "assigned_driver_id": final_driver_id,
        "assigned_driver_name": final_driver_name,
        "created_at": datetime.utcnow()
    }
    
    result = order_collection.insert_one(order_data)
    
    # Sync update to customer's history records
    customer_collection.update_one(
        {"_id": cust["_id"]},
        {"$push": {"records": {
            "order_id": result.inserted_id,
            "date": datetime.utcnow(),
            "status": "PENDING",
            "driver_name": final_driver_name
        }}}
    )
    return RedirectResponse(url="/customers", status_code=303)

# customer.py

@customer_router.post("/customers/bulk-order")
async def bulk_order(
    request: Request, 
    customer_ids: List[str] = Form(...),
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id:
        return JSONResponse(status_code=401, content={"success": False, "message": "Unauthorized"})

    count = 0
    for cid in customer_ids:
        # Verify customer belongs to this admin
        cust = customer_collection.find_one({"_id": ObjectId(cid), "admin_id": admin_id})
        if not cust: 
            continue

        # Prevent duplicate active orders
        if order_collection.find_one({
            "customer_id": cust["_id"], 
            "status": {"$in": ["PENDING", "IN_PROGRESS"]}
        }):
            continue

        # AUTO ASSIGNMENT LOGIC
        assigned_driver = get_optimal_driver(admin_id, cust["city"])
        driver_id = assigned_driver["_id"] if assigned_driver else None
        driver_name = assigned_driver["name"] if assigned_driver else "Unassigned"

        order_data = {
            "admin_id": admin_id,
            "customer_id": cust["_id"],
            "customer_name": cust["name"],
            "city": cust["city"],
            "status": "PENDING",
            "assigned_driver_id": driver_id,
            "assigned_driver_name": driver_name,
            "created_at": datetime.utcnow()
        }
        res = order_collection.insert_one(order_data)
        
        # Sync update to customer's history records
        customer_collection.update_one(
            {"_id": cust["_id"]},
            {"$push": {"records": {
                "order_id": res.inserted_id,
                "date": datetime.utcnow(),
                "status": "PENDING",
                "driver_name": driver_name
            }}}
        )
        count += 1

    return JSONResponse(content={
        "success": True, 
        "message": f"Successfully created {count} orders with auto-assignment."
    })
@customer_router.post("/customers/reassign-driver")
async def reassign_driver(
    order_id: str = Form(...),
    driver_id: str = Form(...),
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id:
        return JSONResponse(status_code=401, content={"success": False})

    order = order_collection.find_one({"_id": ObjectId(order_id), "admin_id": admin_id})
    if not order:
        return JSONResponse(status_code=404, content={"success": False, "message": "Order not found"})
    
    driver = driver_collection.find_one({"_id": ObjectId(driver_id), "admin_id": admin_id})
    if not driver:
        return JSONResponse(status_code=404, content={"success": False, "message": "Driver not found"})

    # Update Order
    order_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {
            "assigned_driver_id": driver["_id"],
            "assigned_driver_name": driver["name"]
        }}
    )
    
    # Update Customer History Record (Syncing data)
    customer_collection.update_one(
        {"records.order_id": ObjectId(order_id)},
        {"$set": {"records.$.driver_name": driver["name"]}}
    )

    return JSONResponse(content={"success": True, "message": "Driver updated"})

# customer.py

from typing import Optional # Add this import at the top

@customer_router.post("/update-customer")
async def update_customer(
    customer_id: str = Form(...),
    name: str = Form(...),
    # 🚀 Change: Make phone optional to prevent 422 errors if it's missing
    phone: Optional[str] = Form(None), 
    city: str = Form(...),
    landmark: str = Form(...),
    pincode: str = Form(""),
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)

    # 📋 Build update dictionary dynamically
    update_data = {
        "name": name,
        "city": city,
        "landmark": landmark,
        "pincode": pincode,
        "updated_at": datetime.utcnow()
    }
    
    # 📱 Only update phone if it was actually provided in the request
    if phone:
        update_data["phone_number"] = phone

    customer_collection.update_one(
        {"_id": ObjectId(customer_id), "admin_id": admin_id},
        {"$set": update_data}
    )
    return RedirectResponse(url="/customers?msg=Customer updated", status_code=303)