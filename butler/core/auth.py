from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()


@dataclass
class User:
    username: str
    role: str = "user"
    api_key_hash: Optional[str] = None


class AuthManager:
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or os.getenv("BUTLER_SECRET_KEY", secrets.token_hex(32))
        self.users: Dict[str, User] = {}
        self.api_keys: Dict[str, User] = {}
        self.session_tokens: Dict[str, Tuple[str, float]] = {}
        self._init_default_users()

    def _init_default_users(self):
        admin_pass = os.getenv("BUTLER_ADMIN_PASSWORD", "admin123")
        admin_hash = self._hash_password(admin_pass)
        self.users["admin"] = User(username="admin", role="admin", api_key_hash=None)
        self._password_hashes = {"admin": admin_hash}

        user_pass = os.getenv("BUTLER_USER_PASSWORD", "user123")
        user_hash = self._hash_password(user_pass)
        self.users["user"] = User(username="user", role="user", api_key_hash=None)
        self._password_hashes["user"] = user_hash

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            100000
        )
        return f"{salt}${key.hex()}"

    def verify_password(self, username: str, password: str) -> bool:
        if username not in self._password_hashes:
            return False
        stored = self._password_hashes[username]
        salt, key_hex = stored.split("$")
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            100000
        )
        return hmac.compare_digest(key.hex(), key_hex)

    def generate_api_key(self, username: str) -> str:
        if username not in self.users:
            raise ValueError(f"User {username} not found")
        api_key = f"bk_{secrets.token_urlsafe(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        user = self.users[username]
        user.api_key_hash = api_key_hash
        self.api_keys[api_key_hash] = user
        return api_key

    def verify_api_key(self, api_key: str) -> Optional[User]:
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return self.api_keys.get(api_key_hash)

    def generate_token(self, username: str, expires_in: int = 3600) -> str:
        if username not in self.users:
            raise ValueError(f"User {username} not found")
        user = self.users[username]
        payload = {
            "username": username,
            "role": user.role,
            "exp": time.time() + expires_in,
            "iat": time.time()
        }
        signature = self._sign_payload(payload)
        token = f"{json.dumps(payload)}.{signature}"
        self.session_tokens[signature] = (username, payload["exp"])
        return token

    def _sign_payload(self, payload: Dict) -> str:
        payload_str = json.dumps(payload, sort_keys=True)
        return hmac.new(
            self.secret_key.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

    def verify_token(self, token: str) -> Optional[User]:
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None
            payload_str, signature = parts
            payload = json.loads(payload_str)
            
            expected_sig = hmac.new(
                self.secret_key.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_sig):
                return None
            
            if payload.get("exp", 0) < time.time():
                return None
            
            username = payload.get("username")
            return self.users.get(username)
        except (ValueError, KeyError):
            return None

    def revoke_token(self, token: str) -> bool:
        try:
            signature = token.split(".")[1]
            if signature in self.session_tokens:
                del self.session_tokens[signature]
                return True
        except IndexError:
            pass
        return False

    def require_role(self, user: User, required_role: str) -> bool:
        role_hierarchy = {"admin": 3, "operator": 2, "user": 1, "viewer": 0}
        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        return user_level >= required_level


_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


async def verify_api_key_optional(request: Request) -> Optional[User]:
    auth_header = request.headers.get("Authorization") or request.headers.get("X-API-Key")
    if not auth_header:
        return None
    
    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:]
    else:
        api_key = auth_header
    
    auth = get_auth_manager()
    user = auth.verify_api_key(api_key)
    if user:
        request.state.user = user
    return user


async def verify_token_optional(request: Request) -> Optional[User]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header[7:]
    auth = get_auth_manager()
    user = auth.verify_token(token)
    if user:
        request.state.user = user
    return user


async def get_current_user(request: Request) -> User:
    auth = get_auth_manager()
    
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials"
        )
    
    if auth_header.startswith("Bearer "):
        token_or_key = auth_header[7:]
        
        user = auth.verify_token(token_or_key)
        if user:
            request.state.user = user
            return user
        
        user = auth.verify_api_key(token_or_key)
        if user:
            request.state.user = user
            return user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials"
    )


async def get_admin_user(request: Request) -> User:
    user = await get_current_user(request)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user


def require_role(required_role: str):
    async def role_checker(request: Request) -> User:
        user = await get_current_user(request)
        auth = get_auth_manager()
        if not auth.require_role(user, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{required_role} role required"
            )
        return user
    return role_checker
