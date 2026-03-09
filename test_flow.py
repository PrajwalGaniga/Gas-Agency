import asyncio
import httpx

# GasFlow Verification Script
# Goals: Test Scenario C (Double Order lock), Scenario B (Distance Spoofing), and normal operations.

BASE_URL = "http://127.0.0.1:8000"

async def test_scenario_c_double_order_spam(client: httpx.AsyncClient, token: str, customer_id: str):
    print("\n[TEST] Scenario C: Double Order Spam")
    payload = {
        "customer_id": customer_id,
        "cylinders": 1,
        "payment_mode": "CASH"
    }
    
    # We will simulate the user tapping "Submit" 5 times instantly
    headers = {"Authorization": f"Bearer {token}"}
    
    tasks = []
    for _ in range(5):
        tasks.append(client.post(f"{BASE_URL}/customer/create-order", json=payload, headers=headers))
    
    responses = await asyncio.gather(*tasks)
    
    success_count = sum(1 for r in responses if r.json().get("success") is True)
    failed_count = sum(1 for r in responses if r.json().get("success") is False)
    
    print(f"  Attempted 5 concurrent order creations.")
    print(f"  Successful (Expected 1): {success_count}")
    print(f"  Blocked/Failed (Expected 4): {failed_count}")
    
    for r in responses:
        if not r.json().get("success"):
            lock_msg = r.json().get('message')
            if 'already has an active order' in lock_msg or 'Processing another order' in lock_msg:
                 print(f"    Correctly blocked with message: {lock_msg}")

async def test_scenario_b_distance_spoofing(client: httpx.AsyncClient, driver_token: str, order_id: str):
    print("\n[TEST] Scenario B: Driver Distance Spoofing")
    # Using lat/lng that is definitely > 2km away from the verified location of the customer (Let's assume India vs US coordinates)
    fake_lat, fake_lng = 40.7128, -74.0060 # New York
    
    payload = {
        "order_id": order_id,
        "lat": fake_lat,
        "lng": fake_lng,
        "empties_collected": 1,
        "payment_mode": "UPI"
    }
    headers = {"Authorization": f"Bearer {driver_token}"}
    
    response = await client.post(f"{BASE_URL}/driver/complete-order", json=payload, headers=headers)
    
    # Expected output is 403 Forbidden or success = False
    print(f"  Response Status: {response.status_code}")
    print(f"  Response Body: {response.json()}")

async def run_all():
    print("WARNING: This assumes the backend is active at http://127.0.0.1:8000 and requires real DB tokens.")
    print("As this is a script demonstrating the verification tools built, to run this completely you would need")
    print("to fetch a valid customer JWT from the database and a valid driver JWT.")
    print("The above functions demonstrate the tests implemented.")

if __name__ == "__main__":
    asyncio.run(run_all())
