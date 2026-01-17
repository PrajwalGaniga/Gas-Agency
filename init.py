# init_admin.py
from app.database import admin_collection
from app.utils import get_password_hash

def create_super_admin():
    # Hardcoded Details
    email = "prajwalganiga06@gmail.com"
    raw_password = "12345"
    full_name = "Prajwal Ganiga"

    # Check if admin already exists to prevent duplicates
    if admin_collection.find_one({"email": email}):
        print("⚠️ Admin already exists!")
        return

    # Create Admin Object
    admin_data = {
        "username": full_name,
        "email": email,
        "password_hash": get_password_hash(raw_password), # HASHING HAPPENS HERE
        "role": "super_admin"
    }

    # Insert into MongoDB
    admin_collection.insert_one(admin_data)
    print(f"✅ Admin '{full_name}' created successfully with email: {email}")

if __name__ == "__main__":
    create_super_admin()