"""Load configuration only when a real AI call is requested."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

from resume_cli.domain.errors import ResumeError

REQUEST_TIMEOUT = 30.0
RETRY_DELAY = 1.0
MAX_OUTPUT_TOKENS = 4096


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    model: str
    base_url: str

    @classmethod
    def load(cls) -> "Settings":
        # Only load the working directory, never walk into unrelated parents.
        try:
            file_values = dotenv_values(Path.cwd() / ".env", interpolate=False)
        except (OSError, UnicodeError) as exc:
            raise ResumeError(
                "CONFIG_UNREADABLE", "无法读取当前目录的 .env，请检查编码与权限。"
            ) from exc

        def value(name: str, default: str = "") -> str:
            return (os.environ.get(name, file_values.get(name)) or default).strip()

        api_key = value("OPENAI_API_KEY")
        model = value("OPENAI_MODEL")
        base_url = value("OPENAI_BASE_URL", "https://api.openai.com/v1")
        missing = [
            key for key, val in [("OPENAI_API_KEY", api_key), ("OPENAI_MODEL", model)] if not val
        ]
        if missing:
            raise ResumeError(
                "CONFIG_MISSING",
                f"请在环境变量或当前目录 .env 配置 {', '.join(missing)}；离线演示可使用 --mock。",
            )
        try:
            url = urlsplit(base_url)
            valid = (
                url.scheme in {"https", "http"}
                and bool(url.hostname)
                and (url.port is None or 0 < url.port < 65536)
                and not url.username
                and not url.password
                and not url.query
                and not url.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ResumeError("CONFIG_URL_INVALID", "OPENAI_BASE_URL 必须是无凭据的 HTTP(S) 端点。")
        return cls(api_key=api_key, model=model, base_url=base_url)
