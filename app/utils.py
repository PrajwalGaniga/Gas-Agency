# app/utils.py
import resend
from passlib.context import CryptContext
import random
from datetime import datetime, timedelta, timezone

# 🔑 RESEND CONFIGURATION
resend.api_key = "re_RtZAfyor_gpysfeE37rcjppacAfVKVzHW"

# Password Hashing Configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(receiver_email, otp):
    """
    Sends an OTP email using the Resend API.
    This replaces SMTP to avoid Render network blockages.
    """
    try:
        params = {
            "from": "onboarding@resend.dev",
            "to": receiver_email,
            "subject": "GasFlow Admin Approval OTP",
            "html": f"""
                <div style="font-family: sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #eef2ff; border-radius: 16px; background-color: #ffffff;">
                    <h2 style="color: #4f46e5; text-align: center;">Admin Approval Required</h2>
                    <p style="color: #374151; font-size: 16px; line-height: 1.5;">Hello Developer,</p>
                    <p style="color: #374151; font-size: 14px; line-height: 1.5;">A new admin is requesting access to the GasFlow System. Please provide them with the following code:</p>
                    <div style="background-color: #f8fafc; padding: 15px; border-radius: 12px; text-align: center; margin: 20px 0;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #111827;">{otp}</span>
                    </div>
                    <p style="color: #6b7280; font-size: 12px; text-align: center;">If you did not expect this request, please ignore this email.</p>
                </div>
            """
        }
        
        # 🚀 Execute API Call
        resend.Emails.send(params)
        
        print(f"✅ OTP email successfully sent via Resend API to {receiver_email}")
        return True
    except Exception as e:
        print(f"❌ Resend API Error: {e}")
        return False

# --- IST HELPERS ---
IST = timezone(timedelta(hours=5, minutes=30))

def to_ist(dt):
    if not dt: return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def to_utc(dt):
    if not dt: return None
    return dt.astimezone(timezone.utc)

def ist_now():
    return datetime.now(timezone.utc).astimezone(IST)

def ist_day_start(date_obj):
    ist_start = datetime.combine(date_obj, datetime.min.time()).replace(tzinfo=IST)
    return to_utc(ist_start)

def ist_day_end(date_obj):
    ist_end = datetime.combine(date_obj, datetime.max.time()).replace(tzinfo=IST)
    return to_utc(ist_end)