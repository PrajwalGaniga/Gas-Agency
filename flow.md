# GasFlow Architecture Master Blueprint

This document maps every technical interaction within the GasFlow ecosystem, tracking how data mutates from the Admin Dashboard, through the Driver's mobile context, and ultimately reconciles back into the MongoDB database.

---

## 0. The Territory Handshake (Driver Registration)
*The logic preventing overlap by assigning a strict geometry of responsibility to each driver.*

### A. The "One City = One Driver" Lock
1. **Admin Action**: Creates or updates a Driver.
2. **Endpoints**: `POST /add-driver` | `POST /update-driver`
3. **Validation**: 
   - Flattens the array of `assigned_cities` into a set.
   - Queries MongoDB for all *active* drivers in the system.
   - Evaluates if the incoming cities intersect with any existing driver's assigned region.
   - **Conflict Action**: Halts execution, protecting the system from "Double Dispatching."
   - **Success Action**: Binds the territory to the driver. The driver's `cities` attribute becomes their canonical dispatch zone.

---

## 1. The Inventory Handshake (Shift Lifecycle)
*The precise steps establishing a working session between the system and a driver.*

### A. Admin Loads Truck
1. **User Action**: Admin physically loads cylinders onto a driver's truck in the morning and initiates a shift via the Inventory UI.
2. **Endpoint**: `POST /admin/shifts/start`
3. **Validation**: 
   - Uses `get_current_admin` to verify auth.
   - **Load Lock**: Queries MongoDB `shifts` to check if an active (`status: "OPEN"`) shift already exists. If yes, the action is blocked to prevent duplicate leakage.
4. **Data Mutation**:
   - A new `Shift` document is created in MongoDB.
   - Initialized with `status: "OPEN"`.
   - `load_departure.full` is set to the provided count.
   - `load_departure.empty` is set to the provided count.
   - `date` receives an exact UTC anchor point based on local `IST` boundaries.

### B. Driver Syncs Context (The App Handshake)
1. **User Action**: Driver logs into the Flutter App.
2. **Endpoint**: `GET /driver/shift/status`
3. **Telemetry Engine**:
   - Fetches the exact `Shift` document where `driver_id == sub` and `status == "OPEN"`.
   - Returns live aggregated telemetry: `current_full = load_departure.full - load_return.full` and `current_empty = load_departure.empty + load_return.empty`.

---

## 2. The Delivery Transaction
*The logic chain securing the physical exchange of gas, empties, and payment.*

### A. GPS Verification (The "Gold Standard")
1. **User Action**: Driver presses "Complete Delivery" at the customer's home.
2. **Endpoint**: `POST /driver/complete-order`
3. **Execution Chain**:
   - The Flutter App captures high-accuracy Lat/Lng from the physical device.
   - The Backend fetches the Customer document and their `verified_lat` / `verified_lng`.
   - Evaluates distance via Haversine formula.
   - **Thresholds**: 
       * `> 150m`: Hard blocks the transaction. A manual Change Request must be filed by the driver and approved by the admin.
       * `50m - 150m`: Soft warning. Delivery allowed but `is_flagged = True`.
       * `< 50m`: Perfect GPS Lock.

### B. State Mutation (Atomic Inventory Decrement)
If GPS checks pass, the database performs atomic batch updates:
1. **Shift Ledger**: Increments `load_return.full` (consumed stock) by 1. Increments `load_return.empty` by user input.
2. **Shift Financials**: Dynamically increments `financials.actual_cash_collected` or `financials.upi_total` based on payment mode.
3. **Order Document**: Marked `status: "DELIVERED"`. **CRITICAL:** Injects `shift_id: str(shift["_id"])` into the order to cryptographically tie the delivery to this exact historical shift, preventing cross-shift leakage.
4. **Customer Document**: Syncs `last_order_date` and resets any pending locks.

---

## 3. The Reconciliation Loop
*How the system validates raw physical numbers against estimated digital states.*

### A. The Live Ledger Feed
1. **Admin Action**: Admin navigates to the Inventory Dashboard to monitor the fleet in real-time.
2. **Endpoint**: `GET /admin/api/inventory/ledger?start_date=...&end_date=...`
3. **Aggregation Logic**:
   - Applies strict UTC boundaries representing 00:00:00 to 23:59:59 IST.
   - Calculates `current_full = initial_full - return_full` mathematically without querying individual orders, saving exponential computational load.
   - Sums cash vs UPI collections exclusively for that active shift.

### B. The Settlement Process (Closing the Loop)
1. **User Action**: Driver returns. Admin inputs the *physical* counts found on the truck and money handed over.
2. **Endpoint**: `POST /admin/shifts/close`
3. **Validation**:
   - Compares Admin's manual entry against the system's `Expected Cash`, `Calculated Full`, and `Calculated Empties`.
   - A `reconciliation_report` object is embedded permanently into the shift document showing ± variations (Shortages / Overages).
   - Marks shift `status: "RECONCILED"`. The shift context is now securely archived, unlocking the driver to begin a new shift tomorrow with a clean slate.

---

## 4. The Offline Sync Engine (Flutter ↔ Hive ↔ FastAPI)
*Resilience architecture for edge-cases where 4G tracking drops.*

### A. Pre-fetch Strategy
1. The Flutter app uses `GET /driver/orders` to fetch JSON.
2. It parses this and writes the orders into a local NoSQL `Hive` box on the phone storage.

### B. The "Dead Zone" Delivery
1. If the driver loses signal, the Flutter App intercepts the `POST /driver/complete-order` request.
2. Instead of crashing, it writes a `PendingSyncTransaction` object into a localized Hive Queue.
3. The UI updates optimistically to show "Delivered" and increments local counters.

### C. Background Hydration
1. A background Isolate or `Connectivity_Plus` listener pings the network.
2. Upon internet restoration, the queue pops the `PendingSyncTransaction`.
3. It replays the JSON payload to `POST /driver/complete-order`.
4. The Backend strictly relies on the timestamp inside the payload rather than `datetime.now()` to ensure accurate temporal placement.
5. If successful, the App deletes the local offline transaction and flashes the "Green Checkmark" Cloud Sync logo.
