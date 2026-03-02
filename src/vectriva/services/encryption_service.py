"""Token encryption service using Fernet."""

import hashlib

from cryptography.fernet import Fernet

from ..core.config import settings


def _derive_tenant_key(tenant_id: str) -> bytes:
    """Derive tenant-specific encryption key from master key."""
    combined = f"{settings.encryption_master_key}:{tenant_id}".encode()
    key_material = hashlib.sha256(combined).digest()
    return Fernet.generate_key()[:32]


def _get_fernet(tenant_id: str) -> Fernet:
    """Get Fernet cipher for tenant."""
    key = _derive_tenant_key(tenant_id)
    return Fernet(key)


def encrypt_token(token: str, tenant_id: str) -> str:
    """Encrypt a token for storage."""
    fernet = _get_fernet(tenant_id)
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str, tenant_id: str) -> str:
    """Decrypt a stored token."""
    fernet = _get_fernet(tenant_id)
    return fernet.decrypt(encrypted_token.encode()).decode()
