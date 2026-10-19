"""Hashing + random code generation. Bcrypt hashes here are identical
in format to the ones Supabase's SQL seed creates with pgcrypto's
crypt(..., gen_salt('bf')) — both are standard bcrypt, so either side
can verify the other's hashes."""

import random
import secrets
import string

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_secret(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_secret(raw: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(raw, hashed)
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
