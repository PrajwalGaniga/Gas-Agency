import os
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from app.database import driver_collection, daily_stats_collection
from admin import get_detailed_driver_metrics, ist_day_start, ist_day_end, ist_now

def run_midnight_sync():
    """
    Senior Sync Logic: Freezes yesterday's raw GPS pings into a permanent 
    summary record for every driver.
    """
    # 1. Identify 'Yesterday' in IST
    yesterday_date = (ist_now() - timedelta(days=1)).date()
    start_utc = ist_day_start(yesterday_date)
    end_utc = ist_day_end(yesterday_date)

    print(f"--- 🌙 STARTING MIDNIGHT SYNC for {yesterday_date} ---")

    # 2. Process every driver in the system
    drivers = list(driver_collection.find({}))
    
    for d in drivers:
        # Calculate final metrics using the high-precision GPS gap logic
        metrics = get_detailed_driver_metrics(d["_id"], start_utc, end_utc)
        
        if not metrics["days"]:
            print(f"Skipping {d['name']} (No activity detected)")
            continue
            
        day_data = metrics["days"][0] # Focus on the specific day processed

        # 3. Create the permanent summary record
        record = {
            "driver_id": d["_id"],
            "driver_name": d["name"],
            "date": datetime.combine(yesterday_date, datetime.min.time()),
            "total_work_seconds": metrics["summary"]["total_hours"] * 3600,
            "duration_str": day_data["duration"],
            "deliveries_completed": day_data["deliveries"],
            "first_active": day_data["first_ping"],
            "last_active": day_data["last_ping"],
            "synced_at": datetime.now(timezone.utc)
        }

        # 4. Upsert into daily_stats (Prevent duplicates)
        daily_stats_collection.update_one(
            {"driver_id": d["_id"], "date": record["date"]},
            {"$set": record},
            upsert=True
        )
        print(f"✅ Synced: {d['name']} | {day_data['duration']} | {day_data['deliveries']} deliveries")

    print(f"--- 🌙 SYNC COMPLETE ---")

if __name__ == "__main__":
    run_midnight_sync()