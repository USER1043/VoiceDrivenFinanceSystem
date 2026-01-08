import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logger = logging.getLogger("db-session")

# -------------------------------------------------
# SUPABASE CONFIGURATION
# -------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

# Clean up common env issues
SUPABASE_URL = SUPABASE_URL.strip()
SUPABASE_KEY = SUPABASE_KEY.strip()

# -------------------------------------------------
# SUPABASE CLIENT
# -------------------------------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------------------------
# DEPENDENCY (FASTAPI)
# -------------------------------------------------
def get_supabase() -> Client:
    """
    FastAPI dependency that provides a Supabase client
    """
    return supabase
