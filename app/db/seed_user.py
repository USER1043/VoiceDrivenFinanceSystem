from app.db.session import SessionLocal
from app.db.models import User

db = SessionLocal()

user = User(email="demo@hackathon.com")
db.add(user)
db.commit()
db.refresh(user)

print("Demo user created with ID:", user.id)

db.close()