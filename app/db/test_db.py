from app.db.session import get_db_cursor

try:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if result and result[0] == 1:
            print("✅ Connected to PostgreSQL")
        else:
            print("❌ Connection failed: Unexpected result")
except Exception as e:
    print("❌ Connection failed:", e)

