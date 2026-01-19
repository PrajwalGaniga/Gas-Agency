# auth.py
from fastapi import Request, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from datetime import datetime, timedelta
from bson import ObjectId

# --- CONFIGURATION ---
SECRET_KEY = "your_secret_key_here"  # In production, use os.getenv()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# --- TOKEN GENERATION (Moved here from admin.py) ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- ADMIN DEPENDENCY (Cookie Based) ---
def get_current_admin(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        # Remove 'Bearer ' if present (though cookies usually just have the token)
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        admin_id = payload.get("sub")
        if admin_id is None:
            return None
        return ObjectId(admin_id)
    except JWTError:
        return None

# --- DRIVER DEPENDENCY (Header Based) ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="driver/login")

def get_current_driver(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        driver_id = payload.get("sub")
        if driver_id is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return ObjectId(driver_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")