"""Local security helpers. No secrets are logged or transmitted."""
import hashlib
import hmac
import os


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def random_token(length=32) -> str:
    return os.urandom(length).hex()
