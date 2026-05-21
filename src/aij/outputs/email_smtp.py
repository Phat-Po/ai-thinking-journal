"""Email SMTP output plugin — sends journal entries via SMTP with STARTTLS."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from aij.outputs.base import JournalEntry, OutputPlugin


class EmailOutput(OutputPlugin):
    name = "email"
    display_name = "Email (SMTP)"

    def __init__(self):
        self._smtp_host = "smtp.gmail.com"
        self._smtp_port = 587
        self._from_addr = ""
        self._to_addr = ""

    def deliver(self, entry: JournalEntry) -> bool:
        password = os.getenv("AIJ_EMAIL_PASSWORD", "")
        if not password:
            return False
        if not self._from_addr or not self._to_addr:
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = entry.title
        msg["From"] = self._from_addr
        msg["To"] = self._to_addr

        # Plain text version (markdown body)
        plain_text = entry.frontmatter + "\n" + entry.title + "\n\n" + entry.body
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))

        # HTML version (simple conversion)
        html_body = "<html><body>"
        html_body += "<h1>%s</h1>" % entry.title
        # Basic markdown-to-html: paragraphs and headers
        for line in entry.body.split("\n"):
            if line.startswith("### "):
                html_body += "<h3>%s</h3>" % line[4:]
            elif line.startswith("## "):
                html_body += "<h2>%s</h2>" % line[3:]
            elif line.startswith("# "):
                html_body += "<h1>%s</h1>" % line[2:]
            elif line.startswith("> "):
                html_body += "<blockquote>%s</blockquote>" % line[2:]
            elif line.startswith("- "):
                html_body += "<li>%s</li>" % line[2:]
            elif line.strip() == "---":
                html_body += "<hr>"
            elif line.strip():
                html_body += "<p>%s</p>" % line
        html_body += "</body></html>"
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self._from_addr, password)
                server.sendmail(self._from_addr, self._to_addr, msg.as_string())
            return True
        except Exception as exc:
            raise RuntimeError("Email send failed: %s" % exc)

    def configure(self, config: dict) -> None:
        if "smtp_host" in config:
            self._smtp_host = config["smtp_host"]
        if "smtp_port" in config:
            self._smtp_port = int(config["smtp_port"])
        if "from_addr" in config:
            self._from_addr = config["from_addr"]
        if "to_addr" in config:
            self._to_addr = config["to_addr"]
