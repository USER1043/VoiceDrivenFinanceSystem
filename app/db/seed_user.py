from app.db.session import get_supabase

supabase = get_supabase()

# Check if user already exists
response = supabase.table("users").select("*").eq("email", "demo@hackathon.com").execute()

if not response.data:
    # Create demo user
    response = supabase.table("users").insert({
        "email": "demo@hackathon.com"
    }).execute()
    
    if response.data:
        user_id = response.data[0]["id"]
        print(f"Demo user created with ID: {user_id}")
    else:
        print("Failed to create demo user")
else:
    user_id = response.data[0]["id"]
    print(f"Demo user already exists with ID: {user_id}")
