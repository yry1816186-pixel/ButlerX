from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SENSITIVE_FIELDS = {
    "email_password",
    "ha_token",
    "gateway_token",
    "openclaw_gateway_password",
    "dashan_mqtt_password",
    "asr_api_key",
    "search_api_key",
    "image_api_key",
    "llm_api_key",
    "embedding_api_key",
    "openclaw_gateway_token",
}

ENCRYPTION_PREFIX = "enc:"
ENCRYPTION_SUFFIX = ":enc"


def is_encrypted_value(value: str) -> bool:
    return value.startswith(ENCRYPTION_PREFIX) and value.endswith(ENCRYPTION_SUFFIX)


def encrypt_sensitive_value(value: str) -> str:
    if not value:
        return value
    try:
        from .encryption import encrypt_sensitive
        encrypted = encrypt_sensitive(value)
        return f"{ENCRYPTION_PREFIX}{encrypted}{ENCRYPTION_SUFFIX}"
    except Exception as e:
        logger.warning(f"Failed to encrypt value: {e}")
        return value


def decrypt_sensitive_value(value: str) -> str:
    if not value or not is_encrypted_value(value):
        return value
    try:
        from .encryption import decrypt_sensitive
        encrypted = value[len(ENCRYPTION_PREFIX):-len(ENCRYPTION_SUFFIX)]
        decrypted = decrypt_sensitive(encrypted)
        return decrypted if decrypted else value
    except Exception as e:
        logger.warning(f"Failed to decrypt value: {e}")
        return value


def decrypt_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    decrypted = {}
    for key, value in config_dict.items():
        if isinstance(value, dict):
            decrypted[key] = decrypt_config(value)
        elif isinstance(value, str) and key.lower() in SENSITIVE_FIELDS:
            decrypted[key] = decrypt_sensitive_value(value)
        else:
            decrypted[key] = value
    return decrypted


def encrypt_config_value(field_name: str, value: str) -> str:
    if field_name.lower() in SENSITIVE_FIELDS and value:
        return encrypt_sensitive_value(value)
    return value


def should_encrypt_field(field_name: str) -> bool:
    return field_name.lower() in SENSITIVE_FIELDS


def get_encrypted_env_var(env_key: str, default: str = "") -> str:
    value = os.getenv(env_key, default)
    if not value:
        return value
    return decrypt_sensitive_value(value)


def is_sensitive_field(field_name: str) -> bool:
    return field_name.lower() in SENSITIVE_FIELDS
