"""Safe configuration loader for contextcon-adlc (zero secrets in logs/repr)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MekoConfig:
    api_key: str
    mcp_url: str
    datapack_id: str
    datapack_name: str

    def __repr__(self) -> str:
        prefix = self.api_key[:4] + "***" if len(self.api_key) >= 4 else "***"
        return (
            f"MekoConfig(mcp_url={self.mcp_url!r}, datapack_id={self.datapack_id!r}, "
            f"datapack_name={self.datapack_name!r}, api_key={prefix}, key_len={len(self.api_key)})"
        )


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def load_config(start_dir: Path | None = None) -> MekoConfig:
    base = (start_dir or Path.cwd()).resolve()
    candidates = [
        base / ".env",
        base.parent / ".env",
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ]
    merged: dict[str, str] = {}
    for cand in reversed(candidates):
        merged.update(_parse_dotenv(cand))

    for key in ("MEKO_API_KEY", "MEKO_MCP_URL", "MEKO_DATAPACK_ID", "MEKO_DATAPACK_NAME"):
        if os.environ.get(key):
            merged[key] = os.environ[key].strip()

    api_key = merged.get("MEKO_API_KEY", "")
    mcp_url = merged.get("MEKO_MCP_URL", "https://mcp.mekodata.ai/mcp")
    datapack_id = merged.get("MEKO_DATAPACK_ID", "")
    datapack_name = merged.get("MEKO_DATAPACK_NAME", "contextcon-adlc")
    if not api_key:
        raise RuntimeError("MEKO_API_KEY not found in environment or .env")
    if not datapack_id:
        raise RuntimeError("MEKO_DATAPACK_ID not found in environment or .env")
    return MekoConfig(
        api_key=api_key,
        mcp_url=mcp_url,
        datapack_id=datapack_id,
        datapack_name=datapack_name,
    )
