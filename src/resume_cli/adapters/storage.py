"""Non-overwriting, complete JSON output committed with a hard link."""

import os
import tempfile
from pathlib import Path

from resume_cli.domain.errors import ResumeError


def check_output_path(path: Path) -> None:
    # lexists also rejects dangling symlinks, which must never be replaced.
    if os.path.lexists(path):
        raise ResumeError("OUTPUT_EXISTS", f"目标已存在，请选择新文件名：{path}", 6)
    if not path.parent.is_dir():
        raise ResumeError("OUTPUT_DIRECTORY_INVALID", f"输出目录不存在：{path.parent}", 6)
    if not os.access(path.parent, os.W_OK):
        raise ResumeError("OUTPUT_UNWRITABLE", f"输出目录不可写：{path.parent}", 6)


def save_json(path: Path, content: str) -> None:
    check_output_path(path)
    temporary: str | None = None
    try:
        # Write privately in the same filesystem, then publish via an exclusive hard link.
        # Unlike os.replace(), this cannot overwrite a target created during the write.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".resume-cli-", delete=False
        ) as stream:
            temporary = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    except FileExistsError as exc:
        raise ResumeError("OUTPUT_EXISTS", f"目标已存在，请选择新文件名：{path}", 6) from exc
    except OSError as exc:
        raise ResumeError(
            "OUTPUT_WRITE_FAILED", "保存失败，请检查磁盘空间、权限及文件系统硬链接支持。", 6
        ) from exc
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
