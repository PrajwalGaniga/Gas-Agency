from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.database import admin_collection
from app.utils import verify_password, get_password_hash, generate_otp, send_otp_email
# Import db and all collections globally
from app.database import db, admin_collection, driver_collection, customer_collection, order_collection
from app.database import (
    db, 
    admin_collection, 
    driver_collection, 
    customer_collection, 
    order_collection
)
from app.utils import verify_password, get_password_hash, generate_otp, send_otp_email
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- Authentication Routes ---
# Constants for security
DEVELOPER_PASSCODE = "GAS"
MASTER_EMAIL = "prajwalganiga06@gmail.com"
from starlette.middleware.sessions import SessionMiddleware

# Add this right after app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key_here")

# Helper to get the current logged-in admin's ID
def get_admin_id(request: Request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        return None
    return ObjectId(admin_id)


# Add this route to your main.py
@app.get("/signup")
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})
# 1. Signup Request: Validates passcode and sends OTP to YOU
@app.post("/signup-request")
async def signup_request(
    request: Request, 
    email: str = Form(...), 
    password: str = Form(...), 
    passcode: str = Form(...) # Change this to Form(...)
):
    # Now it looks at the input from the signup.html form
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

# 2. Complete Signup: Verifies the OTP you give to the new admin
@app.post("/complete-signup")
async def complete_signup(email: str = Form(...), otp: str = Form(...)):
    temp_user = db["temp_signups"].find_one({"email": email})
    
    if temp_user and temp_user.get("otp") == otp:
        # Move from temp to actual admin collection
        admin_collection.insert_one({
            "email": email,
            "password_hash": temp_user["password_hash"],
            "created_at": datetime.utcnow()
        })
        db["temp_signups"].delete_one({"email": email})
        return {"success": True, "message": "Registration complete! You can now login."}
    
    return {"success": False, "message": "Invalid or expired OTP."}

@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# 3. Updated Login: Saves admin_id into the session
@app.post("/login")
async def login_logic(request: Request, email: str = Form(...), password: str = Form(...)):
    user = admin_collection.find_one({"email": email})
    
    if user and verify_password(password, user["password_hash"]):
        # Save Admin ID in session
        request.session["admin_id"] = str(user["_id"])
        request.session["user_email"] = user["email"]
        
        return RedirectResponse(url="/dashboard", status_code=303)
    
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials."})

# --- Forgot Password Flow ---
@app.get("/dashboard")
async def dashboard_view(request: Request):
    # Security check: Ensure admin is logged in
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    
    admin_id = ObjectId(admin_id_str)
    
    # Filter stats by admin_id
    stats = {
        "drivers": driver_collection.count_documents({"admin_id": admin_id}),
        "customers": customer_collection.count_documents({"admin_id": admin_id}),
        "pending": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"}),
        "in_progress": order_collection.count_documents({"admin_id": admin_id, "status": "IN_PROGRESS"}),
        "delivered": order_collection.count_documents({"admin_id": admin_id, "status": "DELIVERED"})
    }
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "stats": stats, 
        "user": {"username": request.session.get("user_email")}
    })

# --- ROBUST DRIVER ORDERS ENDPOINT ---
@app.get("/driver/orders/{city}")
async def get_driver_orders(city: str, driver_id: str):
    # 1. Check for active job first
    active_job = order_collection.find_one({
        "assigned_driver_id": ObjectId(driver_id),
        "status": "IN_PROGRESS"
    })
    
    if active_job:
        # Serialize everything for JSON
        active_job["_id"] = str(active_job["_id"])
        cust_id = active_job["customer_id"]
        active_job["customer_id"] = str(cust_id)
        active_job["assigned_driver_id"] = str(active_job["assigned_driver_id"])
        
        # Fetch customer location status
        cust = customer_collection.find_one({"_id": cust_id})
        active_job["verified_lat"] = cust.get("verified_lat") # null if not set
        active_job["verified_lng"] = cust.get("verified_lng")
        active_job["address"] = cust.get("landmark", "No Address")
        active_job["phone"] = cust.get("phone_number")
        
        return {"success": True, "has_active": True, "active_order": active_job}

    # 2. Otherwise return PENDING orders
    orders = list(order_collection.find({"city": city, "status": "PENDING"}))
    for o in orders:
        o["_id"] = str(o["_id"])
        o["customer_id"] = str(o["customer_id"])
        # Add address for display in list
        cust = customer_collection.find_one({"_id": ObjectId(o["customer_id"])})
        o["address"] = cust.get("landmark", "No Address") if cust else "Unknown"

    return {"success": True, "has_active": False, "orders": orders}

@app.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@app.post("/send-otp")
async def send_otp(request: Request, email: str = Form(...)):
    user = admin_collection.find_one({"email": email}) #
    if not user:
        return templates.TemplateResponse("forgot_password.html", {"request": request, "error": "Email not found."})

    otp = generate_otp()
    admin_collection.update_one({"email": email}, {"$set": {"reset_otp": otp}}) #

    if send_otp_email(email, otp):
        return templates.TemplateResponse("verify_otp.html", {"request": request, "email": email})
    
    return templates.TemplateResponse("forgot_password.html", {"request": request, "error": "Failed to send OTP."})

@app.post("/verify-otp")
async def verify_otp(request: Request, email: str = Form(...), otp: str = Form(...)):
    user = admin_collection.find_one({"email": email}) #
    if user and user.get("reset_otp") == otp:
        return templates.TemplateResponse("reset_password.html", {"request": request, "email": email})
    
    return templates.TemplateResponse("verify_otp.html", {"request": request, "email": email, "error": "Invalid OTP."})

@app.post("/reset-password")
async def reset_password_logic(request: Request, email: str = Form(...), new_password: str = Form(...)):
    hashed_pwd = get_password_hash(new_password)
    admin_collection.update_one( #
        {"email": email},
        {"$set": {"password_hash": hashed_pwd}, "$unset": {"reset_otp": ""}}
    )
    return templates.TemplateResponse("login.html", {"request": request, "message": "✅ Password reset successful!"})


from fastapi import UploadFile, File
import pandas as pd
from datetime import datetime
import io

@app.post("/upload-customers")
async def upload_customers(request: Request, file: UploadFile = File(...)):
    # Read the uploaded file (CSV or Excel)
    contents = await file.read()
    if file.filename.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(contents))
    else:
        df = pd.read_excel(io.BytesIO(contents))

    from app.database import customer_collection

    count_new = 0
    count_updated = 0

    for _, row in df.iterrows():
        phone = str(row['Phone Number']).strip()
        
        # Prepare the customer data
        customer_data = {
            "name": row['Name'],
            "phone_number": phone,
            "city": row['City'],
            "area": "", # You can split 'Address & Landmark' if needed
            "landmark": row['Address & Landmark'],
            "updated_at": datetime.utcnow()
        }

        # Check if customer exists to track stats (optional)
        existing = customer_collection.find_one({"phone_number": phone})
        
        # Upsert Logic: Update if phone exists, insert if not
        # We use $setOnInsert to add fields only during creation (like records and created_at)
        customer_collection.update_one(
            {"phone_number": phone},
            {
                "$set": customer_data,
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                    "verified_lat": None,
                    "verified_lng": None,
                    "records": []  # List to store delivery history
                }
            },
            upsert=True
        )
        
        if existing: count_updated += 1
        else: count_new += 1

    # Redirect back to dashboard with a success message
    from app.database import driver_collection, order_collection
    stats = {
        "drivers": driver_collection.count_documents({}),
        "customers": customer_collection.count_documents({}),
        # Changed "orders" to "pending" to match dashboard.html requirements
        "pending": order_collection.count_documents({"status": "PENDING"}),
        "in_progress": order_collection.count_documents({"status": "IN_PROGRESS"}),
        "delivered": order_collection.count_documents({"status": "DELIVERED"})
    }
    msg = f"✅ Uploaded: {count_new} New, {count_updated} Updated."
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": {"username": "Admin"}, # Replace with actual session user
        "stats": stats,
        "message": msg
    })

from bson import ObjectId
from fastapi import Query

# --- Updated Customer Route with Search ---
@app.get("/customers")
async def customer_management(request: Request, filter_type: str = "all", search: str = Query(None)):
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    
    # 4. Filter base query by admin_id
    query = {"admin_id": ObjectId(admin_id_str)}
    
    if search:
        query["$and"] = [
            {"admin_id": ObjectId(admin_id_str)},
            {"$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"phone_number": {"$regex": search, "$options": "i"}}
            ]}
        ]
    
    # 2. Fetch all matching customers first
    # (Filtering by the very last record status is more accurate in Python 
    # than a simple MongoDB dot-notation query for complex histories)
    all_matching_customers = list(customer_collection.find(query).sort("created_at", -1))
    
    processed_customers = []
    
    for c in all_matching_customers:
        # Convert ObjectId to string for the Frontend/Jinja2
        c["_id"] = str(c["_id"])
        
        # Determine Current Status from the LAST entry in the records array
        if c.get("records") and len(c["records"]) > 0:
            last_record = c["records"][-1]
            status = last_record.get("status", "UNKNOWN")
        else:
            status = "NO ORDERS"
            
        c["current_status"] = status

        # 3. Apply Filter Logic based on the ACTUAL current status
        if filter_type == "all":
            processed_customers.append(c)
        elif filter_type == "delivered" and status == "DELIVERED":
            processed_customers.append(c)
        elif filter_type == "pending" and status == "PENDING":
            processed_customers.append(c)
        elif filter_type == "in_progress" and status == "IN_PROGRESS":
            processed_customers.append(c)

    # 4. Fetch Cities for the dropdown modals
    cities = list(cities_collection.find().sort("name", 1))
    
    return templates.TemplateResponse("customers.html", {
        "request": request, 
        "customers": processed_customers,
        "cities": cities,
        "active_filter": filter_type,
        "search_query": search or ""
    })
# --- Add New City ---
# 2. THE UPDATED ROUTE
@app.post("/add-city")
async def add_city(city_name: str = Form(...)):
    print(f"--- [DEBUG] Adding New City: {city_name} ---")
    try:
        # Use the imported 'db' object to access the 'cities' collection
        db["cities"].update_one(
            {"name": city_name}, 
            {"$set": {"name": city_name}}, 
            upsert=True
        )
        return RedirectResponse(url="/customers", status_code=303)
    except Exception as e:
        print(f"--- [ERROR] Failed to add city: {e} ---")
        raise HTTPException(status_code=500, detail="Database error")

@app.post("/add-customer")
async def add_customer(request: Request, name: str = Form(...), phone: str = Form(...), city: str = Form(...), landmark: str = Form(...)):
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)

    # Attach admin_id to the customer document
    customer_collection.insert_one({
        "admin_id": ObjectId(admin_id_str),
        "name": name, 
        "phone_number": phone, 
        "city": city, 
        "landmark": landmark,
        "verified_lat": None, 
        "verified_lng": None, 
        "records": [], 
        "created_at": datetime.utcnow()
    })
    return RedirectResponse(url="/customers", status_code=303)

@app.post("/create-order")
async def create_order(request: Request, customer_id: str = Form(...)):
    # 1. Security Check
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    
    # 2. Find customer (must belong to this admin)
    cust = customer_collection.find_one({
        "_id": ObjectId(customer_id), 
        "admin_id": ObjectId(admin_id_str)
    })
    
    if not cust:
        raise HTTPException(status_code=403, detail="Unauthorized access to customer")

    # 3. Create the Order linked to this admin
    order_data = {
        "admin_id": ObjectId(admin_id_str), # Critical for multi-tenancy
        "customer_id": ObjectId(customer_id),
        "customer_name": cust["name"],
        "city": cust["city"],
        "status": "PENDING",
        "created_at": datetime.utcnow()
    }
    result = order_collection.insert_one(order_data)
    
    # Update Customer Records
    customer_collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$push": {"records": {
            "order_id": result.inserted_id,
            "date": datetime.utcnow(),
            "status": "PENDING"
        }}}
    )
    return RedirectResponse(url="/customers", status_code=303)

@app.post("/upload-customers")
async def upload_customers(request: Request, file: UploadFile = File(...)):
    # 1. Security Check: Get current Admin ID
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    admin_id = ObjectId(admin_id_str)

    contents = await file.read()
    if file.filename.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(contents))
    else:
        df = pd.read_excel(io.BytesIO(contents))

    count_new = 0
    count_updated = 0

    for _, row in df.iterrows():
        phone = str(row['Phone Number']).strip()
        
        customer_data = {
            "admin_id": admin_id, # Link to current admin
            "name": row['Name'],
            "phone_number": phone,
            "city": row['City'],
            "landmark": row['Address & Landmark'],
            "updated_at": datetime.utcnow()
        }

        # Ensure we only find customers belonging to THIS admin
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

    # Fetch updated stats filtered by admin_id
    stats = {
        "drivers": driver_collection.count_documents({"admin_id": admin_id}),
        "customers": customer_collection.count_documents({"admin_id": admin_id}),
        "pending": order_collection.count_documents({"admin_id": admin_id, "status": "PENDING"}),
        "in_progress": order_collection.count_documents({"admin_id": admin_id, "status": "IN_PROGRESS"}),
        "delivered": order_collection.count_documents({"admin_id": admin_id, "status": "DELIVERED"})
    }
    
    msg = f"✅ Uploaded: {count_new} New, {count_updated} Updated."
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": {"username": request.session.get("user_email")},
        "stats": stats,
        "message": msg
    })

from bson import ObjectId

@app.get("/drivers")
async def driver_management(request: Request):
    from app.database import driver_collection, order_collection, db
    
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    
    admin_id = ObjectId(admin_id_str)
    
    # 3. Filter drivers by admin_id
    drivers = list(driver_collection.find({"admin_id": admin_id}))
    cities = list(db["cities"].find()) # Global cities or add admin_id to cities too
    
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
# --- UPDATED ADD DRIVER ---
@app.post("/add-driver")
async def add_driver(request: Request, name: str = Form(...), phone: str = Form(...), password: str = Form(...), cities: list = Form([])):
    from app.utils import get_password_hash
    
    # 1. Get current Admin ID from session
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    
    # 2. Insert with admin_id tag
    driver_collection.insert_one({
        "admin_id": ObjectId(admin_id_str), # The "Owner"
        "name": name,
        "phone_number": phone,
        "password_hash": get_password_hash(password),
        "assigned_cities": cities,
        "is_active": True,
        "created_at": datetime.utcnow()
    })
    return RedirectResponse(url="/drivers", status_code=303)

# --- UPDATED UPDATE DRIVER ---
@app.post("/update-driver")
async def update_driver(driver_id: str = Form(...), name: str = Form(...), phone: str = Form(...), password: str = Form(None), cities: list = Form([]), is_active: str = Form(None)):
    from app.utils import get_password_hash
    new_status = True if is_active == "true" else False
    
    update_data = {
        "name": name,
        "phone_number": phone,
        "assigned_cities": cities,
        "is_active": new_status,
        "last_edited_at": datetime.utcnow()
    }
    
    # Only update password if admin provided a new one
    if password and password.strip():
        update_data["password_hash"] = get_password_hash(password)
        
    driver_collection.update_one({"_id": ObjectId(driver_id)}, {"$set": update_data})
    return RedirectResponse(url="/drivers", status_code=303)

from bson import ObjectId

@app.get("/assignments")
async def delivery_assignments(request: Request):
    from app.database import order_collection, driver_collection
    
    # 1. Security Check: Get current Admin ID
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    admin_id = ObjectId(admin_id_str)

    # 2. Fetch only PENDING orders belonging to THIS admin
    pending_orders = list(order_collection.find({
        "admin_id": admin_id, 
        "status": "PENDING"
    }))
    for order in pending_orders:
        order["_id"] = str(order["_id"])
        order["customer_id"] = str(order["customer_id"])

    # 3. Fetch only ACTIVE drivers belonging to THIS admin
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

@app.post("/assign-delivery")
async def assign_delivery(order_id: str = Form(...), driver_id: str = Form(...)):
    from app.database import order_collection, driver_collection, customer_collection
    
    # 1. Get Driver Info
    driver = driver_collection.find_one({"_id": ObjectId(driver_id)})
    
    # 2. Update Order status and assign driver
    order_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {
            "status": "IN_PROGRESS",
            "assigned_driver_id": ObjectId(driver_id),
            "assigned_driver_name": driver["name"],
            "assigned_at": datetime.utcnow()
        }}
    )

    # 3. Update the specific record inside the Customer document
    customer_collection.update_one(
        {"records.order_id": ObjectId(order_id)},
        {"$set": {
            "records.$.status": "IN_PROGRESS",
            "records.$.driver_name": driver["name"]
        }}
    )
    
    return RedirectResponse(url="/assignments", status_code=303)

# At the top of main.py, ensure these are imported
from app.database import order_collection, customer_collection, driver_collection 
from datetime import datetime, timedelta
import pandas as pd
import io

@app.get("/reports")
async def reports_page(request: Request, period: str = "24h"):
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    admin_id = ObjectId(admin_id_str)

    now = datetime.utcnow()
    threshold = now - (timedelta(days=7) if period == "1w" else timedelta(hours=24))

    # 4. Filter recent orders by threshold AND admin_id
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

@app.get("/export-report")
async def export_report(request: Request, period: str = "24h"):
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        raise HTTPException(status_code=403, detail="Not authenticated")
    
    now = datetime.utcnow()
    threshold = now - (timedelta(days=7) if period == "1w" else timedelta(hours=24))
    
    # 5. Secure Export Query
    orders = list(order_collection.find({
        "admin_id": ObjectId(admin_id_str),
        "created_at": {"$gte": threshold}
    }))
    
    # Prepare data for Excel (same as before)
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
# --- UPDATED DRIVER LOGIN ---
@app.post("/driver/login")
async def driver_login(data: dict):
    phone = data.get("phone_number")
    password = data.get("password")
    
    driver = driver_collection.find_one({"phone_number": phone})
    
    if not driver:
        return {"success": False, "message": "Phone number not registered."}

    # Use .get() to prevent KeyError if the driver doesn't have a password yet
    stored_hash = driver.get("password_hash")
    
    if stored_hash and verify_password(password, stored_hash):
        if not driver.get("is_active"):
            return {"success": False, "message": "Account inactive. Contact Admin."}
        
        return {
            "success": True,
            "driver": {
                "id": str(driver["_id"]),
                "name": driver["name"],
                "cities": driver.get("assigned_cities", [])
            }
        }
    
    return {"success": False, "message": "Invalid password."}

# --- UPDATED DRIVER ORDER LIST (Includes Address) ---
# --- 2. Updated Driver Orders with Verification Status ---
from fastapi import FastAPI, Request, Form
from bson import ObjectId
from app.database import order_collection, customer_collection, driver_collection

@app.get("/driver/orders/{city}")
async def get_driver_orders(city: str, driver_id: str):
    print(f"\n--- DEBUG: Driver {driver_id} checking city '{city}' ---")
    
    # 1. Check for Active Job
    active_job = order_collection.find_one({
        "assigned_driver_id": ObjectId(driver_id),
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

    # 2. Fetch Pending Orders (Case-Insensitive Regex Match)
    query = {"city": {"$regex": f"^{city.strip()}$", "$options": "i"}, "status": "PENDING"}
    orders = list(order_collection.find(query))
    
    print(f"DEBUG: Found {len(orders)} pending orders in DB for '{city}'")

    processed = []
    for o in orders:
        o["_id"] = str(o["_id"])
        o["customer_id"] = str(o["customer_id"])
        cust = customer_collection.find_one({"_id": ObjectId(o["customer_id"])})
        if cust:
            o["address"] = cust.get("landmark", "No Address")
            o["is_verified"] = True if cust.get("verified_lat") else False
            processed.append(o)

    # Sort: Verified GPS orders at the top
    processed.sort(key=lambda x: x.get("is_verified", False), reverse=True)
    return {"success": True, "has_active": False, "orders": processed}
# --- COMPLETE DELIVERY & UPDATE GPS ---
# --- COMPLETE DELIVERY & SET GPS ---
@app.post("/driver/complete-delivery")
async def complete_delivery(order_id: str = Form(...), lat: str = Form(...), long: str = Form(...)):
    order = order_collection.find_one({"_id": ObjectId(order_id)})
    if not order:
        return {"success": False, "message": "Order not found"}

    # Update Customer permanent location
    customer_collection.update_one(
        {"_id": order["customer_id"]},
        {"$set": {"verified_lat": lat, "verified_lng": long}}
    )
    
    # Mark order as Delivered
    order_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": "DELIVERED", "delivered_at": datetime.utcnow()}}
    )
    
    # Update status in customer record history
    customer_collection.update_one(
        {"records.order_id": ObjectId(order_id)},
        {"$set": {"records.$.status": "DELIVERED"}}
    )
    return {"success": True}

@app.post("/assign-delivery")
async def assign_delivery(request: Request, order_id: str = Form(...), driver_id: str = Form(...)):
    print(f"\n--- DEBUG: Assignment Requested ---")
    print(f"Order ID: {order_id} | Driver ID: {driver_id}")
    
    try:
        o_id, d_id = ObjectId(order_id), ObjectId(driver_id)
        driver = driver_collection.find_one({"_id": d_id})
        
        # 1. Update Order
        order_collection.update_one(
            {"_id": o_id},
            {"$set": {"status": "IN_PROGRESS", "assigned_driver_id": d_id, "assigned_driver_name": driver["name"], "assigned_at": datetime.utcnow()}}
        )

        # 2. Update Customer Record
        customer_collection.update_one(
            {"records.order_id": o_id},
            {"$set": {"records.$.status": "IN_PROGRESS", "records.$.driver_name": driver["name"]}}
        )

        # 3. Handle Response based on Accept Header
        accept_header = request.headers.get("accept", "")
        if "application/json" in accept_header:
            print("DEBUG: Sending JSON Success to Mobile App")
            return {"success": True, "message": "Order assigned successfully!"}
        
        print("DEBUG: Redirecting Admin Web Panel to Assignments")
        return RedirectResponse(url="/assignments", status_code=303)

    except Exception as e:
        print(f"DEBUG CRITICAL ERROR in /assign-delivery: {e}")
        return {"success": False, "message": str(e)}

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, Query

from bson import ObjectId
from fastapi import Query, HTTPException

import math

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two points in KM using Haversine formula."""
    try:
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return 999999.0 # Sort unverified to the bottom
        
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        R = 6371.0 
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    except:
        return 999999.0

@app.get("/driver/orders")
async def get_driver_orders(driver_id: str, cities: str = Query(""), lat: str = None, lng: str = None):
    try:
        d_obj_id = ObjectId(driver_id)
        city_list = [c.strip() for c in cities.split(",") if c.strip()]

        # 1. Multi-Tenant Security: Fetch Driver to get their Admin ID
        driver = driver_collection.find_one({"_id": d_obj_id})
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        admin_id = driver.get("admin_id")

        # 2. Check for Active Job (IN_PROGRESS)
        active_job = order_collection.find_one({
            "assigned_driver_id": d_obj_id,
            "status": "IN_PROGRESS"
        })

        if active_job:
            # --- CRITICAL SERIALIZATION OF ALL ID FIELDS ---
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

        # 3. Fetch Pending Orders for THIS Admin and assigned Cities
        query = {
            "admin_id": admin_id, 
            "city": {"$in": city_list}, 
            "status": "PENDING"
        }
        orders = list(order_collection.find(query))

        processed = []
        for o in orders:
            # Stringify every MongoDB ID to prevent serialization crash
            o["_id"] = str(o["_id"])
            o["customer_id"] = str(o["customer_id"])
            o["admin_id"] = str(o.get("admin_id", ""))

            cust = customer_collection.find_one({"_id": ObjectId(o["customer_id"])})
            if cust:
                o["address"] = cust.get("landmark", "No Address")
                o["phone"] = cust.get("phone_number")
                o["verified_lat"] = cust.get("verified_lat")
                o["verified_lng"] = cust.get("verified_lng")
                
                # --- CALCULATE DISTANCE FOR SORTING ---
                o["distance"] = calculate_distance(lat, lng, o["verified_lat"], o["verified_lng"])
                o["is_verified"] = True if o["verified_lat"] else False
                processed.append(o)

        # 4. Senior Logic Sorting: Nearest GPS verified first, then unverified
        processed.sort(key=lambda x: (not x["is_verified"], x["distance"]))
        
        return {"success": True, "has_active": False, "orders": processed}

    except Exception as e:
        print(f"CRITICAL BACKEND ERROR: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
@app.get("/statistics")
async def statistics_page(request: Request, period: str = "7d"):
    now = datetime.utcnow()
    # 1. Date Logic
    if period == "24h":
        start_date, date_format = now - timedelta(hours=24), "%H:00"
    elif period == "1w":
        start_date, date_format = now - timedelta(days=7), "%Y-%m-%d"
    else:
        start_date, date_format = now - timedelta(days=30), "%Y-%m-%d"

    # 2. Fetch Data
    query = {"created_at": {"$gte": start_date}}
    orders = list(order_collection.find(query))
    
    if not orders:
        return templates.TemplateResponse("statistics.html", {"request": request, "period": period, "no_data": True})

    # 3. Processing with Pandas
    df = pd.DataFrame(orders)
    df['date_label'] = df['created_at'].dt.strftime(date_format)
    
    trend = df.groupby('date_label').size().to_dict()
    city_dist = df['city'].value_counts().to_dict()
    status_dist = df['status'].value_counts().to_dict()
    driver_perf = df[df['status'] == "DELIVERED"]['assigned_driver_name'].value_counts().head(5).to_dict()

    # 4. Final Dictionary (MATCH THESE KEYS IN HTML)
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

# --- ADMIN PROFILE VIEW ---
@app.get("/profile")
async def profile_view(request: Request):
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    
    admin_id = ObjectId(admin_id_str)
    admin = admin_collection.find_one({"_id": admin_id})
    
    # Fetch drivers belonging to this admin to show in profile
    my_drivers = list(driver_collection.find({"admin_id": admin_id}))
    for d in my_drivers:
        d["_id"] = str(d["_id"])
        # Format date for better display
        d["created_at_str"] = d.get("created_at").strftime("%d %b %Y") if d.get("created_at") else "N/A"

    return templates.TemplateResponse("profile.html", {
        "request": request, 
        "admin": admin,
        "drivers": my_drivers
    })

# --- UPDATE ADMIN PROFILE ---
@app.post("/update-profile")
async def update_profile(
    request: Request, 
    phone: str = Form(None), 
    age: str = Form(None), 
    agency_name: str = Form(None)
):
    admin_id = ObjectId(request.session.get("admin_id"))
    
    update_data = {
        "phone": phone,
        "age": age,
        "agency_name": agency_name,
        "updated_at": datetime.utcnow()
    }
    
    admin_collection.update_one({"_id": admin_id}, {"$set": update_data})
    return RedirectResponse(url="/profile?msg=Profile updated successfully", status_code=303)

# --- DELETE DRIVER ROUTE ---
@app.post("/delete-driver")
async def delete_driver(request: Request, driver_id: str = Form(...)):
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    
    admin_id = ObjectId(admin_id_str)
    
    # Securely delete only if the driver belongs to this admin
    driver_collection.delete_one({
        "_id": ObjectId(driver_id), 
        "admin_id": admin_id
    })
    
    return RedirectResponse(url="/drivers?msg=Driver deleted", status_code=303)

# Add this route to your main.py
# --- ADD THIS TO THE TOP OF main.py ---
from app.database import db, admin_collection, driver_collection, customer_collection, order_collection

# Define cities_collection explicitly to fix the NameError
cities_collection = db["cities"] 

# --- ADD THESE NEW ROUTES TO main.py ---

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/?message=Logged out successfully", status_code=303)

@app.get("/profile")
async def profile_view(request: Request):
    admin_id_str = request.session.get("admin_id")
    if not admin_id_str:
        return RedirectResponse(url="/", status_code=303)
    
    admin_id = ObjectId(admin_id_str)
    admin = admin_collection.find_one({"_id": admin_id})
    
    # Fetch drivers managed by this admin
    my_drivers = list(driver_collection.find({"admin_id": admin_id}))
    for d in my_drivers:
        d["_id"] = str(d["_id"])
        # Format registration date
        d["date_str"] = d.get("created_at").strftime("%d %b %Y") if d.get("created_at") else "N/A"

    return templates.TemplateResponse("profile.html", {
        "request": request, 
        "admin": admin,
        "drivers": my_drivers
    })

@app.post("/update-profile")
async def update_profile(
    request: Request, 
    phone: str = Form(None), 
    age: str = Form(None), 
    agency_name: str = Form(None)
):
    admin_id = ObjectId(request.session.get("admin_id"))
    
    update_data = {
        "phone": phone,
        "age": age,
        "agency_name": agency_name,
        "updated_at": datetime.utcnow()
    }
    
    admin_collection.update_one({"_id": admin_id}, {"$set": update_data})
    return RedirectResponse(url="/profile", status_code=303)