import io

import pytest

from bot.drive_media import DriveMedia, MediaTransportError, _api_url, _public_url
from bot.content_engine import CATEGORY_ASSET_BUCKET, select_asset


def test_drive_urls_do_not_embed_secrets():
    fid = "1Z6jgSamAwscA0ygo9BnTHKmX4AMXA8sP"
    assert fid in _public_url(fid)
    assert "usercontent.google.com" in _public_url(fid)
    assert fid in _api_url(fid)
    assert "googleapis.com/drive/v3/files" in _api_url(fid)


def test_drive_media_buffer_has_filename():
    media = DriveMedia("abc123456789", "image/jpeg", "visual.jpeg", b"abc")
    buf = media.as_buffer()
    assert isinstance(buf, io.BytesIO)
    assert buf.name == "visual.jpeg"
    assert buf.read() == b"abc"


def test_category_mapping_is_deterministic():
    assert CATEGORY_ASSET_BUCKET["security"] == "security"
    assert CATEGORY_ASSET_BUCKET["recovery"] == "recovery"
    assert CATEGORY_ASSET_BUCKET["cryptoaid"] == "brand"


def test_select_asset_uses_real_seed_map():
    asset = select_asset({"category": "security"}, {"recent_asset_ids": []})
    assert asset is not None
    assert asset["mime"] in {"image/jpeg", "image/png", "video/mp4"}
    assert len(asset["id"]) > 10
