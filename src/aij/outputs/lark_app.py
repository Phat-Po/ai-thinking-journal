"""Lark custom app output plugin — tenant token + image upload + DM.

Uses --as bot identity (rule: lark-send-as-bot.md).
Auth: POST /open-apis/auth/v3/tenant_access_token/internal/
Send: POST /open-apis/im/v1/messages?receive_id_type=open_id
Image: POST /open-apis/im/v1/images → image_key → send image message
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Optional

from aij.outputs.base import JournalEntry, OutputPlugin

LARK_BASE = "https://open.larksuite.com/open-apis"
TOKEN_CACHE = Path.home() / ".aij" / ".token_cache.json"


class LarkAppOutput(OutputPlugin):
    name = "lark_app"
    display_name = "Lark Custom App (DM + images)"

    def __init__(self):
        self._app_id = ""
        self._app_secret = ""
        self._user_id = ""

    def _get_tenant_token(self) -> str:
        """Get tenant access token, with disk cache."""
        # Check cache
        if TOKEN_CACHE.exists():
            try:
                cache = json.loads(TOKEN_CACHE.read_text())
                if cache.get("expire", 0) > time.time() + 60:
                    return cache["token"]
            except Exception:
                pass

        if not self._app_id or not self._app_secret:
            raise RuntimeError("Lark app_id and app_secret not configured")

        url = LARK_BASE + "/auth/v3/tenant_access_token/internal/"
        payload = json.dumps({
            "app_id": self._app_id,
            "app_secret": self._app_secret,
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        token = data.get("tenant_access_token", "")
        expire = data.get("expire", 7200)

        if not token:
            raise RuntimeError("Failed to get Lark tenant token: %s" % data)

        # Cache to disk
        TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE.write_text(json.dumps({
            "token": token,
            "expire": int(time.time()) + expire,
        }))
        os.chmod(TOKEN_CACHE, 0o600)

        return token

    def _send_message(self, token: str, msg_type: str, content: str) -> bool:
        """Send a message to the configured user via Lark API."""
        url = LARK_BASE + "/im/v1/messages?receive_id_type=open_id"
        payload = json.dumps({
            "receive_id": self._user_id,
            "msg_type": msg_type,
            "content": content,
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("code", -1) != 0:
            return False
        return True

    def _upload_image(self, token: str, image_path: Path) -> Optional[str]:
        """Upload image to Lark, return image_key."""
        url = LARK_BASE + "/im/v1/images"

        # Multipart form data boundary
        boundary = "----aijboundary"
        body_parts = []

        # image_type field
        body_parts.append("--%s\r\n" % boundary)
        body_parts.append('Content-Disposition: form-data; name="image_type"\r\n\r\n')
        body_parts.append("message\r\n")

        # image file field
        body_parts.append("--%s\r\n" % boundary)
        body_parts.append('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % image_path.name)
        body_parts.append("Content-Type: image/png\r\n\r\n")

        # Join text parts
        text_part = "".join(body_parts).encode("utf-8")
        # Read image bytes
        image_data = image_path.read_bytes()
        # Closing boundary
        end_part = ("\r\n--%s--\r\n" % boundary).encode("utf-8")

        body = text_part + image_data + end_part

        req = urllib.request.Request(
            url, data=body,
            headers={
                "Content-Type": "multipart/form-data; boundary=%s" % boundary,
                "Authorization": "Bearer " + token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("code", -1) != 0:
            return None
        return result.get("data", {}).get("image_key")

    def deliver(self, entry: JournalEntry) -> bool:
        if not self._user_id:
            return False

        token = self._get_tenant_token()

        # Send text summary
        body_text = entry.body[:2000]
        if len(entry.body) > 2000:
            body_text += "\n\n...(truncated)"

        text_content = json.dumps({
            "text": "**%s**\n\n%s" % (entry.title, body_text),
        })
        text_ok = self._send_message(token, "text", text_content)

        # Send image if available
        if entry.image_path and entry.image_path.exists():
            image_key = self._upload_image(token, entry.image_path)
            if image_key:
                img_content = json.dumps({"image_key": image_key})
                self._send_message(token, "image", img_content)

        return text_ok

    def configure(self, config: dict) -> None:
        if "app_id" in config:
            self._app_id = config["app_id"]
        self._app_secret = config.get("app_secret") or os.getenv("LARK_APP_SECRET", "")
        if "user_id" in config:
            self._user_id = config["user_id"]
