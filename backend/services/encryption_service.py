"""
Encryption Service
Secure encryption/decryption for sensitive data like API credentials.
Uses AES-GCM encryption with keys from environment variables.
"""
import os
import base64
import logging
from typing import Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Handles encryption and decryption of sensitive data.
    Uses Fernet (AES-128-CBC with HMAC) for symmetric encryption.
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption service.
        
        Args:
            encryption_key: Base64-encoded encryption key or passphrase.
                          If None, uses KALSHI_KEYS_ENCRYPTION_KEY env var.
        """
        self._key = self._get_or_generate_key(encryption_key)
        self._fernet = Fernet(self._key)
    
    def _get_or_generate_key(self, provided_key: Optional[str]) -> bytes:
        """Get encryption key from env or generate from passphrase."""
        key_source = provided_key or os.environ.get('KALSHI_KEYS_ENCRYPTION_KEY')
        
        if not key_source:
            # Generate a new key for development/testing
            # In production, this MUST be set via environment variable
            logger.warning("KALSHI_KEYS_ENCRYPTION_KEY not set! Using generated key (NOT SECURE FOR PRODUCTION)")
            return Fernet.generate_key()
        
        # If it's already a valid Fernet key, use it directly
        try:
            if len(base64.urlsafe_b64decode(key_source)) == 32:
                return key_source.encode() if isinstance(key_source, str) else key_source
        except Exception:
            pass
        
        # Otherwise, derive a key from the passphrase
        return self._derive_key_from_passphrase(key_source)
    
    def _derive_key_from_passphrase(self, passphrase: str) -> bytes:
        """Derive a Fernet-compatible key from a passphrase using PBKDF2."""
        # Use a consistent salt (in production, you might want to store this per-user)
        salt = b'predictpod_kalshi_v1'
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,  # OWASP recommended minimum
            backend=default_backend()
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return key
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""
        
        encrypted = self._fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ""
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self._fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data - key may have changed")
    
    def mask_key(self, key: str, show_chars: int = 4) -> str:
        """
        Create a masked version of a key for display.
        
        Args:
            key: The key to mask
            show_chars: Number of characters to show at the end
            
        Returns:
            Masked key like "****abcd"
        """
        if not key:
            return ""
        
        if len(key) <= show_chars:
            return "*" * len(key)
        
        return "*" * (len(key) - show_chars) + key[-show_chars:]


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    Use this to create a key for KALSHI_KEYS_ENCRYPTION_KEY env var.
    
    Returns:
        Base64-encoded 32-byte key
    """
    return Fernet.generate_key().decode()


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get or create the singleton encryption service."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
