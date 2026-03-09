# Gas Delivery System (GasFlow) - Full Stack Technical Report

This document completely outlines the architecture, flow, components, and database schemas of the GasFlow Delivery System (Gas Agency System). We'll cover the Backend API (FastAPI), the Admin Web Portal (Jinja2 Templates), and the Driver Mobile Application (Flutter).

---

## 🏗️ 1. Complete System Architecture

### High-Level Flow
1. **Admin Portal**: Admins log in, import/create customers, register drivers, and dispatch gas cylinders by creating and assigning "Orders" (either manually or via Smart Auto Assignment). They can also track driver locations and performance in real-time.
2. **Backend Server**: Built on **FastAPI**. It handles REST APIs, data parsing, database connections using **MongoDB Atlas**, authentication using **JWT Tokens**, password hashing, and coordinates data between the Driver App and Admin web portal.
3. **Driver Mobile App**: Built using **Flutter**. It allows drivers to view their assigned deliveries, accept orders, start navigation to the customer, complete deliveries, and handle offline-mode operations. It sends periodic GPS heartbeats to the server.

---

## ⚙️ 2. The Backend & Admin System (FastAPI + Jinja2)

### Structure & Frameworks
- **Framework:** FastAPI (Python)
- **Database:** MongoDB (using `pymongo` driver)
- **Templating:** Jinja2Templates (for the Admin frontend rendering)
- **Authentication:** JWT (JSON Web Tokens) with OAuth2PasswordBearer, Bcrypt for password hashing.
- **Environment:** Loads environment variables through `dotenv`.
- **Date/Time Handling:** Deep conversions handling Indian Standard Time (IST) vs UTC for consistent global date-time logging.

### Modules Breakdown
- `main.py`: Entry point. Mounts all routers (`admin_router`, `customer_router`, `driver_router`).
- `app/database.py`: Handles SSL-secured connection (with fallback bypass) to MongoDB Atlas. Declares collections.
- `auth.py`: Token generation (`create_access_token`) and verification for both Admins (`get_current_admin` via cookies) and Drivers (`get_current_driver` via headers).
- `admin.py`: 
  - Sub-router handling authentication (Login, Signup, OTP-based exact Forgot Password workflows).
  - Handles Dashboard statistics, Driver analytics (Hours worked, Deliveries completed, GPS heartbeats), and Excel Data Exports.
  - View renders for `dashboard.html`, `drivers.html`, `assignments.html`, etc.
- `customer.py`:
  - Customer registry and management logic (e.g., viewing, adding manually, or bulk Excel imports).
  - Contains **Load Balancing Smart Assignment algorithm** (`get_optimal_driver`) to automatically assign orders to active drivers based on least current load.
- `driver.py`:
  - Contains all the REST API endpoints the **Flutter App** consumes (Login, Accept Order, Location Updates, Delivery Completion).

### Admin Workflow
1. **Authentication:** The admin registers using a Master Key / OTP approval process. Logs in via session cookie.
2. **Customer Management:** Admins can insert customers manually or bulk upload via Excel/CSV templates.
3. **Dispatch & Assignments:** Admins create an order for a customer. The system can autosuggest the best driver based on the city and the lowest number of pending tasks.
4. **Live Tracking:** Utilizing the Driver teleport APIs (`/driver/location`), the admin Dashboard plots a GPS tracker map indicating where drivers are.

---

## 📱 3. The Driver Application (Flutter)

### Frameworks & Plugins
- **Framework:** Flutter / Dart
- **State/Caching:** `hive_flutter` for local offline storage and action queuing.
- **Session:** `shared_preferences` for quick session auto-login checks.
- **Location Engine:** `geolocator` for highly accurate background and foreground location mapping.
- **Networking:** Custom `ApiService` handling HTTP requests.

### Core Screens & Workflows
- `main.dart`: Bootstraps the application, opens Hive local boxes (`cached_orders`, `sync_queue`), and checks session viability.
- `login_screen.dart`: Takes phone number and password -> talks to `/driver/login` API to get JWT Bearer token.
- `home_screen.dart`: The core Dashboard. 
  - **Orders Queue:** Polls for active orders assigned to the driver. Sorts intelligently (In Progress first, then Pending, then Completed based on closest GPS distance).
  - **Status Transitions:** Driver taps "Accept Order" (Changes state to `IN_PROGRESS`). Driver taps "Mark Delivered" (Changes state to `DELIVERED` & records delivery latitude/longitude coordinates).
  - **Offline Sync (The "Action Queue"):** If the driver operates in an area without cell service, the `ApiService` caches the action (e.g., Deliveries made) inside Hive's `sync_queue`. The Dashboard `Refresh` engine runs `processSyncQueue()` to upload these pending actions whenever the network returns.
  - **Heartbeat Engine:** A 5-minute background/foreground timer periodically pulses the driver’s location to the server using the `Geolocator` plugin.
- `map_screen.dart`: Secondary map layout visualizer for deliveries.

---

## 🗄️ 4. Database Schemas (MongoDB)

Because MongoDB is NoSQL, the schemas are implicit. Here are the core structures representing the business logic:

### 1. `admins`
```json
{
  "_id": ObjectId,
  "username": "Admin Name",
  "email": "admin@example.com",
  "password_hash": "$2b$12$...",
  "role": "super_admin",
  "phone": "999999999",
  "agency_name": "GasFlow Central",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### 2. `drivers`
```json
{
  "_id": ObjectId,
  "admin_id": ObjectId("..."),
  "name": "Driver Name",
  "phone_number": "1234567890",
  "password_hash": "$2b$12$...",
  "assigned_cities": ["City A", "City B"],
  "is_active": true,
  "current_lat": 12.345,
  "current_lng": 76.890,
  "current_address": "Street Name, City",
  "last_seen": ISODate,
  "created_at": ISODate
}
```

### 3. `customers`
```json
{
  "_id": ObjectId,
  "admin_id": ObjectId("..."),
  "name": "Customer Name",
  "phone_number": "0987654321",
  "city": "City A",
  "landmark": "Near The Big Mall",
  "pincode": "500001",
  "verified_lat": 12.333,      // Captured when driver first completes an order
  "verified_lng": 76.888,      // Captured when driver first completes an order
  "records": [                 // Historical array of order instances
     {
        "order_id": ObjectId("..."),
        "date": ISODate,
        "status": "DELIVERED",
        "driver_name": "Driver Name"
     }
  ],
  "created_at": ISODate
}
```

### 4. `orders`
```json
{
  "_id": ObjectId,
  "admin_id": ObjectId("..."),
  "customer_id": ObjectId("..."),
  "customer_name": "Customer Name",
  "city": "City A",
  "status": "PENDING",             // PENDING -> IN_PROGRESS -> DELIVERED
  "assigned_driver_id": ObjectId("..."),
  "assigned_driver_name": "Driver Name",
  "started_at": ISODate,           // Timestamps transition to IN_PROGRESS
  "delivered_at": ISODate,         // Timestamps transition to DELIVERED
  "verified_lat": 12.333,          // GPS at exact moment of delivery
  "verified_lng": 76.888,
  "created_at": ISODate
}
```

### 5. `driver_audit_logs`, `driver_locations`, `customer_change_requests`
These handle supplementary analytics tracking telemetry, historical GPS pathing, and form submissions from drivers correcting addresses/phone numbers.

---

## 🌟 5. Best Practices & System Design Highlights

1. **Smart Load Balancing**: The `get_optimal_driver` method guarantees that auto-assignments never overload a single driver, ensuring rapid dispatching dynamically based on current queue metrics.
2. **Offline Resilience (Local First Approach)**: The Flutter app utilizes Hive caching to seamlessly operate during blackouts. Important delivery triggers queue locally and sync instantly upon signal restoration without data loss.
3. **Data Integrity via Telemetry**: `calculate_work_time()` intelligently groups GPS pings and limits gaps. It guarantees precise calculations of driver working hours directly validated by live location history—preventing dashboard tampering.
4. **Proactive Fraud Prevention**:
    - Orders can only be completed when the GPS confirms the proximity.
    - Double Order protections prevent generating multiple PENDING deliveries for one customer.
5. **Reverse Geocoding Layer**: The backend automatically turns driver raw lat/lng pings into readable street addresses for the Admin tracking portal using Python `Geopy`.
6. **Date Standardizations**: Deep abstractions cleanly map user inputs across Timezones using uniform constraints (`ist_day_start`, `ist_day_end`). Every timestamp is consistently stored in UTC but displayed in IST.
