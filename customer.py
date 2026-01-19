from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from datetime import datetime
from bson import ObjectId

# Database Imports
from app.database import (
    db, customer_collection, order_collection, 
    cities_collection, admin_collection
)
from admin import get_current_admin

customer_router = APIRouter()
templates = Jinja2Templates(directory="templates")

# PURPOSE: Customer List, Search, and Filtering
@customer_router.get("/customers")
async def customer_management(
    request: Request, 
    filter_type: str = "all", 
    search: str = Query(None),
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    query = {"admin_id": admin_id}
    
    if search:
        query["$and"] = [
            {"admin_id": admin_id},
            {"$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"phone_number": {"$regex": search, "$options": "i"}}
            ]}
        ]
    
    all_matching_customers = list(customer_collection.find(query).sort("created_at", -1))
    
    processed_customers = []
    
    for c in all_matching_customers:
        c["_id"] = str(c["_id"])
        
        if c.get("records") and len(c["records"]) > 0:
            last_record = c["records"][-1]
            status = last_record.get("status", "UNKNOWN")
        else:
            status = "NO ORDERS"
            
        c["current_status"] = status

        if filter_type == "all":
            processed_customers.append(c)
        elif filter_type == "delivered" and status == "DELIVERED":
            processed_customers.append(c)
        elif filter_type == "pending" and status == "PENDING":
            processed_customers.append(c)
        elif filter_type == "in_progress" and status == "IN_PROGRESS":
            processed_customers.append(c)

    cities = list(cities_collection.find().sort("name", 1))
    
    return templates.TemplateResponse("customers.html", {
        "request": request, 
        "customers": processed_customers,
        "cities": cities,
        "active_filter": filter_type,
        "search_query": search or ""
    })

# PURPOSE: Adds a new city
@customer_router.post("/add-city")
async def add_city(city_name: str = Form(...)):
    print(f"--- [DEBUG] Adding New City: {city_name} ---")
    try:
        db["cities"].update_one(
            {"name": city_name}, 
            {"$set": {"name": city_name}}, 
            upsert=True
        )
        return RedirectResponse(url="/customers", status_code=303)
    except Exception as e:
        print(f"--- [ERROR] Failed to add city: {e} ---")
        raise HTTPException(status_code=500, detail="Database error")

# PURPOSE: Adds a new customer (including new pincode field)
@customer_router.post("/add-customer")
async def add_customer(
    request: Request, 
    name: str = Form(...), 
    phone: str = Form(...), 
    city: str = Form(...), 
    landmark: str = Form(...),
    pincode: str = Form(""), # New Field
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

# PURPOSE: Creates a new order for an existing customer
@customer_router.post("/create-order")
async def create_order(request: Request, customer_id: str = Form(...), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    cust = customer_collection.find_one({
        "_id": ObjectId(customer_id), 
        "admin_id": admin_id
    })
    
    if not cust:
        raise HTTPException(status_code=403, detail="Unauthorized access to customer")

    order_data = {
        "admin_id": admin_id,
        "customer_id": ObjectId(customer_id),
        "customer_name": cust["name"],
        "city": cust["city"],
        "status": "PENDING",
        "created_at": datetime.utcnow()
    }
    result = order_collection.insert_one(order_data)
    
    customer_collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$push": {"records": {
            "order_id": result.inserted_id,
            "date": datetime.utcnow(),
            "status": "PENDING"
        }}}
    )
    return RedirectResponse(url="/customers", status_code=303)