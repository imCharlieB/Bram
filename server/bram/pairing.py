"""Pairing with a Home Assistant (G1).

The owner copies a one-time code from the server to the integration. The code
holds the server certificate's fingerprint, so the integration knows it reached
the right server, and a secret, so the server knows it is the right house.
"""
from __future__ import annotations

import datetime
import hashlib
import os
import secrets
import sqlite3
import ssl
import time
from collections.abc import Callable
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

CODE_LIFETIME = 600

_SCHEMA = """
CREATE TABLE IF NOT EXISTS house (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS pending (
    secret_hash TEXT PRIMARY KEY, name TEXT NOT NULL, expires REAL NOT NULL);
"""


def _hash(value: str) -> str:
    # Inputs are random and at least 128 bits, so a plain hash is enough.
    return hashlib.sha256(value.encode()).hexdigest()


def ensure_certificate(data: Path) -> tuple[ssl.SSLContext, str]:
    """Create the server certificate once. Returns the TLS context and fingerprint."""
    data.mkdir(parents=True, exist_ok=True)
    key_file, cert_file = data / "server.key", data / "server.crt"
    if not (key_file.exists() and cert_file.exists()):
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "BRAM Server")])
        now = datetime.datetime.now(datetime.UTC)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(days=1))
                .not_valid_after(now + datetime.timedelta(days=3650))
                .sign(key, hashes.SHA256()))
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()))
        cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_file, key_file)
    return context, cert.fingerprint(hashes.SHA256()).hex()


class Pairing:
    def __init__(self, path: Path | str, clock: Callable[[], float] = time.time) -> None:
        self._db = sqlite3.connect(path, timeout=10)
        self._db.executescript(_SCHEMA)
        self._clock = clock

    def new_code(self, name: str, fingerprint: str) -> str:
        secret = secrets.token_hex(16)
        with self._db:
            self._db.execute("DELETE FROM pending WHERE expires < ?", (self._clock(),))
            self._db.execute("INSERT INTO pending VALUES (?, ?, ?)",
                             (_hash(secret), name, self._clock() + CODE_LIFETIME))
        return f"bram1-{fingerprint}-{secret}"

    def redeem(self, secret: str) -> tuple[str, str] | None:
        """Use a code once. Returns (house_id, token)."""
        with self._db:
            row = self._db.execute(
                "DELETE FROM pending WHERE secret_hash = ? RETURNING name, expires",
                (_hash(secret),)).fetchone()
            if row is None or row[1] < self._clock():
                return None
            house_id, token = secrets.token_hex(8), secrets.token_urlsafe(32)
            self._db.execute("INSERT INTO house VALUES (?, ?, ?)",
                             (house_id, row[0], _hash(token)))
        return house_id, token

    def house_for(self, token: str) -> str | None:
        row = self._db.execute("SELECT id FROM house WHERE token_hash = ?",
                               (_hash(token),)).fetchone()
        return row[0] if row else None

    def houses(self) -> list[tuple[str, str]]:
        return self._db.execute("SELECT id, name FROM house ORDER BY name").fetchall()

    def remove(self, house_id: str) -> bool:
        with self._db:
            return self._db.execute("DELETE FROM house WHERE id = ?", (house_id,)).rowcount == 1

    def close(self) -> None:
        self._db.close()
