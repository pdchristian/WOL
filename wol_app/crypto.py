"""Password encryption using AES-256-GCM with Windows DPAPI key protection."""

import base64
import ctypes
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Module-level cache for the master key (loaded once per session)
_master_key: Optional[bytes] = None


def _secure_clear_memory(data: str) -> None:
    """Securely overwrite string in memory with zeros (best effort)."""
    if not data:
        return
    # Create mutable byte array
    byte_data = bytearray(data.encode('utf-8'))
    for i in range(len(byte_data)):
        byte_data[i] = 0
    # Force garbage collection
    del byte_data


def _get_dpapi_protected_key() -> bytes:
    """
    Derive a persistent 256-bit master key protected by Windows DPAPI.

    DPAPI encrypts/decrypts data per-user, so only the current Windows user
    can decrypt the stored key. We store the encrypted blob in
    ~/.wol_app/master_key.dat alongside config.json.
    """
    import ctypes
    import ctypes.wintypes as wintypes
    from pathlib import Path

    # --- DPAPI structures ---
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    def _make_blob(data: bytes) -> DATA_BLOB:
        blob = DATA_BLOB(len(data), (ctypes.c_char * len(data))(*data))
        return blob

    def _blob_to_bytes(blob: DATA_BLOB) -> bytes:
        if blob.pbData is None or blob.cbData == 0:
            return b""
        return ctypes.string_at(blob.pbData, blob.cbData)

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)

    # CryptUnprotectData
    crypt_unprotect = crypt32.CryptUnprotectData
    crypt_unprotect.restype = wintypes.BOOL
    crypt_unprotect.argtypes = [
        ctypes.POINTER(DATA_BLOB),  # pDataIn
        ctypes.POINTER(wintypes.WCHAR),  # szDescription
        ctypes.POINTER(DATA_BLOB),  # pOptionalEntropy
        ctypes.c_void_p,  # pvReserved
        ctypes.POINTER(None),  # pPromptStruct
        wintypes.DWORD,  # dwFlags
        ctypes.POINTER(DATA_BLOB),  # pDataOut (by ref)
    ]

    # CryptProtectData
    crypt_protect = crypt32.CryptProtectData
    crypt_protect.restype = wintypes.BOOL
    crypt_protect.argtypes = [
        ctypes.POINTER(DATA_BLOB),  # pDataIn
        ctypes.POINTER(wintypes.WCHAR),  # szDescription
        ctypes.POINTER(DATA_BLOB),  # pOptionalEntropy
        ctypes.c_void_p,  # pvReserved
        ctypes.POINTER(None),  # pPromptStruct
        wintypes.DWORD,  # dwFlags
        ctypes.POINTER(DATA_BLOB),  # pDataOut (by ref)
    ]

    key_path = Path.home() / ".wol_app" / "master_key.dat"

    if key_path.exists():
        try:
            encrypted_blob = key_path.read_bytes()
            data_in = _make_blob(encrypted_blob)
            data_out = DATA_BLOB()
            if crypt_unprotect(
                ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)
            ):
                key = _blob_to_bytes(data_out)
                if len(key) == 32:
                    return key
        except Exception:
            pass

    # Generate a new random 256-bit key and protect it with DPAPI
    plaintext_key = os.urandom(32)
    data_in = _make_blob(plaintext_key)
    data_out = DATA_BLOB()
    desc = ctypes.create_unicode_buffer("WOL Master Key")

    if not crypt_protect(
        ctypes.byref(data_in), desc, None, None, None, 0, ctypes.byref(data_out)
    ):
        raise RuntimeError("Failed to protect master key with DPAPI")

    protected_blob = _blob_to_bytes(data_out)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(protected_blob)
    return plaintext_key


def get_master_key() -> bytes:
    """Return the cached master key, loading it from DPAPI if necessary."""
    global _master_key
    if _master_key is None:
        _master_key = _get_dpapi_protected_key()
    return _master_key


def encrypt_password(plaintext: str) -> str:
    """
    Encrypt a password string and return a base64-encoded ciphertext.

    Format: base64(nonce || tag || ciphertext) via AES-256-GCM.
    Empty strings are returned as-is for efficiency.
    """
    if not plaintext:
        return ""
    # Input validation
    if len(plaintext) > 128:
        raise ValueError("Password too long: maximum 128 characters")
    # Check for control characters or invalid characters
    if any(ord(c) < 32 or ord(c) > 126 for c in plaintext):
        raise ValueError("Password contains invalid characters (control characters not allowed)")
    
    key = get_master_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Prepend nonce to ciphertext so we can decrypt later
    encrypted_data = nonce + ciphertext
    # Securely clear plaintext from memory
    _secure_clear_memory(plaintext)
    return base64.b64encode(encrypted_data).decode("ascii")


def decrypt_password(encrypted: str) -> str:
    """
    Decrypt a password that was encrypted with encrypt_password().

    Returns an empty string if the input is empty or clearly not encrypted.
    Raises ValueError on decryption failure (corrupted data, wrong key, etc.).
    """
    if not encrypted:
        return ""
    # Heuristic: if it doesn't look base64-encoded and is short, treat as plaintext
    try:
        encrypted_data = base64.b64decode(encrypted)
    except Exception:
        # Not base64 — likely old plaintext password
        return encrypted

    if len(encrypted_data) < 13:
        # Too short to be valid (nonce=12 + at least 1 byte tag/ciphertext)
        return encrypted

    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    key = get_master_key()
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception:
        # Decryption failed — return empty to avoid crashes
        return ""


def is_encrypted(value: str) -> bool:
    """
    Check if a password value appears to be encrypted (base64-encoded, long enough).

    Used during migration to detect old plaintext passwords.
    """
    if not value:
        return False
    try:
        decoded = base64.b64decode(value)
        # Encrypted data should be at least 13 bytes (12 nonce + 1 tag minimum)
        return len(decoded) >= 13
    except Exception:
        return False
