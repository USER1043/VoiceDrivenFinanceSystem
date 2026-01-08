import json
from typing import Dict, Optional
from app.cache.redis_client import redis_client

STATE_TTL = 300  # 5 minutes


def get_state(user_id: int) -> Optional[Dict]:
    data = redis_client.get(f"state:{user_id}")
    return json.loads(data) if data else None


def save_state(user_id: int, state: Dict):
    redis_client.setex(
        f"state:{user_id}",
        STATE_TTL,
        json.dumps(state)
    )


def clear_state(user_id: int):
    redis_client.delete(f"state:{user_id}")
