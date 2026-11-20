"""Password hashing with PBKDF2-SHA256 (standard library only)."""

import base64
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 390_000


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "$".join(
        [
            ALGORITHM,
            str(iterations),
            base64.b64encode(salt).decode(),
            base64.b64encode(digest).decode(),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$")
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(digest_b64)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    return hmac.compare_digest(digest, expected)
