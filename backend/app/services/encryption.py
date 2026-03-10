from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.FERNET_KEY
    if not key:
        raise ValueError(
            "FERNET_KEY not configured. Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_api_key(key: str) -> str:
    f = _get_fernet()
    return f.encrypt(key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()
