from cryptography.fernet import Fernet
import os

_fernet = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.getenv("SECRET_KEY")
        if not key:
            raise RuntimeError("SECRET_KEY environment variable is not set")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_pat(pat: str) -> str:
    return _get_fernet().encrypt(pat.encode()).decode()


def decrypt_pat(encrypted_pat: str) -> str:
    return _get_fernet().decrypt(encrypted_pat.encode()).decode()


def mask_pat(pat: str) -> str:
    if len(pat) <= 4:
        return "****"
    return "*" * (len(pat) - 4) + pat[-4:]
