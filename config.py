import os

from dotenv import load_dotenv
load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'attendance-system-secret-key')
    DEBUG = os.getenv('DEBUG', 'False')
    
    # PostgreSQL settings
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/attendance')

    # Face recognition settings
    FACE_MODEL = os.getenv('FACE_MODEL', 'SFace')
    FACE_DETECTOR = os.getenv('FACE_DETECTOR', 'opencv')
    FACE_THRESHOLD = float(os.getenv('FACE_THRESHOLD', '0.50'))
    FACE_TOP_K = int(os.getenv('FACE_TOP_K', '5'))
    
    # Google Sheets settings
    GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', None)
    GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID', '')
    GOOGLE_SHEETS_PERSONNEL_TAB = os.getenv('GOOGLE_SHEETS_PERSONNEL_TAB', 'personnel')
    GOOGLE_SHEETS_ATTENDANCE_TAB = os.getenv('GOOGLE_SHEETS_ATTENDANCE_TAB', 'attendance')
    
    # Google Cloud Storage settings
    GCS_CREDENTIALS_PATH = os.getenv('GCS_CREDENTIALS_PATH', None)
    GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'attendance-system-v1')
    GCS_USE_PUBLIC_URLS = os.getenv('GCS_USE_PUBLIC_URLS', 'False')
    GCS_SIGNED_URL_EXPIRY_HOURS = int(os.getenv('GCS_SIGNED_URL_EXPIRY_HOURS', '24'))