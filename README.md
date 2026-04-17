# GasFlow — Gas Agency Delivery Management System

A full-stack field operations platform for LPG/gas cylinder agencies. It provides a **web-based admin dashboard** for managing customers, drivers, orders, and shift-level inventory, paired with a **Flutter mobile app** for on-ground delivery drivers.

---

## 1. Project Overview

**What it does:**
- Allows agency admins to register customers, create gas delivery orders, assign orders to drivers, and track real-time driver location and inventory.
- Provides drivers with a mobile app to view their order queue, mark deliveries complete (with GPS verification), collect payments, and submit change requests.
- Enforces territory locking (one city per driver), GPS-based delivery proof, shift-based inventory accounting, and offline-first delivery completion with background sync.

**Problem it solves:**
A gas delivery agency manually tracks cylinder dispatch, driver locations, cash collection, and cylinder empties with no digital audit trail. GasFlow digitizes the entire dispatch-to-reconciliation cycle.

---

## 2. Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Language | Python 3.x |
| Framework | FastAPI |
| Database | MongoDB Atlas (`pymongo[srv]`) |
| Templating | Jinja2 |
| Auth | JWT (`python-jose`), Cookie-based (Admin), Bearer Token (Driver) |
| Password Hashing | `passlib[bcrypt]`, `bcrypt==4.0.1` |
| Email (OTP) | Resend API (`resend` library) |
| Geolocation | `geopy` (Nominatim reverse geocoder) |
| Data processing | `pandas`, `openpyxl`, `xlsxwriter` |
| Sessions | `itsdangerous`, `starlette` |
| TLS/SSL | `certifi` |
| Env Config | `python-dotenv` |
| Server | `uvicorn` |
| Tunneling tool | `ngrok.exe` (binary present in repo root) |

### Frontend (Admin Web)
| Layer | Technology |
|---|---|
| Rendering | Jinja2 server-side HTML templates |
| Styling | Inline CSS within HTML templates |
| Maps | Leaflet.js (referenced in templates) |

### Mobile (Driver App)
| Layer | Technology |
|---|---|
| Language | Dart |
| Framework | Flutter (Material 3, dark mode) |
| HTTP | `http: ^1.1.0` |
| Local storage (session) | `shared_preferences: ^2.2.2` |
| Offline DB (cache + sync queue) | `hive: ^2.2.3`, `hive_flutter: ^1.1.0` |
| GPS | `geolocator: ^10.1.0` |
| Maps | `google_maps_flutter: ^2.5.0` |
| External navigation | `url_launcher: ^6.2.1` |
| Code generation | `hive_generator`, `build_runner` |
| Icon generation | `flutter_launcher_icons: ^0.13.1` |

---

## 3. Project Structure

```
GasAgencySystem/
│
├── main.py                  # FastAPI app entry point; registers 3 routers
├── admin.py                 # All admin routes (1517 lines) — auth, dashboard, drivers, orders, inventory, shifts
├── customer.py              # Customer and order management routes
├── driver.py                # Driver-facing mobile API routes
├── auth.py                  # JWT token creation & validation; admin (cookie) + driver (bearer) dependencies
│
├── app/
│   ├── database.py          # MongoDB Atlas connection; defines all 9 collection handles
│   ├── schemas.py           # Pydantic request/response models
│   └── utils.py             # Password hashing, OTP generation, Resend email, IST time helpers
│
├── templates/               # Jinja2 HTML templates (17 files)
│   ├── base.html            # Shared base layout
│   ├── login.html           # Admin login page
│   ├── signup.html          # Admin signup page (requires developer passcode)
│   ├── dashboard.html       # Main live fleet tracking dashboard
│   ├── customers.html       # Customer management (CRUD, search, filter, bulk order)
│   ├── drivers.html         # Driver management (CRUD, territory assignment)
│   ├── assignments.html     # Pending order assignment view
│   ├── pending_orders.html  # Territory-grouped pending order command center
│   ├── inventory_management.html  # Shift-based inventory tracker
│   ├── DriverTracking.html  # Per-driver GPS path replay map
│   ├── DriverAudit.html     # Driver work hours, deliveries, change requests audit
│   ├── reports.html         # Order summary reports (24h/1w/1m); reused for reconciliation
│   ├── statistics.html      # Statistics page (template exists, route not found in admin.py)
│   ├── profile.html         # Admin profile + metrics
│   ├── forgot_password.html # Password reset flow
│   ├── reset_password.html  # Password reset form (minimal, 675 bytes)
│   └── verify_otp.html      # OTP verification stub (687 bytes)
│
├── gas_driver_app/          # Flutter mobile app (driver-facing)
│   ├── lib/
│   │   ├── main.dart        # App entry point; Hive init, auto-login check, theme setup
│   │   ├── screens/
│   │   │   ├── home_screen.dart       # Main driver dashboard (850 lines) — order list, inventory, map
│   │   │   ├── login_screen.dart      # Driver phone+password login
│   │   │   ├── map_screen.dart        # Google Maps order visualization
│   │   │   └── sync_status_screen.dart # Displays offline sync queue status
│   │   └── services/
│   │       └── api_service.dart       # All backend HTTP calls + Hive offline caching logic
│   └── pubspec.yaml         # Flutter dependencies
│
├── .env                     # Environment secrets (MONGO_URI, SECRET_KEY, API keys)
├── requirements.txt         # Python dependencies (corrupted: contains raw chat text after line 14)
├── flow.md                  # Internal architecture blueprint (not a user-facing doc)
│
├── inject.py                # One-off script to seed test data into MongoDB
├── cleanup_db.py            # Script to clean MongoDB collections
├── delete.py                # Script to delete records from MongoDB
├── init.py                  # Initialization script (869 bytes)
├── sync_daily_stats.py      # Daily stats sync utility
├── patch_html.py            # Script to patch HTML templates
│
├── test.py                  # Basic test
├── test_flow.py             # Test for delivery flow
├── test_shift_leakage.py    # Test for cross-shift inventory leakage
├── test_system_sync.py      # Test for data sync correctness
├── test_territory_lock.py   # Test for territory conflict enforcement
├── test_validation.py       # Validation tests
├── full_system_audit.py     # Connects to MongoDB and runs shift lock + IST boundary scenario tests
│
├── GasDriverApp/            # Legacy/unused React Native directory (referenced only in .gitignore)
├── ngrok.exe                # Ngrok binary for tunneling localhost (31MB; committed to repo)
└── venv/                    # Python virtual environment (not committed)
```

**MongoDB Collections (as defined in `app/database.py`):**

| Collection | Purpose |
|---|---|
| `admins` | Admin user accounts |
| `drivers` | Driver profiles, assigned cities, GPS coords |
| `customers` | Customer records with order history embedded |
| `orders` | All delivery orders with status lifecycle |
| `shifts` | Shift sessions — truck load, returns, financials |
| `driver_locations` | Historical GPS heartbeat log |
| `driver_audit_logs` | Login events per driver |
| `customer_change_requests` | Driver-submitted data correction requests |
| `daily_stats` | Daily aggregated statistics |
| `counters` | Auto-increment sequence for `customer_id` |
| `cities` | Registered service cities |
| `temp_signups` | Temporary pending admin registrations |
| `temp_resets` | Temporary OTP records for password reset |
| `driver_issues` | Driver-reported field issues |

---

## 4. Features (Implemented Only)

### Admin Web Dashboard

| Feature | Description | Code Location |
|---|---|---|
| Admin Signup | Requires developer passcode → sends OTP to master email → OTP verified to activate account | `admin.py:234–176` |
| Admin Login | Email + bcrypt password → JWT set as HTTP-only cookie | `admin.py:182–190` |
| Forgot / Reset Password | OTP sent via Resend API; OTP compared against `temp_resets` | `admin.py:204–230` |
| Live Fleet Dashboard | Shows all drivers: GPS status (green/yellow/red), shift stock, pending & completed deliveries | `admin.py:372–448` |
| Driver Management | CRUD for drivers; territory (city) assignment with conflict lock | `admin.py:462–508` |
| Territory Lock | Prevents two active drivers from owning the same city | `admin.py:466–473, 486–496` |
| Customer Management | CRUD for customers; search by name/phone/city; filter by order status | `customer.py:88–195` |
| Customer Bulk Import | Upload Excel/CSV; validates required columns, skips duplicates, upserts cities | `admin.py:1167–1265` |
| Excel Template Download | Serves a pre-formatted XLSX import template | `admin.py:1141–1165` |
| Single Order Creation | Admin creates order for customer; auto-assign driver or pick specific driver | `customer.py:270–340` |
| Bulk Order Creation | Creates orders for multiple selected customers simultaneously | `customer.py:344–401` |
| Driver Reassignment | Reassign pending order to a different driver | `customer.py:402–434` |
| Auto-assign (Load Balancing) | `get_optimal_driver()`: picks active driver in correct city with open shift and lowest active order count | `customer.py:30–79` |
| Atomic Double-Order Prevention | Uses `find_one_and_update` with `active_order_lock` to atomically prevent concurrent duplicate orders | `customer.py:283–295` |
| Pending Orders Command Center | Territory-grouped view of all pending orders with date filter and batch rescheduling | `admin.py:563–726` |
| Batch Reschedule | Move multiple orders to a different driver and/or date in one operation | `admin.py:728–797` |
| Driver GPS Tracking | Per-driver map with GPS path, delivery markers, and live position | `admin.py:801–879` |
| Driver Audit | Per-driver work hours (from GPS heartbeats), login history, deliveries count; exportable to Excel | `admin.py:881–951` |
| Change Request Resolution | Admin approves or rejects driver-submitted data corrections; applies writes on approval | `admin.py:953–1013` |
| Reports | Order summary for 24h/1w/1m; exportable to Excel | `admin.py:1017–1043` |
| Shift Management (Start) | Admin starts a driver's shift, sets initial cylinder load; prevents duplicate open shifts | `admin.py:1357–1377` |
| Shift Management (Close) | Admin reconciles shift end: inputs physical counts, system calculates shortages/overages | `admin.py:1379–1418` |
| Inventory Ledger API | Filterable JSON API serving all shift data by date range and driver name | `admin.py:1420–1517` |
| Inventory Dashboard | Per-driver shift stock view (initial load, current full, current empty, financials) | `admin.py:1269–1355` |
| Admin Profile | Displays agency metrics (total orders, success rate, driver efficiency); editable profile fields | `admin.py:1091–1137` |
| Fleet Status API | Single JSON endpoint aggregating all driver's real-time data (GPS, inventory, orders) | `admin.py:271–368` |

### Driver Mobile App (Flutter)

| Feature | Description | Code Location |
|---|---|---|
| Auto-login | Reads saved token from SharedPreferences on app launch | `main.dart:31; api_service.dart:52–60` |
| Dynamic API URL routing | Tries emulator → ngrok → Render cloud on startup | `api_service.dart:15–38` |
| Driver Login | Phone + password POST to `/driver/login` | `login_screen.dart; api_service.dart:70–90` |
| Order Checklist | Fetches orders for current date filterable by assigned city; sorted by status priority then distance | `home_screen.dart; driver.py:84–159` |
| Date Picker | Driver can view orders for any past date | `home_screen.dart:652–657` |
| City Focus Filter | Driver filters order list by a specific assigned city | `home_screen.dart:525–556` |
| Accept Order | Moves order PENDING → IN_PROGRESS | `home_screen.dart; driver.py:74–82` |
| Mark Delivered (GPS-locked) | Captures GPS, calculates Haversine distance, blocks delivery if >150m, flags if 50–150m | `driver.py:370–478; api_service.dart:122–174` |
| Delivery Confirmation Dialog | Driver inputs empties collected, payment mode (CASH/UPI), amount collected | `home_screen.dart:765–850` |
| Offline Delivery Queue | If no network on completion, saves action to Hive `sync_queue`; replays on reconnect | `api_service.dart:141–173; 177–202` |
| Offline Order Cache | Caches last fetched orders in Hive; loads from cache on network failure | `api_service.dart:93–119` |
| Background Sync | Processes Hive sync queue at start of each dashboard refresh | `home_screen.dart:75; api_service.dart:177–202` |
| GPS Heartbeat | Sends location ping to `/driver/location` every 5 minutes | `home_screen.dart:50–58` |
| Shift Status Widget | Shows live truck inventory (loaded, available, empties, collected cash) from `/driver/shift/status` | `home_screen.dart:236–302; driver.py:480–511` |
| Change Request Submission | Driver reports wrong GPS location or wrong phone number; triggers admin approval flow | `home_screen.dart:659–763; driver.py:301–338` |
| Map View | Google Maps screen plotting all order locations | `map_screen.dart` |
| Sync Status Screen | Shows count of pending offline items in Hive queue | `sync_status_screen.dart` |
| In-app Navigation | Opens device navigation app to customer coordinates | `home_screen.dart:601–615` |
| Overdue Badge | Orders pending for 4+ hours display a "DELAYED" badge | `home_screen.dart:360–371` |

---

## 5. Application Workflow

### A. Admin Onboarding
1. Admin visits `/signup` → submits email, password, and developer passcode (`GAS`).
2. Backend validates passcode, stores hashed password in `temp_signups`, sends OTP to `MASTER_EMAIL` via Resend API.
3. Admin receives OTP → submits at `/complete-signup`.
4. Backend validates OTP, promotes user to `admins` collection, deletes temp record.

### B. Daily Dispatch Setup (Shift Start)
1. Admin physically loads cylinders on truck.
2. Admin opens Inventory Dashboard → starts a shift for a driver, entering full/empty cylinder counts.
3. Backend (`POST /shifts/start`) checks no existing `OPEN` shift exists for that driver, then creates a shift document with `load_departure.full` and `status: OPEN`.

### C. Order Creation & Assignment
1. Admin goes to Customers page → creates order for a customer.
2. If `driver_id == "auto"`: `get_optimal_driver()` runs — finds drivers in customer's city with an open shift with stock > 0 and fewest active orders.
3. Order document is inserted with status `PENDING`; customer's `records` array is updated.
4. `active_order_lock` is atomically set on customer to prevent duplicate orders.

### D. Driver Delivery Flow (Mobile App)
1. Driver opens Flutter app → auto-login from SharedPreferences or manual login.
2. App fetches orders for today via `GET /driver/orders` (uses GPS + city filter).
3. Driver taps "Accept Order" → `POST /driver/accept-order` → status moves to `IN_PROGRESS`.
4. Driver goes to customer → taps "Mark Delivered".
5. App captures GPS coordinates and calls `POST /driver/complete-order`.
6. Backend checks:
   - Is shift OPEN?
   - Is `current_full > 0`?
   - Is driver within 150m of verified customer coordinates?
7. If all pass: shift inventory decremented, order marked `DELIVERED`, customer `active_order_lock` cleared.
8. If driver is offline: action is serialized into Hive `sync_queue` and replayed on reconnect.

### E. End-of-Day Reconciliation
1. Driver returns. Admin opens Inventory Dashboard.
2. Admin closes the shift: inputs physical cash, full cylinders, empty cylinders returned.
3. Backend calculates shortages/overages, embeds a `reconciliation_report` into the shift, marks status `RECONCILED`.

### F. Driver Audit & Change Requests
1. Admin opens Driver Audit page for period (24h/1w/1m or specific date).
2. System aggregates work hours from `driver_locations` GPS heartbeats (consecutive pings < 1 hour apart are counted as continuous work).
3. Pending change requests (submitted by driver from the app) are displayed for admin approval.
4. On approval: customer coordinates / phone number / address is updated in the database.

---

## 6. API Routes / Endpoints

### Admin Routes (`admin_router`, served at root `/`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Render login page |
| POST | `/login` | Authenticate admin; set JWT cookie |
| GET | `/logout` | Clear JWT cookie |
| GET | `/signup` | Render signup page |
| POST | `/signup-request` | Validate developer passcode; send OTP to master email |
| POST | `/complete-signup` | Verify OTP; create admin account |
| GET | `/forgot-password` | Render forgot password page |
| POST | `/forgot-password-request` | Generate OTP; send to user email via Resend |
| POST | `/reset-password-finalize` | Verify OTP; update password hash |
| GET | `/dashboard` | Render live fleet dashboard with driver stats |
| GET | `/admin/fleet/status` | JSON: real-time fleet data (GPS, inventory, orders) |
| GET | `/drivers` | Render driver management page |
| POST | `/add-driver` | Create driver; enforce territory lock |
| POST | `/update-driver` | Update driver; enforce territory lock |
| POST | `/delete-driver` | Delete driver by ID |
| GET | `/assignments` | Render pending order assignment page |
| POST | `/assign-delivery` | Assign/reassign order to driver |
| GET | `/admin/pending-orders` | Render territory-grouped pending orders (date-filtered) |
| POST | `/api/reassign-order` | Reassign single order to driver + optional reschedule |
| POST | `/admin/orders/batch-reschedule` | Batch reschedule multiple orders |
| GET | `/track/{driver_id}` | Render GPS tracking page for a driver |
| GET | `/api/track-data/{driver_id}` | JSON: GPS path, delivery markers, current position |
| GET | `/driver-audit` | Render driver work-hours audit with change requests |
| GET | `/export-driver-audit` | Download driver audit as Excel file |
| POST | `/api/resolve-request` | Approve or reject a driver change request |
| GET | `/reports` | Render order summary report (24h/1w/1m) |
| GET | `/export-report` | Download order report as Excel file |
| GET | `/reconciliation` | Render reconciliation page (daily cash vs expected) |
| GET | `/profile` | Render admin profile with agency metrics |
| POST | `/update-profile` | Update admin profile fields |
| GET | `/download-template` | Download Excel customer import template |
| POST | `/upload-customers` | Bulk import customers from Excel/CSV |
| GET | `/inventory` | Render inventory/shift management dashboard |
| POST | `/shifts/start` | Start a driver shift (set initial load) |
| POST | `/shifts/close` | Close + reconcile a shift |
| GET | `/admin/api/inventory/ledger` | JSON: filterable historical shift ledger |

### Customer Routes (`customer_router`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/customers` | Render customer management page (search, filter) |
| POST | `/add-city` | Add a city to the cities collection |
| POST | `/add-customer` | Create a single customer |
| GET | `/validate-consumer-id` | Check if consumer ID is already taken |
| POST | `/create-order` | Create delivery order for a customer |
| POST | `/customers/bulk-order` | Create orders for multiple customers |
| POST | `/customers/reassign-driver` | Reassign order to different driver |
| POST | `/update-customer` | Update customer fields |

### Driver Routes (`driver_router`)

| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | `/driver/login` | Phone + password; returns JWT | None |
| GET | `/driver/orders` | Fetch order checklist for driver (date + GPS filtered) | Bearer JWT |
| POST | `/driver/accept-order` | Move order PENDING → IN_PROGRESS | Bearer JWT |
| POST | `/driver/complete-order` | Complete delivery with GPS, payment, empties | Bearer JWT |
| POST | `/driver/location` | Update driver GPS + reverse geocode address | Bearer JWT |
| POST | `/driver/location-ping` | Simple background location ping (no full auth) | None |
| POST | `/driver/change-request` | Submit data correction request | Bearer JWT |
| POST | `/report-issue` | Report a field issue (Customer Not Home, Leak, etc.) | Bearer JWT |
| POST | `/driver/sync-offline` | Receive batched offline actions from Flutter Hive queue | None |
| GET | `/driver/shift/status` | Get real-time shift inventory and financial data | Bearer JWT |

---

## 7. Setup & Installation

### Prerequisites
- Python 3.10+
- Flutter SDK (≥3.10.7)
- MongoDB Atlas account

### Backend Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Mac/Linux

# 2. Install dependencies (only the first 14 lines of requirements.txt are valid)
pip install fastapi uvicorn jinja2 python-multipart "pymongo[srv]" certifi pandas openpyxl xlsxwriter python-dotenv "passlib[bcrypt]" "bcrypt==4.0.1" starlette itsdangerous
pip install python-jose[cryptography] resend geopy
```

### Environment Variables (`.env`)

```env
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?appName=<AppName>
SECRET_KEY=your_random_secret_key_for_sessions
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_password
DEVELOPER_PASSCODE=GAS
```

> **⚠️ CRITICAL:** The actual `.env` file in the repository contains **live credentials** including the MongoDB connection string, Gmail app password, and Resend API key hardcoded in `app/utils.py`. **Rotate all secrets before any production or public use.**

### Flutter App Setup

```bash
cd gas_driver_app
flutter pub get
```

Configure the backend URL in `lib/services/api_service.dart` if deploying to production:
```dart
static const String _renderUrl = "https://your-backend.onrender.com";
```

---

## 8. Running the Project

### Backend

```bash
# Activate virtual environment first
uvicorn main:app --reload --port 8000
```

### Optional: Expose locally via ngrok (for mobile app testing)

```bash
# ngrok.exe is present in root (must match flutter _ngrokUrl)
./ngrok http 8000
```

### Flutter App

```bash
cd gas_driver_app
flutter run
```

The app auto-detects the backend URL: tries emulator localhost → ngrok URL → Render cloud URL on each startup.

---

## 9. Current Progress / Implementation Status

### Fully Implemented
- Admin authentication (signup with OTP, login, logout, password reset)
- Driver CRUD with territory conflict enforcement
- Customer CRUD with bulk Excel import
- Order creation (single and bulk) with atomic double-order prevention
- Auto-assign with load balancing (`get_optimal_driver`)
- Shift lifecycle (start → open → deliveries → reconciliation)
- GPS-based delivery verification (Haversine formula, 50m/150m thresholds)
- Driver change request workflow (submission → admin approval → DB write)
- Driver GPS heartbeat tracking with reverse geocoding
- Driver work hours calculation from GPS data
- Driver audit Excel export
- Order Excel report export
- Offline-first delivery completion in Flutter (Hive queue + background sync)
- Offline order cache in Flutter
- Shift status display in driver app (live inventory widget)
- Flutter auto-login from cached session
- Dynamic backend URL detection in Flutter app

### Partially Implemented
- **`/driver/sync-offline`** route: Receives batched actions but only logs them (`print`) — does not actually process/replay them against the database (`driver.py:276–299`).
- **`/driver/location-ping`**: Uses a hardcoded `"mock_driver_id"` instead of authenticated driver ID (`driver.py:264`).
- **Reconciliation page**: The `/reconciliation` route renders `reports.html` (not a dedicated template); the cylinder price is hardcoded as `CYLINDER_PRICE = 900` (`admin.py:1067`).
- **Statistics template** (`templates/statistics.html`): The file exists but no corresponding route is found in `admin.py`.
- **`reset_password.html` / `verify_otp.html`**: Templates exist (675/687 bytes) but appear to be minimal stubs.
- **Offline sync in Flutter**: `completeOrder` queues actions but does not update the cash amount in the cached shift status (`api_service.dart:160–162` — explicit comment: "We don't know the price here easily...").

### Missing / Not Implemented
- OTP expiry is not enforced — `temp_resets` and `temp_signups` have a `created_at` field but no TTL index or code-level expiry check.
- The `full_system_audit.py` script has a syntax error (`import timedelta` and `datetime.timedelta` used without correct import) — it will fail at runtime.
- No rate limiting on login or OTP endpoints.
- No input sanitization for regex patterns in MongoDB queries (e.g., `city_name` is interpolated directly into a regex: `f"^{city_name}$"` — a regex injection vulnerability).
- The `GasDriverApp/` directory (likely a legacy React Native project) is referenced in `.gitignore` but no code exists in the repository beyond the ignore entry.

---

## 10. Architectural Gaps

- **IST helper duplication**: `to_ist`, `to_utc`, `ist_now`, `ist_day_start`, `ist_day_end` are defined identically in both `admin.py` and `app/utils.py`. Neither file uses the other's version — pure duplication.
- **No service layer**: All business logic (order creation, inventory calculation, driver selection) lives directly inside route handler functions. There is no separation between HTTP handling and domain logic.
- **No ORM / schema enforcement**: MongoDB documents are raw dicts. Field presence is inconsistent (e.g., `assigned_driver_id` might be `None`, an `ObjectId`, or a string depending on path).
- **Circular import risk**: `admin.py` imports from `customer.py` inside a function body at line 551 (`from customer import get_optimal_driver`) to avoid a top-level circular import — but the underlying coupling remains.
- **No pagination**: Customer list, order list, driver list — all fetched as full collections. This will degrade with scale.
- **`admin.py` monolith**: 1,517 lines in a single file with auth, dashboard, CRUD, tracking, reporting, inventory, and shift management all mixed together.
- **Inconsistent `admin_id` typing**: `admin_id` is stored as `ObjectId` in `admins` collection references but as `str(admin_id)` in `shifts` collection. Queries between them must manually convert.

---

## 11. Workflow Issues

- **`/driver/sync-offline` is a stub**: The endpoint receives batched offline actions from Flutter but only prints them — deliveries completed offline and submitted in a batch will silently disappear if the Hive sync queue sends to this endpoint instead of `/driver/complete-order` (`driver.py:286–290`). The Flutter code actually does replay to `/driver/complete-order` correctly via `processSyncQueue`, making this backend endpoint dead code.
- **Double-route registration**: `POST /driver/accept-order` is registered twice in `driver.py` — once at line 74 (body accepts a raw dict) and again at line 163 (body accepts `AcceptOrderRequest` schema). FastAPI will use the last registration, silently overriding the first.
- **Batch reschedule sets status to `IN_PROGRESS`**: `POST /admin/orders/batch-reschedule` and `POST /api/reassign-order` set `status: "IN_PROGRESS"` directly when reassigning. This bypasses the normal driver acceptance step — orders skip `PENDING` state entirely on reassignment.
- **`reconciliation_report` vs `reports.html`**: The `/reconciliation` route renders `reports.html` but passes a `reconciliation` variable. If `reports.html` is not updated to handle this key, the reconciliation data is silently unused.
- **`export_report` has no return**: `admin.py:1042–1043` — the function creates the Excel file but the `return StreamingResponse(...)` statement is missing. The function returns `None`, so the export endpoint silently fails.

---

## 12. Security Issues

### Critical
| Issue | Location |
|---|---|
| **Live MongoDB URI committed to `.env`** — includes username and password for Atlas cluster | `.env:1` |
| **Resend API key hardcoded** in source code: `resend.api_key = "re_RtZAfyor_..."` | `app/utils.py:8` |
| **Gmail app password committed** to `.env` | `.env:4` |
| **Admin hashed password + OTP** leaked in comments inside `requirements.txt` | `requirements.txt:33,41` |
| **JWT `SECRET_KEY` in `auth.py`** is a hardcoded literal: `"your_secret_key_here"` — not loaded from env | `auth.py:9` |
| **Regex injection**: `city_name` used directly in MongoDB regex without escaping | `customer.py:231–234`, `admin.py:1226` |

### High
| Issue | Location |
|---|---|
| JWT `ACCESS_TOKEN_EXPIRE_MINUTES = 60` for admin but driver tokens expire in **7 days** — overly long | `auth.py:11`, `driver.py:35` |
| OTP has no expiry enforcement — OTPs in `temp_resets`/`temp_signups` never expire | `admin.py:212–218` |
| `/driver/location-ping` accepts location writes with **no authentication** | `driver.py:253–273` |
| `/driver/sync-offline` accepts batched actions with **no authentication** | `driver.py:276–299` |
| Admin `get_current_admin` returns `None` on invalid token instead of raising — routes handle `None` inconsistently | `auth.py:22–37` |
| No CSRF protection on form-based POST routes | All `admin_router` POST routes |
| SSL bypass fallback is implemented for "college WiFi" — production deployments would auto-downgrade TLS | `app/database.py:27` |
| `ngrok.exe` binary (31MB) committed to repository | repo root |

---

## 13. CI/CD & DevOps Analysis

**No CI/CD pipeline found.**

- No GitHub Actions workflows, no `.github/` directory.
- No `Dockerfile` or `docker-compose.yml`.
- No deployment scripts or `Procfile`.
- The backend is manually deployed to **Render** (URL: `https://gas-agency-backend-go6b.onrender.com` — hardcoded in `api_service.dart`).
- Local-to-mobile tunneling relies on `ngrok.exe` committed to the repository.
- No environment separation (dev/staging/prod) — a single `.env` manages everything.

---

## 14. Code Quality Issues

### Duplication
- `to_ist`, `to_utc`, `ist_now`, `ist_day_start`, `ist_day_end` implemented identically in `admin.py` (lines 31–57) and `app/utils.py` (lines 54–76).
- `templates = Jinja2Templates(directory="templates")` and `templates.env.add_extension('jinja2.ext.do')` duplicated in both `admin.py` and `customer.py`.
- `import os` appears twice in `app/database.py` (lines 4 and 5).

### Dead Code
- `/driver/sync-offline` endpoint (`driver.py:276–299`) — not called by the Flutter sync engine; `processSyncQueue` in `api_service.dart` calls `/driver/complete-order` directly.
- First `POST /driver/accept-order` registration at `driver.py:74–82` is silently overridden by the second registration at line 163.
- `EMAIL_USER` / `EMAIL_PASS` in `.env` — code uses Resend API, not SMTP; these env vars are never read in the codebase.

### Poor Quality
- `requirements.txt` is corrupted — lines 17–43 contain raw project discussion chat text, not Python packages. Packages `python-jose`, `resend`, and `geopy` (all used in code) are **absent** from `requirements.txt`.
- `full_system_audit.py` contains broken imports — `import timedelta` (not a module) and `datetime.timedelta` usage that will raise `NameError` at runtime.
- Repeated comment blocks `# customer.py` appear 6+ times within `customer.py` itself and 3+ times within `driver.py` — leftover copy-paste artifacts.
- `DEVELOPER_PASSCODE = "GAS"` and `MASTER_EMAIL = "prajwalganiga06@gmail.com"` are hardcoded constants in `admin.py` (lines 25–26) and also readable from `.env` — two sources of truth.
- Cylinder price hardcoded as `CYLINDER_PRICE = 900` in reconciliation logic with a TODO comment (`admin.py:1067`).
- `GasDriverApp/` folder is referenced in `.gitignore` but does not exist in the repository — leftover from an abandoned technology switch.
