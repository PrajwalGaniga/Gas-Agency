# admin.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, StreamingResponse
from datetime import datetime, timedelta, timezone
import pandas as pd
import io
from bson import ObjectId

# --- INTERNAL IMPORTS ---
from auth import get_current_admin, create_access_token, get_current_driver
from app.database import (
    db, admin_collection, driver_collection, 
    customer_collection, order_collection, cities_collection,
    driver_audit_collection, driver_location_collection, change_requests_collection, daily_stats_collection, shifts_collection
)
from app.schemas import StartShiftRequest, CloseShiftRequest
from app.utils import verify_password, get_password_hash, generate_otp, send_otp_email

admin_router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.add_extension('jinja2.ext.do')

# --- CONSTANTS ---
DEVELOPER_PASSCODE = "GAS"
MASTER_EMAIL = "prajwalganiga06@gmail.com"

# --- 🚀 MANDATORY IST HELPERS ---
IST = timezone(timedelta(hours=5, minutes=30))

def to_ist(dt):
    """Converts any datetime to IST. Safely handles date objects and strings."""
    if not dt: return None
    if isinstance(dt, datetime) is False:
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def to_utc(dt):
    """Converts an aware datetime to UTC for database storage."""
    if not dt: return None
    return dt.astimezone(timezone.utc)

def ist_now():
    """Returns current time in Indian Standard Time."""
    return datetime.now(timezone.utc).astimezone(IST)

def ist_day_start(date_obj):
    """Returns the UTC equivalent of 00:00:00 IST for a given date."""
    ist_start = datetime.combine(date_obj, datetime.min.time()).replace(tzinfo=IST)
    return to_utc(ist_start)

def ist_day_end(date_obj):
    """Returns the UTC equivalent of 23:59:59 IST for a given date."""
    ist_end = datetime.combine(date_obj, datetime.max.time()).replace(tzinfo=IST)
    return to_utc(ist_end)

# Inject helpers into Jinja2 environment
templates.env.globals.update({
    "to_ist": to_ist,
    "ist_now": ist_now
})

# --- 🚀 REFACTORED ANALYTICS (GPS-BASED PROOF OF WORK) ---

def calculate_work_time(driver_id):
    """Calculates total work hours for the current IST day based on GPS Heartbeats."""
    today_start_utc = ist_day_start(ist_now().date())
    pings = list(driver_location_collection.find({
        "driver_id": ObjectId(driver_id),
        "timestamp": {"$gte": today_start_utc}
    }).sort("timestamp", 1))
    
    if not pings: return "0h 0m"
    
    total_seconds = 0
    # 🚀 IMPROVED: Increase threshold to 1 hour (3600s) to handle sparse data
    for i in range(len(pings) - 1):
        diff = (pings[i+1]["timestamp"] - pings[i]["timestamp"]).total_seconds()
        if diff < 3600: 
            total_seconds += diff
            
    return f"{int(total_seconds // 3600)}h {int((total_seconds % 3600) // 60)}m"

def get_detailed_driver_metrics(driver_id, start_date_utc, end_date_utc):
    """Computes daily analytics by grouping GPS Heartbeats and Logins with a generous threshold."""
    pings = list(driver_location_collection.find({
        "driver_id": ObjectId(driver_id),
        "timestamp": {"$gte": start_date_utc, "$lte": end_date_utc}
    }).sort("timestamp", 1))

    logins = list(driver_audit_collection.find({
        "driver_id": ObjectId(driver_id),
        "event": "LOGIN",
        "timestamp": {"$gte": start_date_utc, "$lte": end_date_utc}
    }))

    if not pings and not logins:
        return {"days": [], "summary": {"total_hours": 0, "active_days": 0, "total_deliveries": 0}}

    daily_groups = {}
    for p in pings:
        day = to_ist(p["timestamp"]).date()
        if day not in daily_groups: daily_groups[day] = {"pings": [], "logins": []}
        daily_groups[day]["pings"].append(to_ist(p["timestamp"]))

    for l in logins:
        day = to_ist(l["timestamp"]).date()
        if day not in daily_groups: daily_groups[day] = {"pings": [], "logins": []}
        daily_groups[day]["logins"].append(to_ist(l["timestamp"]))

    processed_days = []
    grand_total_seconds = 0
    grand_total_deliveries = 0

    for day_date, activity in daily_groups.items():
        p_list = sorted(activity["pings"])
        l_list = sorted(activity["logins"])
        
        day_seconds = 0
        # 🚀 THE FIX: Increased to 3600 (1 hour) to ensure sparse GPS data still counts toward work time
        for i in range(len(p_list) - 1):
            diff = (p_list[i+1] - p_list[i]).total_seconds()
            if diff < 3600: 
                day_seconds += diff
        
        grand_total_seconds += day_seconds
        day_start_utc, day_end_utc = ist_day_start(day_date), ist_day_end(day_date)
        
        deliveries_count = order_collection.count_documents({
            "assigned_driver_id": ObjectId(driver_id),
            "status": "DELIVERED",
            "delivered_at": {"$gte": day_start_utc, "$lte": day_end_utc}
        })
        grand_total_deliveries += deliveries_count

        all_act = sorted(p_list + l_list)
        processed_days.append({
            "date": day_date,
            "first_ping": all_act[0] if all_act else None,
            "last_ping": all_act[-1] if all_act else None,
            "duration": f"{int(day_seconds // 3600)}h {int((day_seconds % 3600) // 60)}m",
            "duration_seconds": day_seconds,
            "deliveries": deliveries_count
        })

    return {
        "days": sorted(processed_days, key=lambda x: x["date"], reverse=True),
        "summary": {
            "total_hours": round(grand_total_seconds / 3600, 1),
            "active_days": len(processed_days),
            "total_deliveries": grand_total_deliveries
        }
    }

# --- AUTH ROUTES ---

@admin_router.get("/signup")
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})



@admin_router.post("/complete-signup")
async def complete_signup(email: str = Form(...), otp: str = Form(...)):
    temp_user = db["temp_signups"].find_one({"email": email})
    if temp_user and temp_user.get("otp") == otp:
        admin_collection.insert_one({
            "email": email,
            "password_hash": temp_user["password_hash"],
            "created_at": datetime.now(timezone.utc)
        })
        db["temp_signups"].delete_one({"email": email})
        return {"success": True, "message": "Registration complete!"}
    return {"success": False, "message": "Invalid or expired OTP."}

@admin_router.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@admin_router.post("/login")
async def login_logic(request: Request, email: str = Form(...), password: str = Form(...)):
    user = admin_collection.find_one({"email": email})
    if user and verify_password(password, user["password_hash"]):
        access_token = create_access_token(data={"sub": str(user["_id"])})
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials."})

@admin_router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/?message=Logged out successfully", status_code=303)
    response.delete_cookie("access_token")
    return response

# admin.py additions

@admin_router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@admin_router.post("/forgot-password-request")
async def forgot_request(email: str = Form(...)):
    user = admin_collection.find_one({"email": email})
    if not user:
        return {"success": False, "message": "Email not registered."}
    
    otp = generate_otp()
    # Store OTP temporarily with 10-min expiry
    db["temp_resets"].update_one(
        {"email": email}, 
        {"$set": {"otp": otp, "created_at": datetime.now(timezone.utc)}}, 
        upsert=True
    )
    # Send OTP to the USER for password reset
    send_otp_email(email, otp) 
    return {"success": True, "message": "Security code sent to your email."}

@admin_router.post("/reset-password-finalize")
async def reset_finalize(email: str = Form(...), otp: str = Form(...), new_password: str = Form(...)):
    record = db["temp_resets"].find_one({"email": email, "otp": otp})
    if not record:
        return {"success": False, "message": "Invalid or expired code."}
    
    hashed_pw = get_password_hash(new_password)
    admin_collection.update_one({"email": email}, {"$set": {"password_hash": hashed_pw}})
    db["temp_resets"].delete_one({"email": email})
    return {"success": True, "message": "Password updated successfully."}

# admin.py

@admin_router.post("/signup-request")
async def signup_request(
    passcode: str = Form(...), 
    email: str = Form(...), 
    password: str = Form(...)
):
    # 1. Validate Developer Passcode
    if passcode != DEVELOPER_PASSCODE:
        return {"success": False, "message": "Invalid Developer Passcode."}
    
    # 2. Prevent duplicate registrations
    if admin_collection.find_one({"email": email}):
        return {"success": False, "message": "This email is already registered."}

    otp = generate_otp() #
    hashed_pw = get_password_hash(password) #
    
    # 3. Store pending signup data
    db["temp_signups"].update_one(
        {"email": email},
        {"$set": {
            "otp": otp, 
            "password_hash": hashed_pw, 
            "created_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    
    # 4. Send OTP (Directly to MASTER_EMAIL for Developer Approval)
    success = send_otp_email(MASTER_EMAIL, otp)
    
    if success:
        return {"success": True, "message": "Approval request sent to Developer."}
    else:
        # 📱 This is the message you saw in your phone screenshot
        return {"success": False, "message": "Failed to send email. Please check server logs."}

# --- DASHBOARD & DRIVERS ---

@admin_router.get("/dashboard")
async def dashboard_view(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse("/")
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    stats_list = []
    now_utc = datetime.now(timezone.utc)
    for d in drivers:
        ls = d.get("last_seen")
        ls_utc = ls.replace(tzinfo=timezone.utc) if ls and ls.tzinfo is None else ls
        stats_list.append({
            "id": str(d["_id"]),
            "name": d["name"],
            "phone": d.get("phone_number", "N/A"),
            "is_online": ls_utc and (now_utc - ls_utc).total_seconds() < 300,
            "last_seen": to_ist(ls_utc).isoformat() if ls_utc else None,
            "work_time": calculate_work_time(d["_id"]),
            "current_stock": d.get("current_stock", 0),
            "collected_cash": d.get("collected_cash", 0),
            "completed": order_collection.count_documents({"assigned_driver_id": d["_id"], "status": "DELIVERED"}),
            "pending": order_collection.count_documents({"assigned_driver_id": d["_id"], "status": "PENDING"})
        })
    stats = {
        "drivers": len(drivers), 
        "customers": customer_collection.count_documents({"admin_id": admin_id}),
        "pending": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"}),
        "unassigned": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING", "assigned_driver_id": None}),
        "in_progress": order_collection.count_documents({"admin_id": admin_id, "status": "IN_PROGRESS"}),
        "delivered": order_collection.count_documents({"admin_id": admin_id, "status": "DELIVERED"})
    }
    return templates.TemplateResponse("dashboard.html", {"request": request, "drivers": stats_list, "stats": stats})

@admin_router.get("/drivers")
async def driver_management(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    cities = list(cities_collection.find().sort("name", 1))
    stats = {"pending": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"})}
    for d in drivers:
        d["_id"] = str(d["_id"])
        d["assigned_cities"] = d.get("assigned_cities") or []
        d["total_deliveries"] = order_collection.count_documents({"assigned_driver_id": ObjectId(d["_id"]), "status": "DELIVERED"})
    return templates.TemplateResponse("drivers.html", {"request": request, "drivers": drivers, "cities": cities, "stats": stats})

@admin_router.post("/add-driver")
async def add_driver(name: str = Form(...), phone: str = Form(...), password: str = Form(...), cities: list = Form([]), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    driver_collection.insert_one({
        "admin_id": admin_id, "name": name, "phone_number": phone, 
        "password_hash": get_password_hash(password), "assigned_cities": cities, 
        "is_active": True, "created_at": datetime.now(timezone.utc)
    })
    return RedirectResponse(url="/drivers", status_code=303)

@admin_router.post("/update-driver")
async def update_driver(driver_id: str = Form(...), name: str = Form(...), phone: str = Form(...), password: str = Form(None), cities: list = Form([]), is_active: str = Form(None)):
    update_data = {"name": name, "phone_number": phone, "assigned_cities": cities, "is_active": (is_active == "true"), "last_edited_at": datetime.now(timezone.utc)}
    if password and password.strip():
        update_data["password_hash"] = get_password_hash(password)
    driver_collection.update_one({"_id": ObjectId(driver_id)}, {"$set": update_data})
    return RedirectResponse(url="/drivers", status_code=303)

@admin_router.post("/delete-driver")
async def delete_driver(driver_id: str = Form(...), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    driver_collection.delete_one({"_id": ObjectId(driver_id), "admin_id": admin_id})
    return RedirectResponse(url="/drivers?msg=Driver deleted", status_code=303)

# --- ASSIGNMENTS ---

@admin_router.get("/assignments")
async def delivery_assignments(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: 
        return RedirectResponse(url="/", status_code=303)
    
    # 1. Fetch pending orders
    pending_orders = list(order_collection.find({"admin_id": admin_id, "status": "PENDING"}))
    for order in pending_orders:
        order["_id"] = str(order["_id"])
        order["customer_id"] = str(order["customer_id"])
    
    # 2. Fetch active drivers
    active_drivers = list(driver_collection.find({"admin_id": admin_id, "is_active": True}))
    for d in active_drivers:
        d["_id"] = str(d["_id"])

    # 🚀 FIX: Calculate the 'stats' object required by the navbar
    stats = {
        "pending": order_collection.count_documents({
            "admin_id": admin_id, 
            "status": "PENDING"
        })
    }

    # 3. Pass "stats" into the context dictionary
    return templates.TemplateResponse("assignments.html", {
        "request": request, 
        "orders": pending_orders, 
        "drivers": active_drivers,
        "stats": stats  # 👈 This line prevents the UndefinedError
    })
@admin_router.post("/assign-delivery")
async def assign_delivery(order_id: str = Form(...), driver_id: str = Form(...)):
    try:
        o_id = ObjectId(order_id)
        order = order_collection.find_one({"_id": o_id})
        if not order: return {"success": False, "message": "Order not found"}
        final_driver_id, final_driver_name = None, "Unassigned"
        if driver_id == "auto":
            from customer import get_optimal_driver 
            best_driver = get_optimal_driver(order.get("admin_id"), order.get("city"))
            if best_driver: final_driver_id, final_driver_name = best_driver["_id"], best_driver["name"]
            else: return {"success": False, "message": f"No active drivers for {order.get('city')}"}
        else:
            driver = driver_collection.find_one({"_id": ObjectId(driver_id)})
            if driver: final_driver_id, final_driver_name = driver["_id"], driver["name"]
        order_collection.update_one({"_id": o_id}, {"$set": {"status": "IN_PROGRESS", "assigned_driver_id": final_driver_id, "assigned_driver_name": final_driver_name, "assigned_at": datetime.now(timezone.utc)}})
        customer_collection.update_one({"records.order_id": o_id}, {"$set": {"records.$.status": "IN_PROGRESS", "records.$.driver_name": final_driver_name}})
        return RedirectResponse(url="/assignments", status_code=303)
    except Exception as e: return {"success": False, "message": str(e)}

@admin_router.get("/admin/pending-orders")
async def pending_orders_dashboard(
    request: Request, 
    date: str = Query(None), 
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id: 
        return RedirectResponse(url="/", status_code=303)
    
    # 1. Date Filtering Logic
    now_utc = datetime.utcnow()
    target_dt = datetime.strptime(date, "%Y-%m-%d").date() if date else to_ist(now_utc).date()
    target_date_str = target_dt.strftime("%Y-%m-%d")

    # 2. Fetch Pending Orders for the specific assigned_date
    pending_orders_cursor = order_collection.find({
        "admin_id": admin_id, 
        "status": "PENDING",
        # Find orders explicitly assigned to this date, OR legacy orders missing the field but created on this date
        "$or": [
            {"assigned_date": target_date_str},
            {"assigned_date": {"$exists": False}, "created_at": {"$gte": datetime.combine(target_dt, datetime.min.time()), "$lt": datetime.combine(target_dt + timedelta(days=1), datetime.min.time())}}
        ]
    })
    
    pending_orders = list(pending_orders_cursor)
    
    # 3. Enhance Orders with Customer Info & Group by Territory (City)
    grouped_territories = {}
    
    for order in pending_orders:
        order["_id"] = str(order["_id"])
        order["customer_id"] = str(order["customer_id"])
        
        city = order.get("city", "Unknown City")
        driver_id_str = str(order.get("assigned_driver_id")) if order.get("assigned_driver_id") else "Unassigned"
        driver_name = order.get("assigned_driver_name", "Unassigned")

        # Create a unique logical group key for City + Driver combo
        group_key = f"{city}_{driver_id_str}"

        if group_key not in grouped_territories:
            grouped_territories[group_key] = {
                "city": city,
                "driver_id": driver_id_str,
                "driver_name": driver_name,
                "orders": [],
                "count": 0
            }
        
        # Populate Customer Link
        cust = customer_collection.find_one({"_id": ObjectId(order["customer_id"])})
        if cust:
            order["customer_name"] = cust.get("name", "Unknown")
            order["phone"] = cust.get("phone_number", "N/A")
            order["landmark"] = cust.get("landmark", "N/A")
        
        grouped_territories[group_key]["orders"].append(order)
        grouped_territories[group_key]["count"] += 1

    # Convert mapping to list for the template
    territory_list = list(grouped_territories.values())

    # 4. Fetch Active Drivers (For the Reschedule Dropdown) & Calculate Today's Load
    active_drivers_cursor = driver_collection.find({"admin_id": admin_id, "is_active": True})
    active_drivers = []
    
    today_str = to_ist(now_utc).date().strftime("%Y-%m-%d")

    for d in active_drivers_cursor:
        d["_id"] = str(d["_id"])
        # Calculate active load on the driver specifically for TODAY
        active_load = order_collection.count_documents({
            "assigned_driver_id": ObjectId(d["_id"]),
            "status": {"$in": ["PENDING", "IN_PROGRESS"]},
            "$or": [
                {"assigned_date": today_str},
                {"assigned_date": {"$exists": False}} # Fallback
            ]
        })
        d["today_active_load"] = active_load
        active_drivers.append(d)

    stats = {
        "pending": len(pending_orders),
        "territories": len(territory_list)
    }

    return templates.TemplateResponse("pending_orders.html", {
        "request": request, 
        "territories": territory_list, 
        "drivers": active_drivers,
        "selected_date": target_date_str,
        "selected_date_display": target_dt.strftime("%d %b %Y"),
        "stats": stats
    })

@admin_router.post("/api/reassign-order")
async def reassign_order(
    order_id: str = Form(...), 
    new_driver_id: str = Form(...), 
    target_date: str = Form(None),
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id: return {"success": False, "message": "Unauthorized"}
    try:
        o_id = ObjectId(order_id)
        order = order_collection.find_one({"_id": o_id})
        if not order: return {"success": False, "message": "Order not found"}

        final_driver_id = None
        final_driver_name = "Unassigned"
        
        if new_driver_id != "auto":
            driver = driver_collection.find_one({"_id": ObjectId(new_driver_id)})
            if driver:
                final_driver_id = driver["_id"]
                final_driver_name = driver["name"]

        # Component 7: Date strictness. If no date provided, default to today IST
        now_utc = datetime.utcnow()
        t_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else to_ist(now_utc).date()
        
        # Check if actually rescheduled
        orig_assigned_date = order.get("assigned_date")
        if orig_assigned_date and isinstance(orig_assigned_date, datetime):
            orig_assigned_date = orig_assigned_date.date()
        else:
            orig_date_utc = order.get("created_at")
            orig_assigned_date = to_ist(orig_date_utc).date() if orig_date_utc else to_ist(now_utc).date()

        is_rescheduled = True if t_date_obj != orig_assigned_date or order.get("is_rescheduled") else False
        
        # We store assigned_date as a datetime representing the start of that day in UTC for easier querying later if needed, 
        # or just store string "YYYY-MM-DD". Let's store as a string for precise matching without timezone fuzz.
        assigned_date_str = t_date_obj.strftime("%Y-%m-%d")

        update_payload = {
            "status": "IN_PROGRESS", 
            "assigned_driver_id": final_driver_id, 
            "assigned_driver_name": final_driver_name, 
            "assigned_at": now_utc,
            "assigned_date": assigned_date_str,
        }

        if is_rescheduled:
            update_payload["is_rescheduled"] = True
            if not order.get("original_date"):
                update_payload["original_date"] = orig_assigned_date.strftime("%Y-%m-%d")

        order_collection.update_one(
            {"_id": o_id}, 
            {"$set": update_payload}
        )
        customer_collection.update_one(
            {"records.order_id": o_id}, 
            {"$set": {
                "records.$.status": "IN_PROGRESS", 
                "records.$.driver_name": final_driver_name
            }}
        )
        return RedirectResponse(url="/admin/pending-orders", status_code=303)
    except Exception as e:
        return {"success": False, "message": str(e)}

@admin_router.post("/admin/orders/batch-reschedule")
async def batch_reschedule_orders(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    """Handles mass rescheduling from the Command Center logic"""
    if not admin_id:
        return {"success": False, "message": "Unauthorized"}
    try:
        data = await request.json()
        order_ids = data.get("order_ids", [])
        new_driver_id = data.get("new_driver_id")
        target_date = data.get("target_date")

        if not order_ids or not target_date:
            return {"success": False, "message": "Missing required fields"}

        final_driver_id = None
        final_driver_name = "Unassigned"
        
        if new_driver_id and new_driver_id != "auto":
            driver = driver_collection.find_one({"_id": ObjectId(new_driver_id)})
            if driver:
                final_driver_id = driver["_id"]
                final_driver_name = driver["name"]
        
        now_utc = datetime.utcnow()
        t_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        assigned_date_str = t_date_obj.strftime("%Y-%m-%d")

        success_count = 0
        for o_id_str in order_ids:
            o_id = ObjectId(o_id_str)
            order = order_collection.find_one({"_id": o_id})
            if not order: continue

            # Date calculation
            orig_assigned_date = order.get("assigned_date")
            if orig_assigned_date and isinstance(orig_assigned_date, datetime):
                orig_assigned_date = orig_assigned_date.date()
            else:
                orig_date_utc = order.get("created_at")
                orig_assigned_date = to_ist(orig_date_utc).date() if orig_date_utc else to_ist(now_utc).date()

            is_rescheduled = True if t_date_obj != orig_assigned_date or order.get("is_rescheduled") else False

            update_payload = {
                "status": "IN_PROGRESS", 
                "assigned_driver_id": final_driver_id, 
                "assigned_driver_name": final_driver_name, 
                "assigned_at": now_utc,
                "assigned_date": assigned_date_str,
            }

            if is_rescheduled:
                update_payload["is_rescheduled"] = True
                if not order.get("original_date"):
                    update_payload["original_date"] = orig_assigned_date.strftime("%Y-%m-%d")

            result = order_collection.update_one({"_id": o_id}, {"$set": update_payload})
            if result.modified_count > 0:
                customer_collection.update_one(
                    {"records.order_id": o_id}, 
                    {"$set": {
                        "records.$.status": "IN_PROGRESS", 
                        "records.$.driver_name": final_driver_name
                    }}
                )
                success_count += 1
                
        return {"success": True, "message": f"Successfully rescheduled {success_count} orders"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- TRACKING & AUDIT ---

@admin_router.get("/track/{driver_id}")
async def track_driver_page(request: Request, driver_id: str, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse("/")
    driver = driver_collection.find_one({"_id": ObjectId(driver_id), "admin_id": admin_id})
    if not driver: return RedirectResponse("/dashboard")
    return templates.TemplateResponse("DriverTracking.html", {"request": request, "driver_name": driver["name"], "driver_id": driver_id})

@admin_router.get("/api/track-data/{driver_id}")
async def get_tracking_data(
    driver_id: str, 
    date: str = Query(None), 
    admin_id: ObjectId = Depends(get_current_admin)
):
    """
    Unified Telemetry API: Serves pre-resolved addresses and accurate 
    delivery timestamps to the tracking dashboard.
    """
    if not admin_id: raise HTTPException(status_code=401)
    try:
        d_oid = ObjectId(driver_id)
        target_date = datetime.strptime(date, "%Y-%m-%d").date() if date else ist_now().date()
        start_utc, end_utc = ist_day_start(target_date), ist_day_end(target_date)
        
        driver = driver_collection.find_one({"_id": d_oid})
        
        # 1. Fetch Path with PRE-RESOLVED addresses from database
        loc_cursor = driver_location_collection.find({
            "driver_id": d_oid, 
            "timestamp": {"$gte": start_utc, "$lte": end_utc}
        }).sort("timestamp", 1)
        
        path = [
            {
                "lat": float(l["lat"]), 
                "lng": float(l["lng"]), 
                "time": to_ist(l["timestamp"]).strftime("%I:%M %p"),
                "address": l.get("address", "Log Active") # 🚀 Pull address from DB
            } for l in loc_cursor if l.get("lat") and l.get("lng")
        ]

        # 2. Fetch Delivered Markers with correct timestamps
        orders = list(order_collection.find({
            "assigned_driver_id": d_oid, 
            "$or": [
                {"created_at": {"$gte": start_utc, "$lte": end_utc}},
                {"delivered_at": {"$gte": start_utc, "$lte": end_utc}}
            ]
        }))
        
        markers = []
        for o in orders:
            cust = customer_collection.find_one({"_id": o["customer_id"]})
            if cust and cust.get("verified_lat"):
                d_time_ist = to_ist(o.get("delivered_at"))
                markers.append({
                    "lat": float(cust["verified_lat"]),
                    "lng": float(cust["verified_lng"]),
                    "status": o["status"],
                    "customer": cust["name"],
                    "address": cust.get("landmark", "N/A"),
                    "delivered_time": d_time_ist.strftime("%I:%M %p") if d_time_ist else "Pending" # 🚀 Fix N/A
                })

        return {
            "success": True,
            "driver_name": driver["name"],
            "selected_date_raw": target_date.strftime("%Y-%m-%d"),
            "current_pos": {
                "lat": float(driver.get("current_lat")) if driver.get("current_lat") else None,
                "lng": float(driver.get("current_lng")) if driver.get("current_lng") else None,
                "last_seen": to_ist(driver.get("last_seen")).strftime("%I:%M %p") if driver.get("last_seen") else "Offline",
                "address": driver.get("current_address", "Resolving satellite data...") # 🚀 Live address
            },
            "path": path,
            "markers": markers,
            "date_label": target_date.strftime("%d %b %Y")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@admin_router.get("/driver-audit")
async def driver_audit_page(request: Request, period: str = Query(None), date: str = Query(None), driver_id: str = Query(None), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse("/")
    now_ist = ist_now()
    if date:
        try:
            target_dt = datetime.strptime(date, "%Y-%m-%d").date()
            start_utc, end_utc = ist_day_start(target_dt), ist_day_end(target_dt)
            active_view = "date"
        except: date, period = None, "24h"
    if not date:
        period = period or "24h"
        days_back = {"24h": 1, "1w": 7, "1m": 30}.get(period, 1)
        start_utc = ist_day_start((now_ist - timedelta(days=days_back-1)).date())
        end_utc, active_view = datetime.now(timezone.utc), period

    drivers = list(driver_collection.find({"admin_id": admin_id}))
    summary_totals = {
        "active_days": 0, "total_hours": 0, "total_deliveries": 0, "pending_requests": 0,
        "pending_orders": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"})
    }
    table_data = []
    for d in drivers:
        if driver_id and str(d["_id"]) != driver_id: continue
        metrics = get_detailed_driver_metrics(d["_id"], start_utc, end_utc)
        for day in metrics["days"]:
            table_data.append({"driver_name": d["name"], **day})
            summary_totals["total_hours"] += (day.get("duration_seconds", 0) / 3600)
        summary_totals["total_deliveries"] += metrics["summary"]["total_deliveries"]

    req_query = {"admin_id": admin_id, "timestamp": {"$gte": start_utc, "$lte": end_utc}}
    requests_cursor = change_requests_collection.find(req_query).sort("timestamp", -1)
    processed_requests = []
    for req in requests_cursor:
        cust = customer_collection.find_one({"_id": req.get("customer_id")})
        req["customer_name"] = cust["name"] if cust else "Unknown"
        req["customer_id_str"] = str(req.get("customer_id", ""))
        if req["status"] == "PENDING": summary_totals["pending_requests"] += 1
        processed_requests.append(req)

    summary_totals["total_hours"] = round(summary_totals["total_hours"], 1)
    unique_dates = set([r["date"] for r in table_data])
    summary_totals["active_days"] = len(unique_dates)
    summary_totals["avg_hours"] = round(summary_totals["total_hours"] / len(unique_dates), 1) if unique_dates else 0
    table_data.sort(key=lambda x: x["date"], reverse=True)

    return templates.TemplateResponse("DriverAudit.html", {
        "request": request, "audits": table_data, "summary": summary_totals, "requests": processed_requests, 
        "drivers": drivers, "active_view": active_view, "selected_date": date or now_ist.strftime("%Y-%m-%d"), "selected_driver": driver_id
    })

@admin_router.get("/export-driver-audit")
async def export_driver_audit(period: str = "1w", admin_id: ObjectId = Depends(get_current_admin)):
    now_ist = ist_now()
    days_back = {"24h": 1, "1w": 7, "1m": 30}.get(period, 7)
    start_date_utc = ist_day_start((now_ist - timedelta(days=days_back-1)).date())
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    all_rows = []
    for d in drivers:
        metrics = get_detailed_driver_metrics(d["_id"], start_date_utc, datetime.now(timezone.utc))
        for day in metrics["days"]: 
            all_rows.append({
                "Driver": d["name"], "Date": day["date"].strftime("%Y-%m-%d"), 
                "First Active": day["first_ping"].strftime("%I:%M %p"), "Last Active": day["last_ping"].strftime("%I:%M %p"), 
                "Work Duration": day["duration"], "Deliveries": day["deliveries"]
            })
    df = pd.DataFrame(all_rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
    output.seek(0)
    return StreamingResponse(output, headers={"Content-Disposition": f"attachment; filename=DriverAudit_{period}.xlsx"}, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@admin_router.post("/api/resolve-request")
async def resolve_change_request(request_id: str = Form(...), action: str = Form(...), remarks: str = Form(""), admin_id: ObjectId = Depends(get_current_admin)):
    status = "APPROVED" if action == "approve" else "REJECTED"
    
    # 1. Fetch the request
    req = change_requests_collection.find_one({"_id": ObjectId(request_id), "admin_id": admin_id})
    if not req:
        return RedirectResponse("/driver-audit?error=Request not found", status_code=303)
        
    # 2. Update the Request Status
    change_requests_collection.update_one(
        {"_id": ObjectId(request_id)}, 
        {"$set": {"status": status, "admin_remarks": remarks, "decision_timestamp": datetime.now(timezone.utc)}}
    )
    
    # 3. Apply the changes if Approved
    if status == "APPROVED":
        if req.get("request_type") == "LOCATION_UPDATE":
            # Update Customer Coordinates
            customer_collection.update_one(
                {"_id": req["customer_id"]},
                {"$set": {
                    "verified_lat": req["lat"],
                    "verified_lng": req["lng"],
                    "active_order_lock": False,
                    "last_order_date": datetime.now(timezone.utc)
                }}
            )
            # If an order is tied, mark it DELIVERED
            if req.get("order_id"):
                order_collection.update_one(
                    {"_id": req["order_id"]},
                    {"$set": {"status": "DELIVERED", "is_flagged": True, "delivered_at": datetime.now(timezone.utc)}}
                )
                customer_collection.update_one(
                    {"_id": req["customer_id"], "records.order_id": req["order_id"]},
                    {"$set": {"records.$.status": "DELIVERED"}}
                )
        elif req.get("request_type") == "ADDRESS":
            customer_collection.update_one({"_id": req["customer_id"]}, {"$set": {"landmark": req["new_value"]}})
        elif req.get("request_type") == "PHONE":
            customer_collection.update_one({"_id": req["customer_id"]}, {"$set": {"phone_number": req["new_value"]}})
            
    elif status == "REJECTED":
        if req.get("request_type") == "LOCATION_UPDATE" and req.get("order_id"):
            # Mark the order as CANCELLED or keep it PENDING?
            # Revert to PENDING so driver has to redo it properly or another driver is assigned
            order_collection.update_one(
                {"_id": req["order_id"]},
                {"$set": {"status": "PENDING"}} # Revert
            )
            customer_collection.update_one(
                {"_id": req["customer_id"], "records.order_id": req["order_id"]},
                {"$set": {"records.$.status": "PENDING"}}
            )
            customer_collection.update_one(
                {"_id": req["customer_id"]},
                {"$set": {"active_order_lock": False}}
            )

    return RedirectResponse("/driver-audit?msg=Request updated", status_code=303)

# --- REPORTS & STATISTICS ---

@admin_router.get("/reports")
async def reports_page(request: Request, period: str = "24h", admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    days = {"24h": 1, "1w": 7, "1m": 30}.get(period, 1)
    threshold_utc = datetime.now(timezone.utc) - timedelta(days=days)
    recent_orders = list(order_collection.find({"admin_id": admin_id, "created_at": {"$gte": threshold_utc}}))
    for o in recent_orders: o["_id"] = str(o["_id"])
    summary = {
        "total": len(recent_orders), 
        "delivered": len([o for o in recent_orders if o.get("status") == "DELIVERED"]), 
        "pending": len([o for o in recent_orders if o.get("status") == "PENDING"]), 
        "in_progress": len([o for o in recent_orders if o.get("status") == "IN_PROGRESS"])
    }
    stats = {"pending": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"})}
    return templates.TemplateResponse("reports.html", {"request": request, "summary": summary, "period": period, "orders": recent_orders, "stats": stats})

@admin_router.get("/export-report")
async def export_report(period: str = "24h", admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: raise HTTPException(status_code=403)
    days = {"24h": 1, "1w": 7, "1m": 30}.get(period, 1)
    threshold_utc = datetime.now(timezone.utc) - timedelta(days=days)
    orders = list(order_collection.find({"admin_id": admin_id, "created_at": {"$gte": threshold_utc}}))
    export_data = [{"Order ID": str(o["_id"]), "Customer": o.get("customer_name"), "Status": o.get("status"), "Delivered Time": to_ist(o.get("delivered_at")).strftime("%Y-%m-%d %H:%M") if o.get("delivered_at") else "—"} for o in orders]
    df = pd.DataFrame(export_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
# admin.py

@admin_router.get("/reconciliation")
async def reconciliation_page(request: Request, date: str = Query(None), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    
    target_date = datetime.strptime(date, "%Y-%m-%d").date() if date else ist_now().date()
    start_utc, end_utc = ist_day_start(target_date), ist_day_end(target_date)
    
    drivers = list(driver_collection.find({"admin_id": admin_id, "is_active": True}))
    reconciliation_data = []
    
    for d in drivers:
        # Get all delivered orders for this day
        delivered_orders = list(order_collection.find({
            "assigned_driver_id": d["_id"],
            "status": "DELIVERED",
            "delivered_at": {"$gte": start_utc, "$lte": end_utc}
        }))
        
        expected_cash_orders = [o for o in delivered_orders if o.get("payment_mode", "CASH") == "CASH"]
        expected_upi_orders = [o for o in delivered_orders if o.get("payment_mode") == "UPI"]
        
        # Typically gas cylinder cost is fixed, but let's assume it's stored in order or a constant $1000 for demo
        CYLINDER_PRICE = 900 
        expected_cash = len(expected_cash_orders) * CYLINDER_PRICE
        
        # Assuming we track reported_cash from the driver app side (or we just use expected for now)
        reported_cash = d.get("collected_cash", 0) # Real-world this would be from a daily tally
        
        reconciliation_data.append({
            "driver_name": d["name"],
            "total_delivered": len(delivered_orders),
            "cash_deliveries": len(expected_cash_orders),
            "upi_deliveries": len(expected_upi_orders),
            "expected_cash": expected_cash,
            "reported_cash": reported_cash,
            "difference": reported_cash - expected_cash
        })
        
    return templates.TemplateResponse("reports.html", { # For now reuse reports.html or create a simplified reconciliation view
        "request": request,
        "date_label": target_date.strftime("%d %b %Y"),
        "reconciliation": reconciliation_data
    })
    
# admin.py

@admin_router.get("/profile")
async def profile_view(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: 
        return RedirectResponse(url="/", status_code=303)
        
    admin = admin_collection.find_one({"_id": admin_id})
    my_drivers = list(driver_collection.find({"admin_id": admin_id}))
    
    # 📊 Metrics Calculation
    total_orders = order_collection.count_documents({"admin_id": admin_id})
    delivered_orders = order_collection.count_documents({"admin_id": admin_id, "status": "DELIVERED"})
    
    # 🚀 FIX: Calculate pending orders for the navbar notification badge
    pending_orders = order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"})
    
    success_rate = round((delivered_orders / total_orders * 100), 1) if total_orders > 0 else 0
    account_age = (datetime.now(timezone.utc) - admin["created_at"].replace(tzinfo=timezone.utc)).days if admin.get("created_at") else 0
    driver_efficiency = round(delivered_orders / len(my_drivers), 1) if my_drivers else 0

    stats = {
        "total_orders": total_orders,
        "success_rate": success_rate,
        "account_age": account_age,
        "efficiency": driver_efficiency,
        "active_drivers": len([d for d in my_drivers if d.get("is_active")]),
        "pending": pending_orders, # 👈 THIS PREVENTS THE 500 ERROR
        "level": "Gold" if delivered_orders > 100 else "Silver" # Example logic
    }

    # Process Driver List
    for d in my_drivers:
        d["_id"] = str(d["_id"])
        reg_date_ist = to_ist(d.get("created_at"))
        d["date_str"] = reg_date_ist.strftime("%d %b %Y") if reg_date_ist else "N/A"

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "admin": admin,
        "drivers": my_drivers,
        "stats": stats
    })

@admin_router.post("/update-profile")
async def update_profile(phone: str = Form(None), age: str = Form(None), agency_name: str = Form(None), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    admin_collection.update_one({"_id": admin_id}, {"$set": {"phone": phone, "age": age, "agency_name": agency_name, "updated_at": datetime.now(timezone.utc)}})
    return RedirectResponse(url="/profile", status_code=303)

# admin.py

@admin_router.get("/download-template")
async def download_template(admin_id: ObjectId = Depends(get_current_admin)):
    """Serves a professional Excel template with placeholders."""
    if not admin_id: raise HTTPException(status_code=401)
    
    # Create template structure
    df = pd.DataFrame({
        "consumer_id": [1000001, 1000002],
        "name": ["John Doe", "Jane Smith"],
        "phone_number": ["9876543210", "7001122334"],
        "city": ["Udupi", "Mangalore"],
        "landmark": ["Near City Bus Stand", "Opposite Mall"],
        "pincode": ["576101", "575001"]
    })
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Customer_Import')
    output.seek(0)
    
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=GasFlow_Import_Template.xlsx"}
    )

@admin_router.post("/upload-customers")
async def upload_customers(
    file: UploadFile = File(...), 
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id: return {"summary": {"error": "Unauthorized"}}
    
    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content), dtype=str) if file.filename.endswith('.xlsx') else pd.read_csv(io.BytesIO(content), dtype=str)
        
        # 🛡️ VALIDATION: Check for required columns
        required = ["consumer_id", "name", "phone_number", "city", "landmark", "pincode"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            return {"summary": {"error": f"Missing columns: {', '.join(missing)}"}}

        total_processed = len(df)
        success_count = 0
        duplicate_count = 0
        error_count = 0
        new_cities = set()
        
        errors = []
        duplicates = []

        # Get existing cities to minimize DB calls during the loop
        existing_cities = {c["name"].lower(): c["name"] for c in cities_collection.find()}

        for index, row in df.iterrows():
            row_num = index + 2 # Header is row 1
            
            if pd.isna(row.get('consumer_id')) or pd.isna(row.get('name')) or pd.isna(row.get('phone_number')) or pd.isna(row.get('city')) or \
               str(row.get('consumer_id')).strip() == "nan" or str(row.get('name')).strip() == "nan" or str(row.get('phone_number')).strip() == "nan" or str(row.get('city')).strip() == "nan":
                error_count += 1
                errors.append({"row": row_num, "reason": "Missing mandatory consumer_id/name/phone/city"})
                continue

            try:
                c_str = str(row['consumer_id']).replace(".0", "").strip()
                c_id_val = int(c_str)
                if len(str(c_id_val)) > 7:
                    error_count += 1
                    errors.append({"row": row_num, "reason": "Consumer ID exceeds 7 digits"})
                    continue
            except ValueError:
                error_count += 1
                errors.append({"row": row_num, "reason": "Consumer ID must be numeric"})
                continue

            if customer_collection.find_one({"consumer_id": c_id_val}):
                duplicate_count += 1
                duplicates.append(c_id_val)
                continue

            city_name = str(row['city']).strip()
            city_lower = city_name.lower()
            if city_lower not in existing_cities:
                db["cities"].update_one(
                    {"name": {"$regex": f"^{city_name}$", "$options": "i"}},
                    {"$set": {"name": city_name}},
                    upsert=True
                )
                existing_cities[city_lower] = city_name
                new_cities.add(city_name)
            else:
                city_name = existing_cities[city_lower] # Use proper case

            landmark_val = str(row['landmark']).strip() if pd.notna(row['landmark']) and str(row['landmark']).strip() != "nan" else ""
            pincode_val = str(row['pincode']).replace(".0", "").strip() if pd.notna(row['pincode']) and str(row['pincode']).strip() != "nan" else ""

            customer_collection.insert_one({
                "admin_id": admin_id,
                "consumer_id": c_id_val,
                "name": str(row['name']).strip(),
                "phone_number": str(row['phone_number']).replace(".0", "").strip(),
                "city": city_name,
                "landmark": landmark_val,
                "pincode": pincode_val,
                "verified_lat": None, "verified_lng": None, "records": [],
                "active_order_lock": False,
                "created_at": datetime.utcnow()
            })
            success_count += 1

        return {
            "summary": {
                "total_processed": total_processed,
                "success_count": success_count,
                "duplicate_count": duplicate_count,
                "error_count": error_count,
                "new_cities": list(new_cities)
            },
            "errors": errors,
            "duplicates": duplicates
        }

    except Exception as e:
        return {"summary": {"error": f"Upload failed: {str(e)}"}}

# --- SHIFT & INVENTORY MANAGEMENT ---

@admin_router.get("/inventory")
async def inventory_management(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse("/")
    
    drivers = list(driver_collection.find({"admin_id": admin_id, "is_active": True}))
    
    shift_data = []
    total_agency_full = 0
    total_agency_empty = 0
    total_agency_cash = 0
    
    # Map open shifts by driver_id for quick lookup
    open_shifts = {s["driver_id"]: s for s in shifts_collection.find({"admin_id": str(admin_id), "status": "OPEN"})}
    
    for driver in drivers:
        d_id = str(driver["_id"])
        shift = open_shifts.get(d_id)
        
        if shift:
            # Calculate current stock on truck
            current_full = shift["load_departure"]["full"] - shift["load_return"]["full"]
            current_empty = shift["load_departure"]["empty"] + shift["load_return"]["empty"]
            
            total_agency_full += current_full
            total_agency_empty += current_empty
            total_agency_cash += shift.get("financials", {}).get("expected_cash", 0)
            
            shift_data.append({
                "shift_id": str(shift["_id"]),
                "driver_id": d_id,
                "driver_name": driver["name"],
                "status": "OPEN",
                "initial_full": shift["load_departure"]["full"],
                "current_full": current_full,
                "current_empty": current_empty,
                "expected_cash": shift.get("financials", {}).get("expected_cash", 0),
                "upi_total": shift.get("financials", {}).get("upi_total", 0)
            })
        else:
            shift_data.append({
                "shift_id": None,
                "driver_id": d_id,
                "driver_name": driver["name"],
                "status": "CLOSED",
                "initial_full": 0,
                "current_full": 0,
                "current_empty": 0,
                "expected_cash": 0,
                "upi_total": 0
            })
        
    stats = {
        "pending": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"}),
        "agency_full": total_agency_full,
        "agency_empty": total_agency_empty,
        "agency_cash": total_agency_cash
    }
    
    drivers = list(driver_collection.find({"admin_id": admin_id, "is_active": True}))
    for d in drivers: d["_id"] = str(d["_id"])
    
    return templates.TemplateResponse("inventory_management.html", {
        "request": request,
        "shift_data": shift_data,
        "drivers": drivers,
        "stats": stats
    })

@admin_router.post("/shifts/start")
async def start_shift(driver_id: str = Form(...), full_cylinders: int = Form(...), empty_cylinders: int = Form(0), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse("/")
    
    # Close any existing open shifts for this driver
    shifts_collection.update_many(
        {"driver_id": driver_id, "status": "OPEN"},
        {"$set": {"status": "CLOSED", "closed_at": datetime.now(timezone.utc)}}
    )
    
    shifts_collection.insert_one({
        "admin_id": str(admin_id),
        "driver_id": driver_id,
        "date": datetime.now(timezone.utc),
        "status": "OPEN",
        "load_departure": {"full": full_cylinders, "empty": empty_cylinders},
        "load_return": {"full": 0, "empty": 0},
        "financials": {"expected_cash": 0.0, "actual_cash": 0.0, "upi_total": 0.0}
    })
    
    return RedirectResponse(url="/inventory?msg=Shift Started", status_code=303)

@admin_router.post("/shifts/close")
async def close_shift(shift_id: str = Form(...), actual_cash: float = Form(...), actual_full: int = Form(...), actual_empty: int = Form(...), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse("/")
    
    shifts_collection.update_one(
        {"_id": ObjectId(shift_id), "admin_id": str(admin_id), "status": "OPEN"},
        {"$set": {
            "status": "CLOSED",
            "closed_at": datetime.now(timezone.utc),
            "load_return.full": actual_full,
            "load_return.empty": actual_empty,
            "financials.actual_cash": actual_cash
        }}
    )
    
    return RedirectResponse(url="/inventory?msg=Shift Closed", status_code=303)