"""Google Drive -> Telegram media transport for CHAT07.

Supports public/shared Drive files without persisting credentials. Optional
DRIVE_BEARER_TOKEN may be injected by runtime for authenticated Drive API reads.
Never logs bearer tokens or file bytes.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass

import httpx

MAX_MEDIA_BYTES = int(os.getenv("TELEGRAM_MEDIA_MAX_BYTES", str(48 * 1024 * 1024)))
ALLOWED_MIME = {"image/jpeg", "image/png", "video/mp4"}


class MediaTransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class DriveMedia:
    file_id: str
    mime_type: str
    name: str
    data: bytes

    def as_buffer(self) -> io.BytesIO:
        buf = io.BytesIO(self.data)
        buf.name = self.name
        return buf


def _public_url(file_id: str) -> str:
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"


def _api_url(file_id: str) -> str:
    return f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"


async def fetch_drive_media(*, file_id: str, mime_type: str, name: str) -> DriveMedia:
    if mime_type not in ALLOWED_MIME:
        raise MediaTransportError(f"unsupported_mime:{mime_type}")
    if not file_id or len(file_id) < 10:
        raise MediaTransportError("invalid_file_id")

    token = os.getenv("DRIVE_BEARER_TOKEN", "").strip()
    url = _api_url(file_id) if token else _public_url(file_id)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    timeout = httpx.Timeout(20.0, connect=6.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_MEDIA_BYTES:
                        raise MediaTransportError("media_too_large")
                    chunks.append(chunk)
    except MediaTransportError:
        raise
    except Exception as exc:
        raise MediaTransportError(type(exc).__name__) from exc

    data = b"".join(chunks)
    if not data:
        raise MediaTransportError("empty_media")
    if content_type.startswith("text/html"):
        raise MediaTransportError("drive_returned_html_not_media")
    return DriveMedia(file_id=file_id, mime_type=mime_type, name=name, data=data)
