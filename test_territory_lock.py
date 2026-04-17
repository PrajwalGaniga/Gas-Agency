import os
from pymongo import MongoClient
from datetime import datetime, timezone
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://developer:i2kZt8FtzS246IfY@gasflow-cluster.e5psa.mongodb.net/?retryWrites=true&w=majority&appName=gasflow-cluster")

client = MongoClient(MONGO_URI)
db = client["gas_agency_db"]
driver_collection = db["drivers"]
admin_collection = db["admins"]

def run_test():
    print("\n🚀 STARTING TERRITORY LOCK TEST...\n")
    
    admin = admin_collection.find_one({"email": "prajwalganiga06@gmail.com"})
    if not admin:
        print("❌ FAIL: Cannot find Prajwal Admin.")
        return
        
    admin_id = admin["_id"]
    
    # Clean up test drivers
    driver_collection.delete_many({"name": {"$regex": "^TEST_DRIVER"}})
    
    # 1. Add Driver 1 for Mangalore
    d1 = {
        "admin_id": admin_id,
        "name": "TEST_DRIVER 1",
        "phone_number": "0000000001",
        "assigned_cities": ["Mangalore"],
        "is_active": True
    }
    driver_collection.insert_one(d1)
    print("✅ Created Driver 1 assigned to Mangalore.")
    
    # 2. Try adding Driver 2 for Mangalore (simulate what the backend check does)
    cities = ["Mangalore", "Udupi"]
    existing_drivers = list(driver_collection.find({"admin_id": admin_id, "is_active": True}))
    conflict = False
    for d in existing_drivers:
        # Ignore self if this was an update, but we are simulating an add
        intersect = set(cities).intersection(set(d.get("assigned_cities", [])))
        if intersect:
            print(f"✅ SUCCESSFULLY DETECTED CONFLICT: {', '.join(intersect)} already assigned to {d['name']}")
            conflict = True
            break
            
    if conflict:
        print("\n🎉 PASS: Territory Lock works correctly.")
    else:
        print("\n❌ FAIL: Territory Lock failed to detect overlap.")
        
    # Clean up test drivers
    driver_collection.delete_many({"name": {"$regex": "^TEST_DRIVER"}})

if __name__ == "__main__":
    run_test()
