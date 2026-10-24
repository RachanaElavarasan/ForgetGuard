import os

# Configuration constants for ForgetGuard

# Base Directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Flask secret key
SECRET_KEY = os.environ.get('FORGETGUARD_SECRET', 'forgetguard-super-secret-key-2026')

# SQLite database path
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'forgetguard.db')}")
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Grace period (seconds) before raising empty-room alerts after last occupancy
WAIT_PERIOD_SECONDS = int(os.environ.get('WAIT_PERIOD_SECONDS', 30))

# IoT Device Shared API Key for hardware/simulator authentication
API_KEY = os.environ.get('FORGETGUARD_API_KEY', 'sample_key_123')
