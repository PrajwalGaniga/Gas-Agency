from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import db 

# Import Routers
from admin import admin_router
from customer import customer_router
from driver import driver_router

app = FastAPI(title="Gas Delivery System", version="2.0")

# Mount Static if needed (Assuming standard folder structure)
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Include Routers
app.include_router(admin_router)
app.include_router(customer_router)
app.include_router(driver_router)

@app.on_event("startup")
async def startup_db_client():
    # Database connection logic is already handled in app.database
    print("--- 🚀 App Started ---")