from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionManager:
    def __init__(self, master_key: Optional[str] = None) -> None:
        self.master_key = master_key or self._get_or_create_master_key()
        self._fernet = self._create_fernet()

    def _get_or_create_master_key(self) -> str:
        key_path = os.path.join(os.path.dirname(__file__), "..", "data", "encryption.key")
        
        if os.path.exists(key_path):
            try:
                with open(key_path, "rb") as f:
                    return f.read().decode()
            except (IOError, OSError):
                pass
        
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        try:
            with open(key_path, "wb") as f:
                f.write(key.encode())
            os.chmod(key_path, 0o600)
        except (IOError, OSError):
            pass
        
        return key

    def _create_fernet(self) -> Fernet:
        salt = hashlib.sha256(self.master_key.encode()).digest()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)

    def encrypt(self, data: str) -> str:
        encrypted = self._fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> Optional[str]:
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception:
            return None

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        return self.encrypt(json.dumps(data))

    def decrypt_dict(self, encrypted_data: str) -> Optional[Dict[str, Any]]:
        try:
            decrypted = self.decrypt(encrypted_data)
            if decrypted:
                return json.loads(decrypted)
        except (ValueError, json.JSONDecodeError):
            pass
        return None

    def encrypt_password(self, password: str) -> str:
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt,
            100000
        )
        return f"{base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(key).decode()}"

    def verify_password(self, password: str, stored: str) -> bool:
        try:
            salt_b64, key_b64 = stored.split("$")
            salt = base64.urlsafe_b64decode(salt_b64)
            stored_key = base64.urlsafe_b64decode(key_b64)
            
            key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt,
                100000
            )
            
            from hmac import compare_digest
            return compare_digest(stored_key, key)
        except (ValueError, IndexError):
            return False


_encryption_manager: Optional[EncryptionManager] = None


def get_encryption_manager() -> EncryptionManager:
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


def encrypt_sensitive(value: str) -> str:
    return get_encryption_manager().encrypt(value)


def decrypt_sensitive(encrypted_value: str) -> Optional[str]:
    return get_encryption_manager().decrypt(encrypted_value)
