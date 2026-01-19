# app/database.py
from pymongo import MongoClient
import certifi
import os
import os
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv() # Load variables from .env

MONGO_URI = os.getenv("MONGO_URI")



print("--------------------------------------------------")
print("🔄 CONNECTING TO MONGODB ATLAS...")

try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    client.admin.command('ping')
    print("✅ SUCCESS: Connected to MongoDB Atlas safely!")

except Exception as e:
    print(f"⚠️ Secure connect failed: {e}")
    print("👉 Retrying with SSL Bypass (Fix for College WiFi)...")

    try:
        client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
        client.admin.command('ping')
        print("✅ SUCCESS: Connected to MongoDB Atlas (SSL Bypassed).")

    except Exception as e2:
        print("❌ CRITICAL ERROR: Could not connect to MongoDB Atlas")
        print(f"Details: {e2}")
        client = None

print("--------------------------------------------------")

# ✅ ALWAYS DEFINE COLLECTIONS (NO MATTER WHAT)
if client:
    db = client["Gas-Delivery"]
else:
    db = None

admin_collection = db["admins"] if db is not None else None
driver_collection = db["drivers"] if db is not None else None
customer_collection = db["customers"] if db is not None else None
order_collection = db["orders"] if db is not None else None
# 👇 ADD THIS LINE
cities_collection = db["cities"]

driver_audit_collection = db["driver_audit_logs"]
driver_location_collection = db["driver_locations"]