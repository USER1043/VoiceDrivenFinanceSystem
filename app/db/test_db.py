from app.db.session import engine

try:
    with engine.connect() as conn:
        print("✅ Connected to Supabase PostgreSQL")
except Exception as e:
    print("❌ Connection failed:", e)
