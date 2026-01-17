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