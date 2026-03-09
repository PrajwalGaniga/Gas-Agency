from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["Gas-Delivery"]

def cleanup():
    collections_to_clear = [
        "customers",
        "drivers",
        "orders",
        "shifts",
        "driver_audit_logs",
        "driver_locations",
        "customer_change_requests",
        "daily_stats",
        "counters"
    ]
    
    print(f"🧹 Starting Database Cleanup in '{db.name}'...")
    
    for coll in collections_to_clear:
        count = db[coll].count_documents({})
        db[coll].delete_many({})
        print(f"🗑️ Cleared {count} records from '{coll}'.")
        
    # Re-initialize counters if necessary
    db["counters"].update_one(
        {"_id": "customer_id"},
        {"$set": {"sequence_value": 1000}},
        upsert=True
    )
    print("✅ Counter 'customer_id' reset to 1000.")
    print("✨ Cleanup complete! Admins have been preserved.")

if __name__ == "__main__":
    confirm = input("ARE YOU SURE? This will delete all operational data (customers, drivers, orders, etc.). Type 'YES' to confirm: ")
    if confirm == "YES":
        cleanup()
    else:
        print("❌ Cleanup cancelled.")
