"""Pipeline credentials — always load from environment, never hardcode secrets."""

from __future__ import annotations

import os
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(_ENV_FILE)


def env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default if default is not None else "")
    value = (value or "").strip()
    if required and not value:
        raise RuntimeError(
            f"Missing environment variable {name}. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return value


CHATFIRE_BASE_URL = env("CHATFIRE_BASE_URL", "https://api.chatfire.cn/v1").rstrip("/")
CHATFIRE_CHAT_MODEL = env("CHATFIRE_CHAT_MODEL", "gemini-3-flash-preview")
CHATFIRE_IMAGE_MODEL = env("CHATFIRE_IMAGE_MODEL", "gpt-image-2")

COS_BUCKET = env("COS_BUCKET", "gallery-1316658404")
COS_REGION = env("COS_REGION", "ap-shanghai")
COS_PUBLIC_BASE_URL = env("COS_PUBLIC_BASE_URL", "https://cos.onmicrosoft.cn").rstrip("/")

CHAT_API_URL = env("CHATFIRE_CHAT_URL", f"{CHATFIRE_BASE_URL}/chat/completions")
IMAGE_API_URL = env("CHATFIRE_IMAGE_URL", f"{CHATFIRE_BASE_URL}/images/generations")


def require_chatfire_key() -> str:
    return env("CHATFIRE_API_KEY", required=True)


def require_cos() -> tuple[str, str]:
    return env("COS_SECRET_ID", required=True), env("COS_SECRET_KEY", required=True)
