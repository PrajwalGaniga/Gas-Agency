# delete_data.py
import certifi
from pymongo import MongoClient
from app.database import MONGO_URI # Reuse your existing connection string

def clear_database():
    print("--------------------------------------------------")
    print("⚠️  DATABASE CLEANUP STARTING...")
    
    try:
        # Connect using your existing URI and SSL certificate fix
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client["Gas-Delivery"] # Your database name
        
        # List of collections to clear
        collections = ["customers", "drivers", "orders", "cities", "temp_signups"]
        
        print(f"Connected to: {db.name}")
        
        confirm = input("\n🔥 WARNING: This will delete ALL records in your database. Type 'DELETE' to confirm: ")
        
        if confirm == "DELETE":
            for coll_name in collections:
                result = db[coll_name].delete_many({})
                print(f"✅ Cleared '{coll_name}': {result.deleted_count} records removed.")
            print("\n✨ Database is now clean and ready for Multi-Tenant testing!")
        else:
            print("❌ Cleanup cancelled. No data was deleted.")

    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
    finally:
        print("--------------------------------------------------")

if __name__ == "__main__":
    clear_database()