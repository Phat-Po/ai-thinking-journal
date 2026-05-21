"""OpenAI API summarizer plugin."""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from typing import Optional

from aij.summarizers.base import SummarizerPlugin

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_IMG_URL = "https://api.openai.com/v1/images/generations"


class OpenAISummarizer(SummarizerPlugin):
    name = "openai"
    display_name = "OpenAI API"

    def __init__(self, model: str = "gpt-4.1-mini", poster_model: str = "gpt-4.1",
                 image_model: str = "gpt-image-1"):
        self.model = model
        self.poster_model = poster_model
        self.image_model = image_model

    def call(self, prompt: str, *, timeout: int = 240) -> str:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment")
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }).encode("utf-8")
        req = urllib.request.Request(
            OPENAI_URL, data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()

    def call_image(self, prompt: str, *, size: str = "1024x1280",
                   quality: str = "medium") -> Optional[bytes]:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment")
        payload = json.dumps({
            "model": self.image_model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality,
        }).encode("utf-8")
        req = urllib.request.Request(
            OPENAI_IMG_URL, data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return base64.b64decode(data["data"][0]["b64_json"])

    def check_availability(self) -> bool:
        api_key = os.getenv("OPENAI_API_KEY", "")
        return bool(api_key)

    def configure(self, config: dict) -> None:
        if "model" in config:
            self.model = config["model"]
        if "poster_model" in config:
            self.poster_model = config["poster_model"]
        if "image_model" in config:
            self.image_model = config["image_model"]
