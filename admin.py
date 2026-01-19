# admin.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, StreamingResponse
from datetime import datetime, timedelta
import pandas as pd
import io
from bson import ObjectId

# --- INTERNAL IMPORTS ---
# 1. Auth imports from the NEW auth.py
from auth import get_current_admin, create_access_token ,get_current_driver

# 2. Database imports
from app.database import (
    db, admin_collection, driver_collection, 
    customer_collection, order_collection, cities_collection,
    driver_audit_collection, driver_location_collection
)

# 3. Utils imports
from app.utils import verify_password, get_password_hash, generate_otp, send_otp_email

admin_router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.add_extension('jinja2.ext.do')
# --- CONSTANTS ---
DEVELOPER_PASSCODE = "GAS"
MASTER_EMAIL = "prajwalganiga06@gmail.com"

# --- HELPER FUNCTIONS ---

# PURPOSE: Helper to calculate total working hours for the current day
def calculate_work_time(driver_id):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    logs = list(driver_audit_collection.find({
        "driver_id": ObjectId(driver_id),
        "timestamp": {"$gte": today}
    }).sort("timestamp", 1))
    
    total_seconds = 0
    last_login = None
    
    for log in logs:
        if log["event"] == "LOGIN":
            last_login = log["timestamp"]
        elif log["event"] == "LOGOUT" and last_login:
            total_seconds += (log["timestamp"] - last_login).total_seconds()
            last_login = None
            
    # If currently online (no logout log yet), count time from last login to now
    if last_login:
        total_seconds += (datetime.utcnow() - last_login).total_seconds()
        
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    return f"{hours}h {minutes}m"

# --- AUTH ROUTES ---

@admin_router.get("/signup")
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@admin_router.post("/signup-request")
async def signup_request(
    request: Request, 
    email: str = Form(...), 
    password: str = Form(...), 
    passcode: str = Form(...)
):
    if passcode != DEVELOPER_PASSCODE:
        return {"success": False, "message": "Invalid Developer Passcode."}
    
    if admin_collection.find_one({"email": email}):
        return {"success": False, "message": "Email already registered."}

    otp = generate_otp()
    hashed_pw = get_password_hash(password)
    
    db["temp_signups"].update_one(
        {"email": email}, 
        {"$set": {"otp": otp, "password_hash": hashed_pw, "created_at": datetime.utcnow()}}, 
        upsert=True
    )
    
    send_otp_email(MASTER_EMAIL, otp)
    return {"success": True, "message": "Approval OTP sent to Master Admin."}

@admin_router.post("/complete-signup")
async def complete_signup(email: str = Form(...), otp: str = Form(...)):
    temp_user = db["temp_signups"].find_one({"email": email})
    
    if temp_user and temp_user.get("otp") == otp:
        admin_collection.insert_one({
            "email": email,
            "password_hash": temp_user["password_hash"],
            "created_at": datetime.utcnow()
        })
        db["temp_signups"].delete_one({"email": email})
        return {"success": True, "message": "Registration complete! You can now login."}
    
    return {"success": False, "message": "Invalid or expired OTP."}

@admin_router.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@admin_router.post("/login")
async def login_logic(request: Request, email: str = Form(...), password: str = Form(...)):
    user = admin_collection.find_one({"email": email})
    
    if user and verify_password(password, user["password_hash"]):
        # USE IMPORTED FUNCTION FROM AUTH.PY
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

# --- PASSWORD RESET ROUTES ---

@admin_router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@admin_router.post("/send-otp")
async def send_otp(request: Request, email: str = Form(...)):
    user = admin_collection.find_one({"email": email})
    if not user:
        return templates.TemplateResponse("forgot_password.html", {"request": request, "error": "Email not found."})

    otp = generate_otp()
    admin_collection.update_one({"email": email}, {"$set": {"reset_otp": otp}})

    if send_otp_email(email, otp):
        return templates.TemplateResponse("verify_otp.html", {"request": request, "email": email})
    
    return templates.TemplateResponse("forgot_password.html", {"request": request, "error": "Failed to send OTP."})

@admin_router.post("/verify-otp")
async def verify_otp(request: Request, email: str = Form(...), otp: str = Form(...)):
    user = admin_collection.find_one({"email": email})
    if user and user.get("reset_otp") == otp:
        return templates.TemplateResponse("reset_password.html", {"request": request, "email": email})
    
    return templates.TemplateResponse("verify_otp.html", {"request": request, "email": email, "error": "Invalid OTP."})

@admin_router.post("/reset-password")
async def reset_password_logic(request: Request, email: str = Form(...), new_password: str = Form(...)):
    hashed_pwd = get_password_hash(new_password)
    admin_collection.update_one(
        {"email": email},
        {"$set": {"password_hash": hashed_pwd}, "$unset": {"reset_otp": ""}}
    )
    return templates.TemplateResponse("login.html", {"request": request, "message": "✅ Password reset successful!"})

# --- DASHBOARD & DRIVERS ---

@admin_router.get("/dashboard")
async def dashboard_view(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: 
        return RedirectResponse("/")
    
    # 1. Fetch all drivers for this admin
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    stats_list = []
    
    for d in drivers:
        is_online = (datetime.utcnow() - d.get("last_seen", datetime.min)).total_seconds() < 300
        
        stats_list.append({
            "id": str(d["_id"]),
            "name": d["name"],
            "phone": d.get("phone_number", "N/A"),
            "is_online": is_online,
            "last_seen": d.get("last_seen"),
            "work_time": calculate_work_time(d["_id"]),
            "completed": order_collection.count_documents({"assigned_driver_id": d["_id"], "status": "DELIVERED"}),
            # This only counts orders ALREADY assigned to this driver
            "pending": order_collection.count_documents({"assigned_driver_id": d["_id"], "status": "PENDING"})
        })
    
    # 2. Calculate system-wide stats
    total_drivers = len(drivers)
    total_customers = customer_collection.count_documents({"admin_id": admin_id})
    
    # Total Pending in system
    all_pending_orders = order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"})
    
    # NEW: Calculate Unassigned Pending Orders specifically
    unassigned_pending = order_collection.count_documents({
        "admin_id": admin_id, 
        "status": "PENDING", 
        "assigned_driver_id": None # No driver assigned yet
    })

    in_progress_orders = order_collection.count_documents({"admin_id": admin_id, "status": "IN_PROGRESS"})
    delivered_orders = order_collection.count_documents({"admin_id": admin_id, "status": "DELIVERED"})
    
    stats = {
        "drivers": len(drivers),
        "customers": customer_collection.count_documents({"admin_id": admin_id}),
        "pending": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"}),
        # NEW: Find orders that are PENDING but have NO DRIVER
        "unassigned": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING", "assigned_driver_id": None}),
        "in_progress": order_collection.count_documents({"admin_id": admin_id, "status": "IN_PROGRESS"}),
        "delivered": order_collection.count_documents({"admin_id": admin_id, "status": "DELIVERED"})
    }
    
    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request, 
            "drivers": stats_list,
            "stats": stats,
            "message": request.query_params.get("message")
        }
    )
@admin_router.get("/drivers")
async def driver_management(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    cities = list(cities_collection.find().sort("name", 1))
    
    for d in drivers:
        d["_id"] = str(d["_id"])
        if "assigned_cities" not in d or d["assigned_cities"] is None:
            d["assigned_cities"] = []
            
        d["total_deliveries"] = order_collection.count_documents({
            "assigned_driver_id": ObjectId(d["_id"]),
            "status": "DELIVERED"
        })
    
    return templates.TemplateResponse("drivers.html", {
        "request": request,
        "drivers": drivers,
        "cities": cities
    })

@admin_router.post("/add-driver")
async def add_driver(
    request: Request, name: str = Form(...), phone: str = Form(...), 
    password: str = Form(...), cities: list = Form([]),
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    driver_collection.insert_one({
        "admin_id": admin_id,
        "name": name,
        "phone_number": phone,
        "password_hash": get_password_hash(password),
        "assigned_cities": cities,
        "is_active": True,
        "created_at": datetime.utcnow()
    })
    return RedirectResponse(url="/drivers", status_code=303)

@admin_router.post("/update-driver")
async def update_driver(
    driver_id: str = Form(...), name: str = Form(...), 
    phone: str = Form(...), password: str = Form(None), 
    cities: list = Form([]), is_active: str = Form(None)
):
    new_status = True if is_active == "true" else False
    
    update_data = {
        "name": name,
        "phone_number": phone,
        "assigned_cities": cities,
        "is_active": new_status,
        "last_edited_at": datetime.utcnow()
    }
    
    if password and password.strip():
        update_data["password_hash"] = get_password_hash(password)
        
    driver_collection.update_one({"_id": ObjectId(driver_id)}, {"$set": update_data})
    return RedirectResponse(url="/drivers", status_code=303)

@admin_router.post("/delete-driver")
async def delete_driver(request: Request, driver_id: str = Form(...), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    driver_collection.delete_one({
        "_id": ObjectId(driver_id), 
        "admin_id": admin_id
    })
    return RedirectResponse(url="/drivers?msg=Driver deleted", status_code=303)

# --- ASSIGNMENTS ---

# admin.py

@admin_router.get("/assignments")
async def delivery_assignments(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)

    # 1. Fetch only PENDING orders belonging to THIS admin
    pending_orders = list(order_collection.find({"admin_id": admin_id, "status": "PENDING"}))
    for order in pending_orders:
        order["_id"] = str(order["_id"])
        order["customer_id"] = str(order["customer_id"])

    # 2. Fetch ACTIVE drivers and stringify everything for JSON/Template safety
    active_drivers = list(driver_collection.find({"admin_id": admin_id, "is_active": True}))
    for driver in active_drivers:
        driver["_id"] = str(driver["_id"])
        # Stringify any datetime objects to prevent 500 Serialization Errors
        for key, value in driver.items():
            if isinstance(value, datetime):
                driver[key] = value.isoformat()

    return templates.TemplateResponse("assignments.html", {
        "request": request,
        "orders": pending_orders,
        "drivers": active_drivers
    })

@admin_router.post("/assign-delivery")
async def assign_delivery(request: Request, order_id: str = Form(...), driver_id: str = Form(...)):
    try:
        o_id = ObjectId(order_id)
        order = order_collection.find_one({"_id": o_id})
        if not order:
            return {"success": False, "message": "Order not found"}

        final_driver_id = None
        final_driver_name = "Unassigned"

        # 🚀 FIXED: Handle "auto" string separately to prevent ObjectId conversion crash
        if driver_id == "auto":
            from customer import get_optimal_driver 
            admin_id = order.get("admin_id")
            city = order.get("city")
            best_driver = get_optimal_driver(admin_id, city)
            
            if best_driver:
                final_driver_id = best_driver["_id"]
                final_driver_name = best_driver["name"]
            else:
                return {"success": False, "message": f"No active drivers found for {city}"}
        else:
            # Manual selection - Convert only if it's a valid ID string
            d_id = ObjectId(driver_id)
            driver = driver_collection.find_one({"_id": d_id})
            if driver:
                final_driver_id = d_id
                final_driver_name = driver["name"]

        # Update both collections
        order_collection.update_one(
            {"_id": o_id},
            {"$set": {
                "status": "IN_PROGRESS", 
                "assigned_driver_id": final_driver_id, 
                "assigned_driver_name": final_driver_name, 
                "assigned_at": datetime.utcnow()
            }}
        )
        customer_collection.update_one(
            {"records.order_id": o_id},
            {"$set": {"records.$.status": "IN_PROGRESS", "records.$.driver_name": final_driver_name}}
        )

        return RedirectResponse(url="/assignments", status_code=303)
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- TRACKING & AUDIT (NEW) ---

@admin_router.get("/track/{driver_id}")
async def track_driver_page(request: Request, driver_id: str, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse("/")
    
    driver = driver_collection.find_one({"_id": ObjectId(driver_id), "admin_id": admin_id})
    if not driver:
        return RedirectResponse("/dashboard")
        
    return templates.TemplateResponse("DriverTracking.html", {
        "request": request,
        "driver_name": driver["name"],
        "driver_id": driver_id
    })

@admin_router.get("/api/track-data/{driver_id}")
async def get_tracking_data(driver_id: str, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: raise HTTPException(status_code=401)
    
    d_oid = ObjectId(driver_id)
    driver = driver_collection.find_one({"_id": d_oid, "admin_id": admin_id})
    
    # 1. Get Current Location
    current_pos = None
    if driver and driver.get("current_lat"):
        current_pos = {"lat": driver["current_lat"], "lng": driver["current_lng"]}
        
    # 2. Get Path History (last 24h) for the movement line
    yesterday = datetime.utcnow() - timedelta(hours=24)
    loc_cursor = driver_location_collection.find(
        {"driver_id": d_oid, "timestamp": {"$gte": yesterday}}
    ).sort("timestamp", 1)
    path = [{"lat": l["lat"], "lng": l["lng"]} for l in loc_cursor]
    
    # 3. Get ALL assigned orders for this driver to show on map
    orders = order_collection.find({
        "assigned_driver_id": d_oid,
        "status": {"$in": ["PENDING", "IN_PROGRESS", "DELIVERED"]}
    })
    
    markers = []
    for o in orders:
        cust = customer_collection.find_one({"_id": o["customer_id"]})
        if cust and cust.get("verified_lat"):
            markers.append({
                "lat": float(cust["verified_lat"]),
                "lng": float(cust["verified_lng"]),
                "status": o["status"],
                "customer": cust["name"],
                "address": cust.get("landmark", "Unknown")
            })
            
    return {"current_pos": current_pos, "path": path, "markers": markers}

# --- REPORTS & STATISTICS ---

@admin_router.get("/reports")
async def reports_page(request: Request, period: str = "24h", admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)

    now = datetime.utcnow()
    threshold = now - (timedelta(days=7) if period == "1w" else timedelta(hours=24))

    query = {
        "admin_id": admin_id,
        "created_at": {"$gte": threshold}
    }
    recent_orders = list(order_collection.find(query))
    
    for o in recent_orders:
        o["_id"] = str(o["_id"])
    
    summary = {
        "total": len(recent_orders),
        "delivered": len([o for o in recent_orders if o.get("status") == "DELIVERED"]),
        "pending": len([o for o in recent_orders if o.get("status") == "PENDING"]),
        "in_progress": len([o for o in recent_orders if o.get("status") == "IN_PROGRESS"])
    }

    return templates.TemplateResponse("reports.html", {
        "request": request,
        "summary": summary,
        "period": period,
        "orders": recent_orders
    })

@admin_router.get("/export-report")
async def export_report(request: Request, period: str = "24h", admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        raise HTTPException(status_code=403, detail="Not authenticated")
    
    now = datetime.utcnow()
    threshold = now - (timedelta(days=7) if period == "1w" else timedelta(hours=24))
    
    orders = list(order_collection.find({
        "admin_id": admin_id,
        "created_at": {"$gte": threshold}
    }))
    
    export_data = [{
        "Order ID": str(o["_id"]),
        "Customer": o.get("customer_name"),
        "City": o.get("city"),
        "Driver": o.get("assigned_driver_name", "Unassigned"),
        "Status": o.get("status"),
        "Date": o.get("created_at").strftime("%Y-%m-%d %H:%M")
    } for o in orders]

    df = pd.DataFrame(export_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='DeliveryReport')
    
    output.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=GasDelivery_Report_{period}.xlsx"}
    return StreamingResponse(output, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@admin_router.get("/statistics")
async def statistics_page(request: Request, period: str = "7d"):
    now = datetime.utcnow()
    if period == "24h":
        start_date, date_format = now - timedelta(hours=24), "%H:00"
    elif period == "1w":
        start_date, date_format = now - timedelta(days=7), "%Y-%m-%d"
    else:
        start_date, date_format = now - timedelta(days=30), "%Y-%m-%d"

    query = {"created_at": {"$gte": start_date}}
    orders = list(order_collection.find(query))
    
    if not orders:
        return templates.TemplateResponse("statistics.html", {"request": request, "period": period, "no_data": True})

    df = pd.DataFrame(orders)
    df['date_label'] = df['created_at'].dt.strftime(date_format)
    
    trend = df.groupby('date_label').size().to_dict()
    city_dist = df['city'].value_counts().to_dict()
    status_dist = df['status'].value_counts().to_dict()
    driver_perf = df[df['status'] == "DELIVERED"]['assigned_driver_name'].value_counts().head(5).to_dict()

    stats_data = {
        "trend_labels": list(trend.keys()),
        "trend_values": [int(x) for x in trend.values()],
        "city_labels": list(city_dist.keys()),
        "city_values": [int(x) for x in city_dist.values()],
        "status_labels": list(status_dist.keys()),
        "status_values": [int(x) for x in status_dist.values()],
        "driver_labels": list(driver_perf.keys()),
        "driver_values": [int(x) for x in driver_perf.values()],
        "total_volume": int(len(df)),
        "avg_daily": float(round(len(df) / (7 if period == "1w" else 30), 1)) if period != "24h" else float(len(df))
    }

    return templates.TemplateResponse("statistics.html", {
        "request": request, "period": period, "stats": stats_data, "no_data": False
    })

# --- UPLOAD & PROFILE ---

@admin_router.post("/upload-customers")
async def upload_customers(request: Request, file: UploadFile = File(...), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)

    contents = await file.read()
    if file.filename.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(contents))
    else:
        df = pd.read_excel(io.BytesIO(contents))

    count_new = 0
    count_updated = 0

    for _, row in df.iterrows():
        phone = str(row['Phone Number']).strip()
        pincode = str(row.get('Pincode', '')).strip()
        
        customer_data = {
            "admin_id": admin_id,
            "name": row['Name'],
            "phone_number": phone,
            "city": row['City'],
            "landmark": row['Address & Landmark'],
            "pincode": pincode,
            "updated_at": datetime.utcnow()
        }

        existing = customer_collection.find_one({"phone_number": phone, "admin_id": admin_id})
        
        customer_collection.update_one(
            {"phone_number": phone, "admin_id": admin_id},
            {
                "$set": customer_data,
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                    "verified_lat": None,
                    "verified_lng": None,
                    "records": [] 
                }
            },
            upsert=True
        )
        
        if existing: count_updated += 1
        else: count_new += 1

    stats = {
        "drivers": driver_collection.count_documents({"admin_id": admin_id}),
        "customers": customer_collection.count_documents({"admin_id": admin_id}),
        "pending": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"}),
        "in_progress": order_collection.count_documents({"admin_id": admin_id, "status": "IN_PROGRESS"}),
        "delivered": order_collection.count_documents({"admin_id": admin_id, "status": "DELIVERED"})
    }
    
    user_email = admin_collection.find_one({"_id": admin_id})["email"]
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": {"username": user_email},
        "stats": stats,
        "message": f"✅ Uploaded: {count_new} New, {count_updated} Updated."
    })

@admin_router.get("/profile")
async def profile_view(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    admin = admin_collection.find_one({"_id": admin_id})
    my_drivers = list(driver_collection.find({"admin_id": admin_id}))
    for d in my_drivers:
        d["_id"] = str(d["_id"])
        d["date_str"] = d.get("created_at").strftime("%d %b %Y") if d.get("created_at") else "N/A"

    return templates.TemplateResponse("profile.html", {
        "request": request, 
        "admin": admin,
        "drivers": my_drivers
    })

@admin_router.post("/update-profile")
async def update_profile(
    request: Request, 
    phone: str = Form(None), 
    age: str = Form(None), 
    agency_name: str = Form(None),
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    update_data = {
        "phone": phone,
        "age": age,
        "agency_name": agency_name,
        "updated_at": datetime.utcnow()
    }
    
    admin_collection.update_one({"_id": admin_id}, {"$set": update_data})
    return RedirectResponse(url="/profile", status_code=303)