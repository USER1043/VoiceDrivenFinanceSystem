from app.db.session import get_db_cursor

# Check if user already exists
with get_db_cursor(commit=False) as cursor:
    cursor.execute("SELECT id, email FROM users WHERE email = %s", ("demo@hackathon.com",))
    existing_user = cursor.fetchone()

if existing_user:
    user_id = existing_user[0]
    print(f"Demo user already exists with ID: {user_id}")
else:
    # Create demo user
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (email) VALUES (%s) RETURNING id",
            ("demo@hackathon.com",)
        )
        result = cursor.fetchone()
        if result:
            user_id = result[0]
            print(f"Demo user created with ID: {user_id}")
        else:
            print("Failed to create demo user")

