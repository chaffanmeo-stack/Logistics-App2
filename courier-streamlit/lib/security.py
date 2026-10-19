"""Hashing + random code generation. Uses the `bcrypt` package directly
(not passlib) — passlib 1.7.4 is incompatible with bcrypt>=4.1 and
silently fails verification, which was causing logins to always fail."""

import random
import secrets
import string

import bcrypt


def hash_secret(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_secret(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def generate_pin() -> str:
    return "".join(random.choices(string.digits, k=6))


def generate_delivery_code() -> str:
    return "".join(random.choices(string.digits, k=4))


def generate_tracking_id() -> str:
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"TRK-{suffix}"
