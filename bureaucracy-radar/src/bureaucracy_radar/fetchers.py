from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


@dataclass
class FetchResult:
    url: str
    raw_bytes: bytes
    text: str
    content_hash: str


def _build_request(url: str) -> Request:
    user_agent = os.getenv(
        "BUREAUCRACY_RADAR_USER_AGENT",
        "Mozilla/5.0 (compatible; BureaucracyRadar/0.1)",
    )
    return Request(url, headers={"User-Agent": user_agent})


def fetch_url(url: str, timeout: int = 30) -> FetchResult:
    request = _build_request(url)
    with urlopen(request, timeout=timeout) as response:
        raw_bytes = response.read()

    text = extract_text(raw_bytes, url)
    content_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    return FetchResult(url=url, raw_bytes=raw_bytes, text=text, content_hash=content_hash)


def extract_text(raw_bytes: bytes, url: str) -> str:
    lowered = url.lower()
    if lowered.endswith(".pdf"):
        return "PDF extraction not implemented in this first scaffold."

    html = raw_bytes.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.extract()

    text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = [line for line in lines if line]
    return "\n".join(cleaned)


def save_raw_snapshot(base_dir: Path, source_id: str, raw_bytes: bytes, suffix: str = ".bin") -> Path:
    source_dir = base_dir / source_id
    source_dir.mkdir(parents=True, exist_ok=True)
    file_path = source_dir / f"latest{suffix}"
    file_path.write_bytes(raw_bytes)
    return file_path
