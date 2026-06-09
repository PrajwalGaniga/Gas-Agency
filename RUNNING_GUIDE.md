# 🚀 GasFlow — Running Guide

This document explains how to set up and run both the **Backend (FastAPI)** and the **Mobile App (Flutter)** for the GasFlow Gas Delivery System.

---

## 📁 Project Structure

```
Gas-Agency/
├── admin.py              # Admin-side API routes
├── driver.py             # Driver-side API routes
├── customer.py           # Customer/order logic
├── main.py               # FastAPI entry point
├── auth.py               # Authentication helpers
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (MongoDB URI, secret keys)
├── venv/                 # Python virtual environment (created by you)
├── templates/            # HTML templates for Admin UI (Jinja2)
├── app/
│   └── schemas.py        # Pydantic request/response models
└── gas_driver_app/       # Flutter mobile app (Driver side)
    ├── lib/
    │   ├── main.dart
    │   ├── screens/
    │   └── services/
    └── pubspec.yaml
```

---

## ⚙️ Part 1 — Backend Setup (FastAPI + Python)

### Step 1: Create the Virtual Environment

Open a terminal inside `Gas-Agency/` and run:

```powershell
# Windows (PowerShell)
python -m venv venv
```

### Step 2: Activate the Virtual Environment

```powershell
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# If you get an execution policy error, run this first:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

You should see `(venv)` appear at the start of your terminal prompt.

### Step 3: Install All Dependencies

```powershell
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, MongoDB driver, Pandas, and all other dependencies.

### Step 4: Set Up Environment Variables

Create a `.env` file in the root `Gas-Agency/` folder:

```env
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<dbname>?retryWrites=true&w=majority
SECRET_KEY=your-super-secret-key-here
ALGORITHM=HS256
```

> ⚠️ Never commit `.env` to Git. It is already in `.gitignore`.

### Step 5: Run the Backend Server

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**The backend will be live at:**
- Admin Dashboard → http://localhost:8000
- API Docs (Swagger) → http://localhost:8000/docs
- API Redoc → http://localhost:8000/redoc

> Use `--host 0.0.0.0` so your phone on the same Wi-Fi can also access it.

---

## 📱 Part 2 — Mobile App Setup (Flutter)

### Prerequisites

Make sure Flutter is installed. Check with:

```powershell
flutter --version
```

If not installed, download from: https://docs.flutter.dev/get-started/install/windows

### Step 1: Navigate to the Flutter Project

```powershell
cd gas_driver_app
```

### Step 2: Install Flutter Dependencies

```powershell
flutter pub get
```

### Step 3: Run the App

#### On a connected Android phone or emulator:

```powershell
flutter run
```

#### To build a release APK:

```powershell
flutter build apk --release
# APK will be at: build/outputs/flutter-apk/app-release.apk
```

#### To run on a specific device:

```powershell
flutter devices           # List connected devices
flutter run -d <deviceId> # Run on that device
```

---

## 🔌 Connecting App to Backend

The app auto-detects which server to use in this priority order:

| Priority | Server | URL |
|----------|--------|-----|
| 1st | Local Emulator | `http://10.0.2.2:8000` |
| 2nd | Ngrok Bridge | Set in `api_service.dart` |
| 3rd | Cloud (Render) | `https://gas-agency-backend-go6b.onrender.com` |

**For local development (phone on same WiFi as laptop):**

1. Start backend with `--host 0.0.0.0`
2. Find your laptop's local IP: `ipconfig` → look for IPv4 (e.g. `192.168.1.5`)
3. Open `gas_driver_app/lib/services/api_service.dart`
4. Update `_ngrokUrl` to your IP: `http://192.168.1.5:8000`

---

## 🗂️ Quick Reference Commands

```powershell
# ─── Backend ─────────────────────────────────────────────────────
# Activate venv
.\venv\Scripts\Activate.ps1

# Run backend (development mode with hot-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Deactivate venv when done
deactivate

# ─── Flutter App ─────────────────────────────────────────────────
cd gas_driver_app

# Install dependencies
flutter pub get

# Run app on connected device
flutter run

# Build release APK
flutter build apk --release
```

---

## ✅ Verify Everything is Working

1. **Backend running** → Open http://localhost:8000/docs in browser, you should see the Swagger UI
2. **Admin Dashboard** → Open http://localhost:8000 — you should see the login page
3. **Mobile App** → Login with a driver's phone number and PIN

---

## 🐛 Common Issues

| Problem | Solution |
|---------|----------|
| `uvicorn not found` | Make sure venv is activated: `.\venv\Scripts\Activate.ps1` |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| `App can't connect to backend` | Make sure backend is running with `--host 0.0.0.0` and check your IP in `api_service.dart` |
| `flutter not found` | Add Flutter's `bin` folder to your system PATH |
| `Execution policy error` | Run `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `pymongo connection error` | Check your `MONGODB_URI` in the `.env` file |
