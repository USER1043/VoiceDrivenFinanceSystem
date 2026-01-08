# dependencies
from supabase import Client
from app.db.session import get_supabase

def get_db() -> Client:
    """
    FastAPI dependency that provides a Supabase client.
    Note: kept the name 'get_db' for compatibility with existing code.
    """
    return get_supabase()
