from fastapi import HTTPException, Request
import time

# Store requests per IP
request_log = {}

MAX_REQUESTS = 5
WINDOW_SIZE = 60  # seconds

def check_rate_limit(request: Request):
    ip = request.client.host
    current_time = time.time()

    if ip not in request_log:
        request_log[ip] = []

    # remove old requests (older than 60 sec)
    request_log[ip] = [
        timestamp for timestamp in request_log[ip]
        if current_time - timestamp < WINDOW_SIZE
    ]

    if len(request_log[ip]) >= MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Too many login attempts",
                "message": "Try again after some time (1 minute limit exceeded)"
            }
        )

    request_log[ip].append(current_time)