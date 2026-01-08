from dotenv import load_dotenv

load_dotenv()

from app.cache.redis_client import redis_client

redis_client.set("health_check", "ok")
print(redis_client.get("health_check"))
