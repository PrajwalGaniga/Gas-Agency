from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, StreamingResponse
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
import pandas as pd
import io
from bson import ObjectId

# Database Imports
from app.database import (
    db, admin_collection, driver_collection, 
    customer_collection, order_collection, cities_collection
)
from app.utils import verify_password, get_password_hash, generate_otp, send_otp_email

admin_router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- JWT CONFIGURATION (Admin Side) ---
SECRET_KEY = "your_secret_key_here"  # In production, move to .env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_admin(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        # Remove 'Bearer ' if present (though cookies usually just have the token)
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        admin_id = payload.get("sub")
        if admin_id is None:
            return None
        return ObjectId(admin_id)
    except JWTError:
        return None

# --- CONSTANTS ---
DEVELOPER_PASSCODE = "GAS"
MASTER_EMAIL = "prajwalganiga06@gmail.com"

# PURPOSE: Renders the signup page
@admin_router.get("/signup")
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

# PURPOSE: Validates developer passcode and sends OTP for signup
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

# PURPOSE: Verifies OTP and creates the admin account
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

# PURPOSE: Renders the login page
@admin_router.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# PURPOSE: Authenticates admin, generates JWT, and sets it in a secure cookie
@admin_router.post("/login")
async def login_logic(request: Request, email: str = Form(...), password: str = Form(...)):
    user = admin_collection.find_one({"email": email})
    
    if user and verify_password(password, user["password_hash"]):
        # Create JWT Token
        access_token = create_access_token(data={"sub": str(user["_id"])})
        
        response = RedirectResponse(url="/dashboard", status_code=303)
        # Set HttpOnly Cookie
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        return response
    
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials."})

# PURPOSE: Logs out the admin by clearing the cookie
@admin_router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/?message=Logged out successfully", status_code=303)
    response.delete_cookie("access_token")
    return response

# PURPOSE: Password reset flow - Page
@admin_router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

# PURPOSE: Password reset flow - Send OTP
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

# PURPOSE: Password reset flow - Verify OTP
@admin_router.post("/verify-otp")
async def verify_otp(request: Request, email: str = Form(...), otp: str = Form(...)):
    user = admin_collection.find_one({"email": email})
    if user and user.get("reset_otp") == otp:
        return templates.TemplateResponse("reset_password.html", {"request": request, "email": email})
    
    return templates.TemplateResponse("verify_otp.html", {"request": request, "email": email, "error": "Invalid OTP."})

# PURPOSE: Password reset flow - Reset Logic
@admin_router.post("/reset-password")
async def reset_password_logic(request: Request, email: str = Form(...), new_password: str = Form(...)):
    hashed_pwd = get_password_hash(new_password)
    admin_collection.update_one(
        {"email": email},
        {"$set": {"password_hash": hashed_pwd}, "$unset": {"reset_otp": ""}}
    )
    return templates.TemplateResponse("login.html", {"request": request, "message": "✅ Password reset successful!"})

# PURPOSE: Admin Dashboard - Shows statistics
@admin_router.get("/dashboard")
async def dashboard_view(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
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
        "stats": stats, 
        "user": {"username": user_email}
    })

# PURPOSE: Driver Management View
@admin_router.get("/drivers")
async def driver_management(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    cities = list(db["cities"].find()) 
    
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

# PURPOSE: Add new driver
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

# PURPOSE: Update existing driver
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

# PURPOSE: Delete a driver
@admin_router.post("/delete-driver")
async def delete_driver(request: Request, driver_id: str = Form(...), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)
    
    driver_collection.delete_one({
        "_id": ObjectId(driver_id), 
        "admin_id": admin_id
    })
    return RedirectResponse(url="/drivers?msg=Driver deleted", status_code=303)

# PURPOSE: Delivery Assignments Page
@admin_router.get("/assignments")
async def delivery_assignments(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id:
        return RedirectResponse(url="/", status_code=303)

    pending_orders = list(order_collection.find({
        "admin_id": admin_id, 
        "status": "PENDING"
    }))
    for order in pending_orders:
        order["_id"] = str(order["_id"])
        order["customer_id"] = str(order["customer_id"])

    active_drivers = list(driver_collection.find({
        "admin_id": admin_id, 
        "is_active": True
    }))
    for driver in active_drivers:
        driver["_id"] = str(driver["_id"])

    return templates.TemplateResponse("assignments.html", {
        "request": request,
        "orders": pending_orders,
        "drivers": active_drivers
    })

# PURPOSE: Assign a driver to an order
@admin_router.post("/assign-delivery")
async def assign_delivery(request: Request, order_id: str = Form(...), driver_id: str = Form(...)):
    print(f"\n--- DEBUG: Assignment Requested ---")
    try:
        o_id, d_id = ObjectId(order_id), ObjectId(driver_id)
        driver = driver_collection.find_one({"_id": d_id})
        
        order_collection.update_one(
            {"_id": o_id},
            {"$set": {
                "status": "IN_PROGRESS", 
                "assigned_driver_id": d_id, 
                "assigned_driver_name": driver["name"], 
                "assigned_at": datetime.utcnow()
            }}
        )

        customer_collection.update_one(
            {"records.order_id": o_id},
            {"$set": {
                "records.$.status": "IN_PROGRESS", 
                "records.$.driver_name": driver["name"]
            }}
        )

        # Handle Response based on Accept Header (App vs Web)
        accept_header = request.headers.get("accept", "")
        if "application/json" in accept_header:
            return {"success": True, "message": "Order assigned successfully!"}
        
        return RedirectResponse(url="/assignments", status_code=303)

    except Exception as e:
        print(f"DEBUG CRITICAL ERROR in /assign-delivery: {e}")
        return {"success": False, "message": str(e)}

# PURPOSE: Reports View
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

# PURPOSE: Export Report as Excel
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

# PURPOSE: Statistics Page
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

# PURPOSE: Bulk Upload Customers via Excel/CSV
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
        # Retrieve Pincode if it exists in the sheet, else empty string
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

# PURPOSE: Admin Profile View
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

# PURPOSE: Update Admin Profile
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