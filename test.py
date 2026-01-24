from datetime import datetime, timedelta, timezone
from bson import ObjectId
from app.database import db, customer_collection, order_collection, driver_collection, driver_location_collection
from app.utils import get_password_hash

def run_pro_test():
    admin = db["admins"].find_one({"email": "prajwalganiga06@gmail.com"})
    if not admin: return print("❌ Admin not found")
    
    # 1. Setup Driver
    driver_collection.update_one({"phone_number": "7001122334"}, {"$set": {
        "admin_id": admin["_id"], "name": "Padil Pro Driver", 
        "password_hash": get_password_hash("1234"), "is_active": True, "assigned_cities": ["Mangalore"]
    }}, upsert=True)
    driver = driver_collection.find_one({"phone_number": "7001122334"})

    # 2. Add Customers & Orders
    locs = [
        {"name": "C1 (Padil Center)", "lat": 12.86981, "lng": 74.84300},
        {"name": "C2 (Near Railway)", "lat": 12.87150, "lng": 74.84500},
        {"name": "C3 (Bridge Side)", "lat": 12.87300, "lng": 74.84800},
    ]
    
    now = datetime.now(timezone.utc)
    for i, l in enumerate(locs):
        c = customer_collection.insert_one({"admin_id": admin["_id"], "name": l["name"], "city": "Mangalore", "landmark": "Padil Area", "verified_lat": l["lat"], "verified_lng": l["lng"]})
        order_collection.insert_one({"admin_id": admin["_id"], "customer_id": c.inserted_id, "customer_name": l["name"], "status": "PENDING", "assigned_driver_id": driver["_id"], "created_at": now})
        
        # 🛰️ Mock path pings for Admin Map Pathing
        driver_location_collection.insert_one({"driver_id": driver["_id"], "lat": l["lat"] - 0.0005, "lng": l["lng"] - 0.0005, "timestamp": now - timedelta(minutes=10)})

    print("✅ Test Data Injected. Open Map to see Optimized Pathing!")

if __name__ == "__main__": run_pro_test()