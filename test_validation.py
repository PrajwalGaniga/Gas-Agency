import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_gps_validation():
    print("--- Testing GPS Validation Bounds ---")
    
    # 1. Valid Ping
    payload_valid = {
        "driver_id": "TEST-DRV",
        "lat": 12.9716,
        "lng": 77.5946
    }
    r = requests.post(f"{BASE_URL}/driver/location-ping", json=payload_valid)
    print(f"Valid Ping (12.97, 77.59): {r.status_code}")
    
    # 2. Invalid Ping (Latitude out of bounds)
    payload_invalid_lat = {
        "driver_id": "TEST-DRV",
        "lat": 95.0,  # Invalid
        "lng": 77.5946
    }
    r = requests.post(f"{BASE_URL}/driver/location-ping", json=payload_invalid_lat)
    print(f"Invalid Lat Ping (95.0, 77.59): {r.status_code} \nResponse: {r.text}")
    
    # 3. Invalid Ping (Longitude out of bounds)
    payload_invalid_lng = {
        "driver_id": "TEST-DRV",
        "lat": 12.9716,
        "lng": 185.0 # Invalid
    }
    r = requests.post(f"{BASE_URL}/driver/location-ping", json=payload_invalid_lng)
    print(f"Invalid Lng Ping (12.97, 185.0): {r.status_code} \nResponse: {r.text}")

def test_offline_sync_simulation():
    print("\n--- Testing Offline Sync Queue Simulation ---")
    # In a real scenario, this is an array of delayed payloads hit against /driver/sync-offline-data
    
    payload = {
        "device_id": "TEST-DEVICE-001",
        "offline_actions": [
            {
                "action_type": "COMPLETE_ORDER",
                "timestamp": "2026-03-09T10:00:00Z",
                "payload": {
                    "order_id": "TEST-OFFLINE-ORD",
                    "lat": 12.9716,
                    "lng": 77.5946,
                    "empties": 1,
                    "payment_mode": "CASH"
                }
            }
        ]
    }
    
    r = requests.post(f"{BASE_URL}/driver/sync-offline", json=payload)
    print(f"Sync Queue endpoint hit: {r.status_code} \nResponse: {r.text}")

if __name__ == "__main__":
    try:
        test_gps_validation()
        test_offline_sync_simulation()
    except Exception as e:
        print(f"Error during test: {e}")
