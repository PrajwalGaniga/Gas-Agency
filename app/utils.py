from passlib.context import CryptContext
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Password Hashing Configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def generate_otp():
    return str(random.randint(100000, 999999))

# --- REAL EMAIL CONFIGURATION ---
SENDER_EMAIL = "prajwalganiga06@gmail.com"
APP_PASSWORD = "cpkb hwsv pawn ihtj" # Your specific Gmail App Password

def send_otp_email(receiver_email, otp):
    """
    Sends a real OTP email using Gmail SMTP and an App Password.
    """
    subject = "GasFlow Admin Approval OTP"
    body = f"""
    Hello Developer,
    
    A new admin is requesting access to the GasFlow System. 
    Please provide them with the following verification code to complete their registration:
    
    VERIFICATION CODE: {otp}
    
    If you did not expect this request, please ignore this email.
    """

    # Setup the MIME message
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # Secure the connection
        server.login(SENDER_EMAIL, APP_PASSWORD)
        
        # Send the email
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, receiver_email, text)
        server.quit()
        
        print(f"✅ OTP email successfully sent to {receiver_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False
    
from datetime import datetime, timedelta, timezone

# Global IST Timezone Object
IST = timezone(timedelta(hours=5, minutes=30))

def to_ist(dt):
    """Converts any datetime (aware or naive) to IST. Assumes naive is UTC."""
    if not dt: return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def to_utc(dt):
    """Converts an aware datetime to UTC for database storage."""
    if not dt: return None
    return dt.astimezone(timezone.utc)

def ist_now():
    """Returns current time in Indian Standard Time."""
    return datetime.now(timezone.utc).astimezone(IST)

def ist_day_start(date_obj):
    """Returns the UTC equivalent of 00:00:00 IST for a given date."""
    ist_start = datetime.combine(date_obj, datetime.min.time()).replace(tzinfo=IST)
    return to_utc(ist_start)

def ist_day_end(date_obj):
    """Returns the UTC equivalent of 23:59:59 IST for a given date."""
    ist_end = datetime.combine(date_obj, datetime.max.time()).replace(tzinfo=IST)
    return to_utc(ist_end)

# 🛠️ CRITICAL FIX: Inject helpers into Jinja2 environment (Fixes UndefinedError)

