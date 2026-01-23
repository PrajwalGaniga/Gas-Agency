import os
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from app.database import (
    db, customer_collection, order_collection, 
    driver_collection, driver_location_collection, driver_audit_collection
)
from app.utils import get_password_hash

# --- 🛰️ TEST CONFIGURATION ---
ADMIN_EMAIL = "prajwalganiga06@gmail.com"
DRIVER_PHONE = "7001122334"
BASE_LAT = 12.86981
BASE_LNG = 74.843008

def setup_test_data():
    print("🚀 Starting Pro Map Test Data Insertion...")

    # 1. Verify/Setup Admin & Driver
    admin = db["admins"].find_one({"email": ADMIN_EMAIL})
    if not admin:
        print("❌ Admin not found. Please sign up first.")
        return
    
    # Ensure Driver exists with correct password
    driver_collection.update_one(
        {"phone_number": DRIVER_PHONE},
        {"$set": {
            "admin_id": admin["_id"],
            "name": "Padil Express Driver",
            "password_hash": get_password_hash("1234"),
            "is_active": True,
            "assigned_cities": ["Mangalore"],
            "current_lat": BASE_LAT + 0.005,
            "current_lng": BASE_LNG + 0.005,
            "last_seen": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    driver = driver_collection.find_one({"phone_number": DRIVER_PHONE})

    # 2. Define 3 Test Customers around Padil
    test_customers = [
        {"name": "Test Alpha (Delivered)", "lat": 12.8710, "lng": 74.8440, "status": "DELIVERED"},
        {"name": "Test Beta (Delivered)", "lat": 12.8750, "lng": 74.8480, "status": "DELIVERED"},
        {"name": "Test Gamma (Ongoing)", "lat": 12.8790, "lng": 74.8520, "status": "IN_PROGRESS"},
    ]

    # 3. Create Orders & Generate Path Breadcrumbs
    now = datetime.now(timezone.utc)
    path_points = []
    
    for i, data in enumerate(test_customers):
        # Insert Customer
        c_res = customer_collection.insert_one({
            "admin_id": admin["_id"],
            "name": data["name"],
            "phone_number": f"900000000{i}",
            "city": "Mangalore",
            "landmark": f"Near Padil Point {i+1}",
            "verified_lat": data["lat"],
            "verified_lng": data["lng"],
            "created_at": now - timedelta(hours=5)
        })
        
        # Insert Order
        o_time = now - timedelta(hours=4 - i) # Spread deliveries across time
        order_collection.insert_one({
            "admin_id": admin["_id"],
            "customer_id": c_res.inserted_id,
            "customer_name": data["name"],
            "status": data["status"],
            "assigned_driver_id": driver["_id"],
            "assigned_driver_name": driver["name"],
            "created_at": o_time,
            "delivered_at": o_time + timedelta(minutes=30) if data["status"] == "DELIVERED" else None
        })

        # 🛰️ Simulate GPS breadcrumbs moving toward this customer
        for step in range(5):
            offset = step * 0.0005
            path_points.append({
                "driver_id": driver["_id"],
                "lat": BASE_LAT + (i * 0.004) + offset,
                "lng": BASE_LNG + (i * 0.004) + offset,
                "timestamp": o_time - timedelta(minutes=20 - (step * 4))
            })

    # 4. Insert GPS Pings into Location Collection
    driver_location_collection.insert_many(path_points)

    # 5. Update Driver's Final Live Position to the last delivery point
    last_point = path_points[-1]
    driver_collection.update_one(
        {"_id": driver["_id"]},
        {"$set": {"current_lat": last_point["lat"], "current_lng": last_point["lng"]}}
    )

    print(f"✅ SUCCESS: 3 Customers, 3 Orders, and {len(path_points)} GPS Breadcrumbs inserted.")
    print(f"📍 View result at: http://127.0.0.1:8000/track/{driver['_id']}")

if __name__ == "__main__":
    setup_test_data()