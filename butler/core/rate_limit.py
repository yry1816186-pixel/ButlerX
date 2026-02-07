from __future__ import annotations

import time
import logging
from collections import defaultdict
from typing import Dict, Optional, Tuple
from functools import wraps
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_limit: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_limit = burst_limit
        
        self._minute_buckets: Dict[str, list[float]] = defaultdict(list)
        self._hour_buckets: Dict[str, list[float]] = defaultdict(list)
        self._cleanup_interval = 300
        self._last_cleanup = time.time()

    def _cleanup_old_requests(self) -> None:
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        cutoff_minute = now - 60
        cutoff_hour = now - 3600
        
        for client_id, timestamps in list(self._minute_buckets.items()):
            self._minute_buckets[client_id] = [
                ts for ts in timestamps if ts > cutoff_minute
            ]
            if not self._minute_buckets[client_id]:
                del self._minute_buckets[client_id]
        
        for client_id, timestamps in list(self._hour_buckets.items()):
            self._hour_buckets[client_id] = [
                ts for ts in timestamps if ts > cutoff_hour
            ]
            if not self._hour_buckets[client_id]:
                del self._hour_buckets[client_id]
        
        self._last_cleanup = now

    def _get_client_id(self, request: Request) -> str:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            return f"auth:{auth_header}"
        
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            return f"ip:{x_forwarded_for.split(',')[0].strip()}"
        
        x_real_ip = request.headers.get("X-Real-IP")
        if x_real_ip:
            return f"ip:{x_real_ip}"
        
        return f"ip:{request.client.host if request.client else 'unknown'}"

    def check_rate_limit(self, request: Request) -> Tuple[bool, Optional[str]]:
        self._cleanup_old_requests()
        
        client_id = self._get_client_id(request)
        now = time.time()
        
        minute_requests = self._minute_buckets[client_id]
        hour_requests = self._hour_buckets[client_id]
        
        recent_minute = [ts for ts in minute_requests if ts > now - 10]
        if len(recent_minute) >= self.burst_limit:
            return False, "Burst limit exceeded"
        
        minute_requests = [ts for ts in minute_requests if ts > now - 60]
        if len(minute_requests) >= self.requests_per_minute:
            return False, f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
        
        hour_requests = [ts for ts in hour_requests if ts > now - 3600]
        if len(hour_requests) >= self.requests_per_hour:
            return False, f"Rate limit exceeded: {self.requests_per_hour} requests per hour"
        
        self._minute_buckets[client_id].append(now)
        self._hour_buckets[client_id].append(now)
        
        return True, None

    def get_remaining(self, request: Request) -> Dict[str, int]:
        client_id = self._get_client_id(request)
        now = time.time()
        
        minute_requests = [ts for ts in self._minute_buckets.get(client_id, []) if ts > now - 60]
        hour_requests = [ts for ts in self._hour_buckets.get(client_id, []) if ts > now - 3600]
        
        return {
            "per_minute_remaining": max(0, self.requests_per_minute - len(minute_requests)),
            "per_hour_remaining": max(0, self.requests_per_hour - len(hour_requests)),
            "burst_remaining": max(0, self.burst_limit - len([ts for ts in minute_requests if ts > now - 10])),
        }


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def rate_limit(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_limit: int = 10,
):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            limiter = get_rate_limiter()
            
            allowed, error_msg = limiter.check_rate_limit(request)
            if not allowed:
                remaining = limiter.get_remaining(request)
                headers = {
                    "X-RateLimit-Limit-Minute": str(requests_per_minute),
                    "X-RateLimit-Remaining-Minute": str(remaining["per_minute_remaining"]),
                    "X-RateLimit-Limit-Hour": str(requests_per_hour),
                    "X-RateLimit-Remaining-Hour": str(remaining["per_hour_remaining"]),
                    "Retry-After": "60",
                }
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error_msg,
                    headers=headers,
                )
            
            result = await func(request, *args, **kwargs)
            return result
        
        return wrapper
    return decorator


def check_rate_limit_middleware(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_limit: int = 10,
):
    async def middleware(request: Request, call_next):
        limiter = get_rate_limiter()
        
        allowed, error_msg = limiter.check_rate_limit(request)
        if not allowed:
            remaining = limiter.get_remaining(request)
            headers = {
                "X-RateLimit-Limit-Minute": str(requests_per_minute),
                "X-RateLimit-Remaining-Minute": str(remaining["per_minute_remaining"]),
                "X-RateLimit-Limit-Hour": str(requests_per_hour),
                "X-RateLimit-Remaining-Hour": str(remaining["per_hour_remaining"]),
                "Retry-After": "60",
            }
            return HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg,
                headers=headers,
            )
        
        response = await call_next(request)
        
        remaining = limiter.get_remaining(request)
        response.headers["X-RateLimit-Limit-Minute"] = str(requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(remaining["per_minute_remaining"])
        response.headers["X-RateLimit-Limit-Hour"] = str(requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(remaining["per_hour_remaining"])
        
        return response
    
    return middleware
