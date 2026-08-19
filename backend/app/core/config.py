"""Environment / settings loader."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / '.env')

# --- required ---
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ['JWT_SECRET']

# --- optional ---
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')
EMERGENT_EMAIL_KEY = os.environ.get('EMERGENT_EMAIL_KEY', '')
EMAIL_FROM_NAME = os.environ.get('EMAIL_FROM_NAME', 'NexusCRM')
APP_URL = os.environ.get('APP_URL', '')
CORS_ORIGINS_RAW = os.environ.get('CORS_ORIGINS', '')

# --- constants ---
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
JWT_ALG = "HS256"
JWT_EXP_HOURS = 24 * 7
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "1") != "0"
