import redis
import json

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


def get_cached_approved():
    data = redis_client.get("approved_docs")
    return json.loads(data) if data else None

def set_cached_approved(data):
    redis_client.set("approved_docs", json.dumps(data), ex=300)



def get_cached_dashboard():
    data = redis_client.get("dashboard_stats")
    return json.loads(data) if data else None

def set_cached_dashboard(data):
    redis_client.set("dashboard_stats", json.dumps(data), ex=300)



def clear_cache():
    redis_client.delete("approved_docs")
    redis_client.delete("dashboard_stats")