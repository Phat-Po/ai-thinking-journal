"""Lark webhook output plugin — POST interactive card to group webhook."""

from __future__ import annotations

import json
import sys
import urllib.request

from aij.outputs.base import JournalEntry, OutputPlugin


class LarkWebhookOutput(OutputPlugin):
    name = "lark_webhook"
    display_name = "Lark Webhook (group-only)"

    def __init__(self):
        self._webhook_url = ""

    def deliver(self, entry: JournalEntry) -> bool:
        if not self._webhook_url:
            print("Warning: lark_webhook webhook_url not configured", file=sys.stderr)
            return False

        # Truncate body for card display
        body_text = entry.body[:2000]
        if len(entry.body) > 2000:
            body_text += "\n\n...(truncated)"

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": entry.title,
                    },
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": body_text,
                    },
                ],
            },
        }

        payload = json.dumps(card).encode("utf-8")
        req = urllib.request.Request(
            self._webhook_url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            if result.get("code", -1) != 0:
                print("Warning: Lark webhook returned: %s" % result, file=sys.stderr)
                return False
            print("Lark webhook: sent to group")
            return True
        except Exception as exc:
            print("Warning: Lark webhook failed: %s" % exc, file=sys.stderr)
            return False

    def configure(self, config: dict) -> None:
        self._webhook_url = config.get("webhook_url", "")
