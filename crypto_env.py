# crypto_env.py
# Core encryption/decryption helper for .env and password.txt
# Imported by encrypt.py and decrypt.py
# At runtime, main.py and new_alertcomp.py decrypt into memory only — no plain file created
import sys
import os
from pathlib import Path
from cryptography.fernet import Fernet  # symmetric encryption library (AES-128)

# File paths
PROJECT_ROOT     = Path(__file__).resolve().parent
ENV_PLAIN        = PROJECT_ROOT / ".env"
ENV_ENCRYPTED    = PROJECT_ROOT / ".env.encrypted"
PASSWORD_PLAIN   = PROJECT_ROOT / "password" / "password.txt"
PASSWORD_ENCRYPTED = PROJECT_ROOT / "password" / "password.txt.encrypted"


def get_master_key() -> bytes:
    """Read ENV_MASTER_KEY from OS environment and return as bytes."""
    key = os.environ.get("ENV_MASTER_KEY", "").strip()
    if not key:
        raise SystemExit(
            "ERROR: ENV_MASTER_KEY environment variable is not set.\n"
            "Set it with: $env:ENV_MASTER_KEY = '<your key>'\n"
            "Or permanently: [System.Environment]::SetEnvironmentVariable('ENV_MASTER_KEY', '<your key>', 'User')"
        )
    return key.encode()


def encrypt_file(plain_path: Path, encrypted_path: Path) -> None:
    """Encrypt a plain text file and save as encrypted file."""
    if not plain_path.exists():
        raise FileNotFoundError(f"Plain file not found: {plain_path}")

    key = get_master_key()
    f = Fernet(key)

    plain_bytes = plain_path.read_bytes()
    encrypted_bytes = f.encrypt(plain_bytes)

    encrypted_path.parent.mkdir(parents=True, exist_ok=True)
    encrypted_path.write_bytes(encrypted_bytes)
    print(f"Encrypted: {plain_path} → {encrypted_path}")


def decrypt_file(encrypted_path: Path, plain_path: Path) -> None:
    """Decrypt an encrypted file and save as plain text file."""
    if not encrypted_path.exists():
        raise FileNotFoundError(f"Encrypted file not found: {encrypted_path}")

    key = get_master_key()
    f = Fernet(key)

    encrypted_bytes = encrypted_path.read_bytes()
    try:
        plain_bytes = f.decrypt(encrypted_bytes)
    except Exception:
        raise SystemExit(
            "ERROR: Decryption failed. Wrong master key or corrupted file.\n"
            "Make sure ENV_MASTER_KEY matches the key used to encrypt."
        )

    plain_path.parent.mkdir(parents=True, exist_ok=True)
    plain_path.write_bytes(plain_bytes)
    print(f"Decrypted: {encrypted_path} → {plain_path}")


def decrypt_to_memory(encrypted_path: Path) -> str:
    """
    Decrypt an encrypted file and return contents as a string.
    NO plain file is created — decryption happens in memory only.
    Used by main.py and new_alertcomp.py at runtime.
    """
    if not encrypted_path.exists():
        return None  # caller falls back to plain file if it exists

    key = get_master_key()
    f = Fernet(key)

    encrypted_bytes = encrypted_path.read_bytes()
    try:
        plain_bytes = f.decrypt(encrypted_bytes)
    except Exception:
        raise SystemExit(
            "ERROR: Decryption failed. Wrong master key or corrupted file.\n"
            "Make sure ENV_MASTER_KEY matches the key used to encrypt."
        )

    return plain_bytes.decode("utf-8")


def load_env_from_encrypted() -> bool:
    """
    Decrypt .env.encrypted into memory and inject into os.environ.
    Returns True if loaded from encrypted file, False if fell back to plain .env.
    Call this BEFORE load_dotenv() in main.py and new_alertcomp.py.
    """
    content = decrypt_to_memory(ENV_ENCRYPTED)
    if content is None:
        return False  # no encrypted file — caller uses plain .env normally

    # Parse the .env content and inject into os.environ
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)

    return True


def load_password_from_encrypted() -> str | None:
    """
    Decrypt password.txt.encrypted into memory and return password string.
    Returns None if no encrypted password file exists.
    """
    content = decrypt_to_memory(PASSWORD_ENCRYPTED)
    if content is None:
        return None
    return content.strip()

def get_env(key: str, env_prefix: str = "") -> str:
    if env_prefix:
        val = os.environ.get(f"{env_prefix}_{key}", "")
        if val:
            return val
    return os.environ.get(key, "")
    
def _get_env_prefix() -> str:
    for i, arg in enumerate(sys.argv):
        if arg == "--env" and i + 1 < len(sys.argv):
            return sys.argv[i + 1].upper().strip()
        if arg.startswith("--env="):
            return arg.split("=", 1)[1].upper().strip()
    return ""
