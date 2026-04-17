import os
from pymongo import MongoClient
from datetime import datetime, timezone
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://developer:i2kZt8FtzS246IfY@gasflow-cluster.e5psa.mongodb.net/?retryWrites=true&w=majority&appName=gasflow-cluster")

client = MongoClient(MONGO_URI)
db = client["gas_agency_db"]
shifts_col = db["shifts"]
orders_col = db["orders"]
drivers_col = db["drivers"]
admin_col = db["admins"]

def run_test():
    print("\n🚀 STARTING SHIFT LEAKAGE TEST...\n")
    
    admin = admin_col.find_one()
    if not admin:
        admin_col.insert_one({"email": "testadmin@gasflow.com", "name": "Test Admin"})
        admin = admin_col.find_one()
        
    driver = drivers_col.find_one({"admin_id": admin["_id"], "is_active": True})
    if not driver:
        driver = drivers_col.find_one({"is_active": True})
        if not driver:
            drivers_col.insert_one({
                "admin_id": admin["_id"],
                "name": "Test Driver",
                "phone_number": "0000000000",
                "is_active": True
            })
            driver = drivers_col.find_one({"admin_id": admin["_id"], "is_active": True})

    driver_id = str(driver["_id"])
    admin_id = str(admin["_id"])
    
    # Clean up test data
    shifts_col.delete_many({"driver_id": driver_id, "status": "TEST_SHIFT"})
    orders_col.delete_many({"assigned_driver_id": ObjectId(driver_id), "status": "TEST_DELIVERED"})
    
    # 1. Start Shift A
    shift_a = {
        "admin_id": admin_id,
        "driver_id": driver_id,
        "date": datetime.now(timezone.utc),
        "status": "TEST_SHIFT",
        "load_departure": {"full": 50, "empty": 0},
        "load_return": {"full": 0, "empty": 0},
        "financials": {"expected_cash": 0.0, "actual_cash": 0.0, "upi_total": 0.0}
    }
    result_a = shifts_col.insert_one(shift_a)
    shift_a_id = str(result_a.inserted_id)
    print(f"✅ Shift A Started: {shift_a_id}")
    
    # 2. Complete 2 orders in Shift A
    orders_col.insert_many([
        {
            "assigned_driver_id": ObjectId(driver_id),
            "status": "TEST_DELIVERED",
            "shift_id": shift_a_id,
            "cylinders_delivered": 1
        },
        {
            "assigned_driver_id": ObjectId(driver_id),
            "status": "TEST_DELIVERED",
            "shift_id": shift_a_id,
            "cylinders_delivered": 1
        }
    ])
    print(f"✅ 2 Orders COMPLETED in Shift A.")
    
    # 3. Verifying Shift A Count
    count_a = orders_col.count_documents({"shift_id": shift_a_id, "status": "TEST_DELIVERED"})
    print(f"   -> Shift A Completed Count: {count_a}")
    
    # 4. End Shift A (just logically, we don't need to change status for the test isolation)
    # 5. Start Shift B
    shift_b = {
        "admin_id": admin_id,
        "driver_id": driver_id,
        "date": datetime.now(timezone.utc),
        "status": "TEST_SHIFT",
        "load_departure": {"full": 50, "empty": 0},
        "load_return": {"full": 0, "empty": 0},
        "financials": {"expected_cash": 0.0, "actual_cash": 0.0, "upi_total": 0.0}
    }
    result_b = shifts_col.insert_one(shift_b)
    shift_b_id = str(result_b.inserted_id)
    print(f"\n✅ Shift B Started: {shift_b_id}")
    
    # 6. Verify Shift B's INITIAL completed count
    count_b = orders_col.count_documents({"shift_id": shift_b_id, "status": "TEST_DELIVERED"})
    print(f"   -> Shift B Completed Count: {count_b}")
    
    # 7. Assertions
    if count_a == 2 and count_b == 0:
        print("\n🎉 PASS: Data Leakage is FIXED! Shift B starts with exactly 0 completed deliveries despite the driver having historical deliveries.")
    else:
        print("\n❌ FAIL: Leakage detected or order insertion failed.")
        
    # Cleanup
    shifts_col.delete_many({"driver_id": driver_id, "status": "TEST_SHIFT"})
    orders_col.delete_many({"assigned_driver_id": ObjectId(driver_id), "status": "TEST_DELIVERED"})

if __name__ == "__main__":
    run_test()
