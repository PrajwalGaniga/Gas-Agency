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
    driver_audit_collection, driver_location_collection, change_requests_collection,daily_stats_collection
)
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
    
    # 🚀 FIX: If it's already a date (no time), don't try to add timezone
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

# 🛠️ CRITICAL FIX: Inject helpers into Jinja2 environment (Fixes UndefinedError)
templates.env.globals.update({
    "to_ist": to_ist,
    "ist_now": ist_now
})

# --- CONSTANTS ---
DEVELOPER_PASSCODE = "GAS"
MASTER_EMAIL = "prajwalganiga06@gmail.com"

# --- HELPER FUNCTIONS ---

# --- 🚀 REFACTORED ANALYTICS (GPS-BASED PROOF OF WORK) ---

def calculate_work_time(driver_id):
    """
    Calculates total work hours for the current IST day based on GPS Heartbeats.
    Ensures 'Total Work Hours' in Fleet Control isn't 0 if pings exist.
    """
    today_start_utc = ist_day_start(ist_now().date())
    
    # 🛰️ Fetch all location pings for this driver today
    pings = list(driver_location_collection.find({
        "driver_id": ObjectId(driver_id),
        "timestamp": {"$gte": today_start_utc}
    }).sort("timestamp", 1))
    
    if not pings:
        return "0h 0m"
    
    total_seconds = 0
    # Logic: Sum gaps between pings if they are < 15 minutes apart
    for i in range(len(pings) - 1):
        diff = (pings[i+1]["timestamp"] - pings[i]["timestamp"]).total_seconds()
        if diff < 900:  # 15 minute 'Active' threshold
            total_seconds += diff
            
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    return f"{hours}h {minutes}m"


def get_detailed_driver_metrics(driver_id, start_date_utc, end_date_utc):
    """
    Computes daily analytics for the Audit Page by grouping GPS Heartbeats.
    Fixes simultaneous clock-in/out by identifying the absolute start/end pings.
    """
    # 1. Fetch all pings in the selected timeframe
    pings = list(driver_location_collection.find({
        "driver_id": ObjectId(driver_id),
        "timestamp": {"$gte": start_date_utc, "$lte": end_date_utc}
    }).sort("timestamp", 1))

    if not pings:
        return {"days": [], "summary": {"total_hours": 0, "active_days": 0, "total_deliveries": 0}}

    # 2. Group pings by IST Date
    daily_groups = {}
    for p in pings:
        ist_ping = to_ist(p["timestamp"])
        date_key = ist_ping.date()
        if date_key not in daily_groups: 
            daily_groups[date_key] = []
        daily_groups[date_key].append(ist_ping)

    processed_days = []
    grand_total_seconds = 0
    grand_total_deliveries = 0

    # 3. Process each day's activity
    for day_date, day_pings in daily_groups.items():
        day_seconds = 0
        for i in range(len(day_pings) - 1):
            diff = (day_pings[i+1] - day_pings[i]).total_seconds()
            if diff < 900: # Count gaps < 15 mins as work
                day_seconds += diff
        
        grand_total_seconds += day_seconds
        day_start_utc, day_end_utc = ist_day_start(day_date), ist_day_end(day_date)
        
        # 📦 Count actual deliveries completed in this IST day
        deliveries_count = order_collection.count_documents({
            "assigned_driver_id": ObjectId(driver_id),
            "status": "DELIVERED",
            "delivered_at": {"$gte": day_start_utc, "$lte": day_end_utc}
        })
        grand_total_deliveries += deliveries_count

        # Get the timestamp of the very last delivery today
        last_delivered_order = order_collection.find_one(
            {"assigned_driver_id": ObjectId(driver_id), "status": "DELIVERED", "delivered_at": {"$gte": day_start_utc, "$lte": day_end_utc}},
            sort=[("delivered_at", -1)]
        )

        processed_days.append({
            "date": day_date,
            "first_ping": day_pings[0],  # 🌅 Earliest Heartbeat (Clock In)
            "last_ping": day_pings[-1],   # 🌇 Latest Heartbeat (Clock Out)
            "duration": f"{int(day_seconds // 3600)}h {int((day_seconds % 3600) // 60)}m",
            "deliveries": deliveries_count,
            "last_delivery_at": last_delivered_order.get("delivered_at") if last_delivered_order else None
        })

    return {
        "days": sorted(processed_days, key=lambda x: x["date"], reverse=True),
        "summary": {
            "total_hours": round(grand_total_seconds / 3600, 1),
            "active_days": len(processed_days),
            "total_deliveries": grand_total_deliveries,
            "avg_deliveries": round(grand_total_deliveries / len(processed_days), 1) if processed_days else 0,
            "avg_hours": round((grand_total_seconds / 3600) / len(processed_days), 1) if processed_days else 0
        }
    }
# --- AUTH ROUTES ---

@admin_router.get("/signup")
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@admin_router.post("/signup-request")
async def signup_request(request: Request, email: str = Form(...), password: str = Form(...), passcode: str = Form(...)):
    if passcode != DEVELOPER_PASSCODE:
        return {"success": False, "message": "Invalid Developer Passcode."}
    if admin_collection.find_one({"email": email}):
        return {"success": False, "message": "Email already registered."}

    otp = generate_otp()
    hashed_pw = get_password_hash(password)
    db["temp_signups"].update_one(
        {"email": email}, 
        {"$set": {"otp": otp, "password_hash": hashed_pw, "created_at": datetime.now(timezone.utc)}}, 
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

# --- DASHBOARD & DRIVERS ---

@admin_router.get("/dashboard")
async def dashboard_view(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse("/")
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    stats_list = []
    now_utc = datetime.now(timezone.utc)
    for d in drivers:
        ls = d.get("last_seen")
        is_online = ls and (now_utc - ls.replace(tzinfo=timezone.utc)).total_seconds() < 600
        ls_utc = ls.replace(tzinfo=timezone.utc) if ls and ls.tzinfo is None else ls
        stats_list.append({
            "id": str(d["_id"]),
            "name": d["name"],
            "phone": d.get("phone_number", "N/A"),
            "is_online": ls_utc and (now_utc - ls_utc).total_seconds() < 300,
            "last_seen": to_ist(ls_utc),
            "work_time": calculate_work_time(d["_id"]),
            "completed": order_collection.count_documents({"assigned_driver_id": d["_id"], "status": "DELIVERED"}),
            "pending": order_collection.count_documents({"assigned_driver_id": d["_id"], "status": "PENDING"})
        })
    stats = {
        "drivers": len(drivers), "customers": customer_collection.count_documents({"admin_id": admin_id}),
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
    for d in drivers:
        d["_id"] = str(d["_id"])
        d["assigned_cities"] = d.get("assigned_cities") or []
        d["total_deliveries"] = order_collection.count_documents({"assigned_driver_id": ObjectId(d["_id"]), "status": "DELIVERED"})
    return templates.TemplateResponse("drivers.html", {"request": request, "drivers": drivers, "cities": cities})

@admin_router.post("/add-driver")
async def add_driver(request: Request, name: str = Form(...), phone: str = Form(...), password: str = Form(...), cities: list = Form([]), admin_id: ObjectId = Depends(get_current_admin)):
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
async def delete_driver(request: Request, driver_id: str = Form(...), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    driver_collection.delete_one({"_id": ObjectId(driver_id), "admin_id": admin_id})
    return RedirectResponse(url="/drivers?msg=Driver deleted", status_code=303)

# --- ASSIGNMENTS ---

@admin_router.get("/assignments")
async def delivery_assignments(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    pending_orders = list(order_collection.find({"admin_id": admin_id, "status": "PENDING"}))
    for order in pending_orders:
        order["_id"], order["customer_id"] = str(order["_id"]), str(order["customer_id"])
    active_drivers = list(driver_collection.find({"admin_id": admin_id, "is_active": True}))
    for driver in active_drivers:
        driver["_id"] = str(driver["_id"])
        for key, value in driver.items():
            if isinstance(value, datetime): driver[key] = to_ist(value).isoformat()
    return templates.TemplateResponse("assignments.html", {"request": request, "orders": pending_orders, "drivers": active_drivers})

@admin_router.post("/assign-delivery")
async def assign_delivery(request: Request, order_id: str = Form(...), driver_id: str = Form(...)):
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

# --- TRACKING & AUDIT ---

@admin_router.get("/track/{driver_id}")
async def track_driver_page(request: Request, driver_id: str, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse("/")
    driver = driver_collection.find_one({"_id": ObjectId(driver_id), "admin_id": admin_id})
    if not driver: return RedirectResponse("/dashboard")
    return templates.TemplateResponse("DriverTracking.html", {"request": request, "driver_name": driver["name"], "driver_id": driver_id})

# admin.py (Update the get_tracking_data route)

@admin_router.get("/api/track-data/{driver_id}")
async def get_tracking_data(
    driver_id: str, 
    date: str = Query(None), # 📅 Historical Date Selector (Format: YYYY-MM-DD)
    admin_id: ObjectId = Depends(get_current_admin)
):
    """
    Core Intelligence: Fetches real-time driver coordinates, breadcrumb path, 
    and delivery markers for the Admin Fleet Map.
    """
    if not admin_id: 
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        d_oid = ObjectId(driver_id)
        
        # 1. 🕒 Determine Timeframe (IST-Aware)
        # Defaults to 'Today' if no date is provided by the dashboard
        target_date = datetime.strptime(date, "%Y-%m-%d").date() if date else ist_now().date()
        start_utc = ist_day_start(target_date)
        end_utc = ist_day_end(target_date)

        # 2. 🚛 Fetch Driver's Live/Last Known Position
        driver = driver_collection.find_one({"_id": d_oid})
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
            
        current_pos = {
            "lat": float(driver.get("current_lat")) if driver.get("current_lat") else None,
            "lng": float(driver.get("current_lng")) if driver.get("current_lng") else None,
            "last_seen": to_ist(driver.get("last_seen")).strftime("%H:%M") if driver.get("last_seen") else "Never"
        }
        
        # 3. 🛰️ Fetch Heartbeat Path (The Breadcrumb Trail)
        # This draws the Polyline on the Admin Map showing the actual route taken
        loc_cursor = driver_location_collection.find({
            "driver_id": d_oid, 
            "timestamp": {"$gte": start_utc, "$lte": end_utc}
        }).sort("timestamp", 1)
        
        # 🚀 Fix: Ensure coordinates are floats to prevent JS map errors
        path = [
            {"lat": float(l["lat"]), "lng": float(l["lng"]), "time": to_ist(l["timestamp"]).strftime("%H:%M")} 
            for l in loc_cursor if l.get("lat") and l.get("lng")
        ]

        # 4. 📦 Fetch Delivery Markers for this day
        # Displays status-colored markers: Green (Delivered), Blue (Ongoing), Orange (Pending)
        orders = list(order_collection.find({
            "assigned_driver_id": d_oid, 
            "created_at": {"$gte": start_utc, "$lte": end_utc}
        }))
        
        markers = []
        for o in orders:
            # Cross-reference with customer data for verified GPS
            cust = customer_collection.find_one({"_id": o["customer_id"]})
            if cust and cust.get("verified_lat") is not None:
                markers.append({
                    "lat": float(cust["verified_lat"]),
                    "lng": float(cust["verified_lng"]),
                    "status": o["status"], 
                    "customer": cust["name"],
                    "address": cust.get("landmark", "N/A"),
                    "order_id": str(o["_id"])
                })

        # 🟢 TERMINAL DEBUG: Track successful data retrieval
        print(f"🛰️ TRACKING API: Returning {len(path)} path points and {len(markers)} markers for Driver {driver['name']}")

        return {
            "success": True,
            "driver_name": driver["name"],
            "current_pos": current_pos,
            "path": path,
            "markers": markers,
            "date_label": target_date.strftime("%d %b %Y")
        }
        
    except Exception as e:
        print(f"❌ TRACKING ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch tracking data")
    
# admin.py
@admin_router.get("/driver-audit")
async def driver_audit_page(
    request: Request, 
    period: str = Query("24h"), 
    driver_id: str = Query(None), 
    admin_id: ObjectId = Depends(get_current_admin)
):
    if not admin_id: 
        return RedirectResponse("/")

    # 1. 🕒 Standardize IST Timeframe Logic
    now_ist = ist_now()
    now_utc = datetime.now(timezone.utc)
    periods_map = {"24h": 1, "1w": 7, "1m": 30}
    days_back = periods_map.get(period, 1)
    
    # Calculate the global start window based on the selected period
    start_date_utc = ist_day_start((now_ist - timedelta(days=days_back-1)).date())
    # Boundaries for Today's dynamic data
    today_start_utc = ist_day_start(now_ist.date())

    # 2. Fetch Drivers and Initialize Containers
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    driver_ids_list = [d["_id"] for d in drivers]
    
    table_data = []
    summary_totals = {
        "active_days": 0, 
        "total_hours": 0, 
        "total_deliveries": 0, 
        "pending_requests": 0
    }

    # 3. ❄️ FETCH FROZEN HISTORICAL DATA (Yesterday and older)
    # This avoids expensive raw GPS ping scans for old data
    hist_query = {
        "driver_id": {"$in": driver_ids_list},
        "date": {"$gte": start_date_utc, "$lt": today_start_utc}
    }
    if driver_id:
        hist_query["driver_id"] = ObjectId(driver_id)

    historical_records = list(daily_stats_collection.find(hist_query).sort("date", -1))

    # Add historical data to the audit table
    for record in historical_records:
        table_data.append({
            "driver_name": record["driver_name"],
            "date": record["date"],
            "first_ping": record["first_active"],
            "last_ping": record["last_active"],
            "duration": record["duration_str"],
            "deliveries": record["deliveries_completed"]
        })
        summary_totals["total_hours"] += (record.get("total_work_seconds", 0) / 3600)
        summary_totals["total_deliveries"] += record["deliveries_completed"]
    
    # 4. 🔥 FETCH DYNAMIC DATA (Today's live pings)
    for d in drivers:
        if driver_id and str(d["_id"]) != driver_id:
            continue
            
        # Calculate today's metrics on-the-fly using the GPS gap logic
        today_metrics = get_detailed_driver_metrics(d["_id"], today_start_utc, now_utc)
        
        for day in today_metrics["days"]:
            table_data.append({
                "driver_name": d["name"],
                **day
            })
            summary_totals["total_hours"] += (day.get("duration_seconds", 0) / 3600) # Ensure duration_seconds exists in helper
        
        # If no duration_seconds, fallback to the dynamic summary
        if not today_metrics["days"] and period == "24h":
            # Handles the case where driver hasn't pinged yet today
            pass
        
        summary_totals["total_deliveries"] += today_metrics["summary"]["total_deliveries"]

    # 5. 📋 AGGREGATE CHANGE REQUESTS
    requests_cursor = change_requests_collection.find({
        "admin_id": admin_id
    }).sort("timestamp", -1).limit(50)
    
    processed_requests = []
    for req in requests_cursor:
        cust = customer_collection.find_one({"_id": req.get("customer_id")})
        req["customer_name"] = cust["name"] if cust else "Unknown Customer"
        req["customer_id_str"] = str(req.get("customer_id", ""))
        
        if req["status"] == "PENDING":
            summary_totals["pending_requests"] += 1
        processed_requests.append(req)

    # Final summary formatting
    summary_totals["total_hours"] = round(summary_totals["total_hours"], 1)
    summary_totals["active_days"] = len(set([d['date'].date() if isinstance(d['date'], datetime) else d['date'] for d in table_data]))
    summary_totals["avg_hours"] = round(summary_totals["total_hours"] / summary_totals["active_days"], 1) if summary_totals["active_days"] > 0 else 0

    # Sort table by date descending (Newest first)
    table_data.sort(key=lambda x: x["date"], reverse=True)

    return templates.TemplateResponse("DriverAudit.html", {
        "request": request, 
        "audits": table_data, 
        "summary": summary_totals, 
        "requests": processed_requests, 
        "drivers": drivers, 
        "active_period": period,
        "selected_driver": driver_id
    })

@admin_router.get("/export-driver-audit")
async def export_driver_audit(period: str = "1w", admin_id: ObjectId = Depends(get_current_admin)):
    now_ist = ist_now()
    days_back = {"24h": 1, "1w": 7, "1m": 30}.get(period, 7)
    start_date_utc = ist_day_start((now_ist - timedelta(days=days_back-1)).date())
    now_utc = datetime.now(timezone.utc)
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    all_rows = []
    for d in drivers:
        metrics = get_detailed_driver_metrics(d["_id"], start_date_utc, now_utc)
        for day in metrics["days"]: 
            all_rows.append({
                "Driver": d["name"], 
                "Date": day["date"].strftime("%Y-%m-%d"), 
                "First Active": day["first_ping"].strftime("%I:%M %p"), 
                "Last Active": day["last_ping"].strftime("%I:%M %p"), 
                "Work Duration": day["duration"], 
                "Deliveries": day["deliveries"],
                "Last Delivery Time": to_ist(day["last_delivery_at"]).strftime("%I:%M %p") if day["last_delivery_at"] else "—"
            })
    df = pd.DataFrame(all_rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False, sheet_name='WorkAudit')
    output.seek(0)
    return StreamingResponse(output, headers={"Content-Disposition": f"attachment; filename=DriverAudit_{period}.xlsx"}, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@admin_router.post("/api/resolve-request")
async def resolve_change_request(
    request_id: str = Form(...),
    action: str = Form(...), 
    remarks: str = Form(""),
    admin_id: ObjectId = Depends(get_current_admin)
):
    status = "APPROVED" if action == "approve" else "REJECTED"
    change_requests_collection.update_one(
        {"_id": ObjectId(request_id), "admin_id": admin_id},
        {"$set": {
            "status": status,
            "admin_remarks": remarks,
            "decision_timestamp": datetime.now(timezone.utc) # 🚀 Log resolution time
        }}
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
    summary = {"total": len(recent_orders), "delivered": len([o for o in recent_orders if o.get("status") == "DELIVERED"]), "pending": len([o for o in recent_orders if o.get("status") == "PENDING"]), "in_progress": len([o for o in recent_orders if o.get("status") == "IN_PROGRESS"])}
    return templates.TemplateResponse("reports.html", {"request": request, "summary": summary, "period": period, "orders": recent_orders})

@admin_router.get("/export-report")
async def export_report(request: Request, period: str = "24h", admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: raise HTTPException(status_code=403)
    days = {"24h": 1, "1w": 7, "1m": 30}.get(period, 1)
    threshold_utc = datetime.now(timezone.utc) - timedelta(days=days)
    orders = list(order_collection.find({"admin_id": admin_id, "created_at": {"$gte": threshold_utc}}))
    export_data = [{"Order ID": str(o["_id"]), "Customer": o.get("customer_name"), "Status": o.get("status"), "Delivered Time (IST)": to_ist(o.get("delivered_at")).strftime("%Y-%m-%d %H:%M") if o.get("delivered_at") else "—", "Created Date (IST)": to_ist(o.get("created_at")).strftime("%Y-%m-%d %H:%M") if o.get("created_at") else "N/A"} for o in orders]
    df = pd.DataFrame(export_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
    output.seek(0)
    return StreamingResponse(output, headers={"Content-Disposition": f"attachment; filename=GasDelivery_Report_{period}.xlsx"}, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# admin.py 

@admin_router.get("/statistics") # 🚀 FIXED: Added missing decorator
async def statistics_page(request: Request, period: str = "7d"):
    days = {"24h": 1, "1w": 7, "1m": 30}.get(period, 7)
    now_utc = datetime.now(timezone.utc)
    start_date_utc = now_utc - timedelta(days=days)
    date_format = "%H:00" if period == "24h" else "%Y-%m-%d"
    
    orders = list(order_collection.find({"created_at": {"$gte": start_date_utc}}))
    if not orders:
        return templates.TemplateResponse("statistics.html", {"request": request, "period": period, "no_data": True})
        
    df = pd.DataFrame(orders)
    df['created_at_ist'] = df['created_at'].apply(to_ist)
    df['date_label'] = df['created_at_ist'].dt.strftime(date_format)
    
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
        "avg_daily": float(round(len(df) / days, 1))
    }
    return templates.TemplateResponse("statistics.html", {"request": request, "period": period, "stats": stats_data, "no_data": False})
# --- UPLOAD & PROFILE ---

@admin_router.post("/upload-customers")
async def upload_customers(request: Request, file: UploadFile = File(...), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents)) if file.filename.endswith('.csv') else pd.read_excel(io.BytesIO(contents))
    count_new, count_updated = 0, 0
    now_utc = datetime.now(timezone.utc)
    
    for _, row in df.iterrows():
        phone = str(row['Phone Number']).strip()
        customer_data = {
            "admin_id": admin_id, "name": row['Name'], "phone_number": phone, "city": row['City'], 
            "landmark": row['Address & Landmark'], "pincode": str(row.get('Pincode', '')).strip(), "updated_at": now_utc
        }
        customer_collection.update_one(
            {"phone_number": phone, "admin_id": admin_id}, 
            {"$set": customer_data, "$setOnInsert": {"created_at": now_utc, "verified_lat": None, "verified_lng": None, "records": []}}, 
            upsert=True
        )
        count_new += 1 # Simplified for audit

    # 🚀 FIXED: Added "unassigned" to satisfy dashboard.html requirements
    stats = {
        "drivers": driver_collection.count_documents({"admin_id": admin_id}),
        "customers": customer_collection.count_documents({"admin_id": admin_id}),
        "pending": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"}),
        "unassigned": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING", "assigned_driver_id": None}),
        "in_progress": order_collection.count_documents({"admin_id": admin_id, "status": "IN_PROGRESS"}),
        "delivered": order_collection.count_documents({"admin_id": admin_id, "status": "DELIVERED"})
    }
    
    admin_user = admin_collection.find_one({"_id": admin_id})
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": {"username": admin_user["email"] if admin_user else "Admin"}, 
        "stats": stats, 
        "message": f"✅ Uploaded successfully."
    })

# admin.py

@admin_router.get("/profile")
async def profile_view(request: Request, admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: 
        return RedirectResponse(url="/", status_code=303)
        
    admin = admin_collection.find_one({"_id": admin_id})
    my_drivers = list(driver_collection.find({"admin_id": admin_id}))
    
    # 📊 Advanced Stats Calculation
    total_orders = order_collection.count_documents({"admin_id": admin_id})
    delivered_orders = order_collection.count_documents({"admin_id": admin_id, "status": "DELIVERED"})
    
    # Success Rate (Percentage)
    success_rate = round((delivered_orders / total_orders * 100), 1) if total_orders > 0 else 0
    
    # Account Age (Days)
    account_age = (datetime.now(timezone.utc) - admin["created_at"].replace(tzinfo=timezone.utc)).days if admin.get("created_at") else 0
    
    # Driver Efficiency (Avg deliveries per driver)
    driver_efficiency = round(delivered_orders / len(my_drivers), 1) if my_drivers else 0

    # 🎖️ Level System (Gamification)
    level = "Bronze"
    if delivered_orders > 500: level = "Platinum"
    elif delivered_orders > 100: level = "Gold"
    elif delivered_orders > 20: level = "Silver"

    # Process Driver List for Table
    for d in my_drivers:
        d["_id"] = str(d["_id"])
        reg_date_ist = to_ist(d.get("created_at"))
        d["date_str"] = reg_date_ist.strftime("%d %b %Y") if reg_date_ist else "N/A"

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "admin": admin,
        "drivers": my_drivers,
        "stats": {
            "total_orders": total_orders,
            "success_rate": success_rate,
            "account_age": account_age,
            "efficiency": driver_efficiency,
            "level": level,
            "active_drivers": len([d for d in my_drivers if d.get("is_active")])
        }
    })

@admin_router.post("/update-profile")
async def update_profile(request: Request, phone: str = Form(None), age: str = Form(None), agency_name: str = Form(None), admin_id: ObjectId = Depends(get_current_admin)):
    if not admin_id: return RedirectResponse(url="/", status_code=303)
    admin_collection.update_one({"_id": admin_id}, {"$set": {"phone": phone, "age": age, "agency_name": agency_name, "updated_at": datetime.now(timezone.utc)}})
    return RedirectResponse(url="/profile", status_code=303)