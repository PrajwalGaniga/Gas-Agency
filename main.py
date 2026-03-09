from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from app.database import db 
import traceback

# Import Routers
from admin import admin_router
from customer import customer_router
from driver import driver_router

app = FastAPI(title="Gas Delivery System", version="2.0")

# --- GLOBAL EXCEPTION HANDLERS ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"❌ CRITICAL ERROR: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "An unexpected server error occurred.", "details": str(exc)},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_msg = ", ".join([f"{e['loc'][-1]}: {e['msg']}" for e in errors])
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": f"Validation Error: {error_msg}"},
    )

# Include Routers
app.include_router(admin_router)
app.include_router(customer_router)
app.include_router(driver_router)

@app.on_event("startup")
async def startup_db_client():
    # Database connection logic is already handled in app.database
    print("--- 🚀 App Started ---")