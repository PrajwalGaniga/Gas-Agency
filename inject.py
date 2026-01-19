# inject.py
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from app.database import (
    db, admin_collection, driver_collection, 
    customer_collection, order_collection, 
    driver_audit_collection, driver_location_collection
)
from app.utils import get_password_hash

# Admin Credentials provided by user
ADMIN_ID = ObjectId("696613a87cf8f8cdf4e9b1d5")
ADMIN_EMAIL = "prajwalganiga06@gmail.com"

# Coordinates for Mangalore/Padil Area
LOCATIONS = {
    "center": {"lat": 12.8681, "lng": 74.8795}, # Padil Junction
    "cust1": {"lat": 12.8695, "lng": 74.8810},  # Near Padil Station
    "cust2": {"lat": 12.8650, "lng": 74.8750},  # Bajal Area
    "cust3": {"lat": 12.8720, "lng": 74.8850},  # Alape
    "cust4": {"lat": 12.8620, "lng": 74.8800}   # Kannur
}

async def inject_test_data():
    print("--- 💉 Starting Data Injection ---")

    # 1. Ensure Admin exists (or update if provided ID is different)
    # We use update_one with upsert to match your exact provided _id
    admin_collection.update_one(
        {"_id": ADMIN_ID},
        {"$set": {
            "username": "Prajwal Ganiga",
            "email": ADMIN_EMAIL,
            "password_hash": "$2b$12$1ZLjlFgrewgImPE1dB9rCuskoZA2Cro.kyb6wfLiDXtmabOPYZrMm",
            "role": "super_admin"
        }},
        upsert=True
    )
    print(f"✅ Admin Linked: {ADMIN_EMAIL}")

    # 2. Create 4 Customers in Mangalore/Padil
    customer_ids = []
    customers = [
        {"name": "Suresh Kumar", "phone": "9876543210", "loc": LOCATIONS["cust1"], "pin": "575007"},
        {"name": "Anitha Rao", "phone": "9876543211", "loc": LOCATIONS["cust2"], "pin": "575007"},
        {"name": "Ramesh Shetty", "phone": "9876543212", "loc": LOCATIONS["cust3"], "pin": "575007"},
        {"name": "Vikram Das", "phone": "9876543213", "loc": LOCATIONS["cust4"], "pin": "575007"}
    ]

    for c in customers:
        res = customer_collection.update_one(
            {"phone_number": c["phone"]},
            {"$set": {
                "admin_id": ADMIN_ID,
                "name": c["name"],
                "phone_number": c["phone"],
                "city": "Mangalore",
                "landmark": f"Near Padil, {c['name']} House",
                "pincode": c["pin"],
                "verified_lat": c["loc"]["lat"],
                "verified_lng": c["loc"]["lng"],
                "records": [],
                "created_at": datetime.utcnow()
            }},
            upsert=True
        )
        # Fetch the ID of the inserted/updated customer
        doc = customer_collection.find_one({"phone_number": c["phone"]})
        customer_ids.append(doc["_id"])
    
    print(f"✅ Created 4 Customers in Padil/Mangalore")

    # 3. Create a Driver
    driver_pass = get_password_hash("driver123")
    driver_res = driver_collection.update_one(
        {"phone_number": "7001122334"},
        {"$set": {
            "admin_id": ADMIN_ID,
            "name": "Padil Express Driver",
            "phone_number": "7001122334",
            "password_hash": driver_pass,
            "assigned_cities": ["Mangalore"],
            "is_active": True,
            "last_seen": datetime.utcnow(),
            "current_lat": LOCATIONS["center"]["lat"],
            "current_lng": LOCATIONS["center"]["lng"],
            "created_at": datetime.utcnow()
        }},
        upsert=True
    )
    driver_doc = driver_collection.find_one({"phone_number": "7001122334"})
    driver_id = driver_doc["_id"]
    print(f"✅ Created Driver: Padil Express Driver")

    # 4. Create Audit Logs (Check Login/Working Hours)
    driver_audit_collection.insert_many([
        {"driver_id": driver_id, "event": "LOGIN", "timestamp": datetime.utcnow() - timedelta(hours=4)},
        {"driver_id": driver_id, "event": "LOGOUT", "timestamp": datetime.utcnow() - timedelta(hours=2)},
        {"driver_id": driver_id, "event": "LOGIN", "timestamp": datetime.utcnow() - timedelta(minutes=30)}
    ])
    print(f"✅ Injected Driver Audit History")

    # 5. Create Orders & Locations for Tracking Path
    # Order 1: Delivered
    order1 = order_collection.insert_one({
        "admin_id": ADMIN_ID,
        "customer_id": customer_ids[0],
        "customer_name": "Suresh Kumar",
        "city": "Mangalore",
        "status": "DELIVERED",
        "assigned_driver_id": driver_id,
        "assigned_driver_name": "Padil Express Driver",
        "created_at": datetime.utcnow() - timedelta(hours=1)
    })

    # Order 2: In Progress (Live on map)
    order2 = order_collection.insert_one({
        "admin_id": ADMIN_ID,
        "customer_id": customer_ids[1],
        "customer_name": "Anitha Rao",
        "city": "Mangalore",
        "status": "IN_PROGRESS",
        "assigned_driver_id": driver_id,
        "assigned_driver_name": "Padil Express Driver",
        "created_at": datetime.utcnow() - timedelta(minutes=20)
    })
    print(f"✅ Created 1 Delivered and 1 Active Order")

    # 6. Injected simulated path movement for the map
    path_points = [
        {"lat": 12.8681, "lng": 74.8795}, # Start Padil
        {"lat": 12.8685, "lng": 74.8800},
        {"lat": 12.8690, "lng": 74.8805}  # Current
    ]
    for p in path_points:
        driver_location_collection.insert_one({
            "driver_id": driver_id,
            "lat": p["lat"],
            "lng": p["lng"],
            "timestamp": datetime.utcnow()
        })
    print(f"✅ Injected GPS Path History")

    print("\n--- 🏁 Injection Complete! ---")
    print("You can now login to the Admin Dashboard and view the Live Audit and Map.")

if __name__ == "__main__":
    asyncio.run(inject_test_data())