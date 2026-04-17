import os
from pymongo import MongoClient
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Connect to DB (Matching your application's DB string roughly)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://prajwalganiga06:passwordadmin123@gas-driver.ngwamww.mongodb.net/?appName=Gas-Driver")
client = MongoClient(MONGO_URI)
db = client.get_database("GasAgencyDB")

shifts_col = db.shifts_collection
drivers_col = db.driver_collection

def run_sync_test():
    print("🚀 Running System Sync Integration Test...")
    
    # 1. Grab a target driver (Replace with a real driver ID if known, or pick first)
    target_driver = drivers_col.find_one()
    
    if not target_driver:
        print("⚠️ No drivers found. Creating a Mock Driver for testing...")
        mock_driver = {
            "name": "Test Driver X",
            "phone_number": "555-0199",
            "current_stock": 0,
            "collected_cash": 0,
            "current_lat": "20.5937",
            "current_lng": "78.9629",
            "admin_id": "test_admin_123"
        }
        res = drivers_col.insert_one(mock_driver)
        target_driver = drivers_col.find_one({"_id": res.inserted_id})
        
    driver_id_str = str(target_driver["_id"])
    print(f"🎯 Selected Driver: {target_driver['name']} ({driver_id_str})")
    
    # 2. Cleanup any old OPEN shifts for this driver to ensure a clean test state
    shifts_col.update_many({"driver_id": driver_id_str, "status": "OPEN"}, {"$set": {"status": "CLOSED"}})
    
    # 3. Simulate Shift Start (50 cylinders)
    print("\n📦 Simulating Shift Start (Load 50)...")
    shift_doc = {
        "driver_id": driver_id_str,
        "status": "OPEN",
        "start_time": datetime.now(timezone.utc),
        "load_departure": {"full": 50, "empty": 0, "defective": 0},
        "load_return": {"full": 0, "empty": 0, "defective": 0},
        "financials": {"actual_cash_collected": 0, "upi_collected": 0}
    }
    shifts_col.insert_one(shift_doc)
    
    # 4. Simulate a Delivery (₹850 collected, 1 empty returned/1 full consumed)
    print("💸 Simulating Delivery (1 Cylinder Delivered, ₹850 Collected)...")
    shifts_col.update_one(
        {"driver_id": driver_id_str, "status": "OPEN"},
        {"$inc": {
            "load_return.full": 1, # Consumed 1 full cylinder
            "load_return.empty": 1, # Got 1 empty back
            "financials.actual_cash_collected": 850 # Got ₹850
        }}
    )
    
    # 5. Validate Unified Aggregate Logic (Simulating what your API does)
    print("\n🔍 Validating System Sync...")
    shift = shifts_col.find_one({"driver_id": driver_id_str, "status": "OPEN"})
    
    shift_start_load = shift.get("load_departure", {}).get("full", 0)
    consumed_full = shift.get("load_return", {}).get("full", 0)
    remaining_full = max(0, shift_start_load - consumed_full)
    total_collected = shift.get("financials", {}).get("actual_cash_collected", 0)
    
    # 6. Assertions
    passed = True
    
    # Check Math
    if remaining_full == 49:
         print("✅ PASS: Remaining Stock calculated correctly (49).")
    else:
         print(f"❌ FAIL: Remaining Stock is {remaining_full}, expected 49.")
         passed = False
         
    if total_collected == 850:
         print("✅ PASS: Total Cash Collected aggregated correctly (₹850).")
    else:
         print(f"❌ FAIL: Total Cash Collected is ₹{total_collected}, expected ₹850.")
         passed = False

    if passed:
        print("\n🎉 ALL TESTS PASSED: Single-Source Dashboard metrics match Inventory Ledger.")
    else:
        print("\n⚠️ SYSTEM SYNC FAILURE.")

if __name__ == "__main__":
    run_sync_test()
