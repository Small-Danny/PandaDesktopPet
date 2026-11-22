"""notifications.py — Read-only listener for Windows 10/11 system notifications.

Uses Python's standard sqlite3 module to poll %LOCALAPPDATA%\\Microsoft\\Windows\\Notifications\\wpndatabase.db
in read-only mode (?mode=ro) with query_only=ON, avoiding any lock conflicts with the OS.
Preserves all notification lines (sender, subject, email body) without truncation.
Zero third-party dependencies.

Nothing here writes to Windows: the notification centre keeps every toast. The pet
shows one bubble per poll and keeps the last RECENT_LIMIT items in RAM only.
"""
from __future__ import annotations

import datetime
import os
import sqlite3
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path

RECENT_LIMIT = 20      # RAM drawer size; cleared when the pet exits
PREVIEW_LINES = 4      # body lines shown in the bubble


def resolve_friendly_app_name(raw_id: str) -> str:
    """Translates ugly AppX / COM IDs into clean human-friendly application names."""
    if not raw_id:
        return "Windows"
    raw_lower = raw_id.lower()
    if "outlook" in raw_lower:
        return "Outlook"
    elif "teams" in raw_lower:
        return "Teams"
    elif "line" in raw_lower:
        return "LINE"
    elif "discord" in raw_lower:
        return "Discord"
    elif "slack" in raw_lower:
        return "Slack"
    elif "telegram" in raw_lower:
        return "Telegram"
    elif "code" in raw_lower or "visualstudio" in raw_lower:
        return "VS Code"
    elif "chrome" in raw_lower:
        return "Chrome"
    elif "edge" in raw_lower:
        return "Edge"
    elif "spotify" in raw_lower:
        return "Spotify"
    elif "wechat" in raw_lower:
        return "WeChat"
    elif "gmail" in raw_lower:
        return "Gmail"

    # Fallback to last token
    token = raw_id.split("!")[-1].split(".")[-1]
    return token or "Windows"


class WindowsNotificationMonitor:
    def __init__(self) -> None:
        self.db_path = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db")
        self.last_seen_id: int | None = None
        self._init_last_id()

    def _init_last_id(self) -> None:
        if not os.path.exists(self.db_path):
            return
        try:
            uri = "file:" + self.db_path.replace("\\", "/") + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=0.5)) as con:   # closed, not just committed
                con.execute("PRAGMA query_only = ON")
                row = con.execute("SELECT max(Id) FROM Notification WHERE Type = ?", ("toast",)).fetchone()
                if row and row[0] is not None:
                    self.last_seen_id = int(row[0])
        except Exception:
            pass

    def check_new_notifications(self) -> list[dict[str, str]]:
        """Returns new toast notifications since last check, or [] if none."""
        if not os.path.exists(self.db_path):
            return []

        results: list[dict[str, str]] = []
        try:
            uri = "file:" + self.db_path.replace("\\", "/") + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=0.5)) as con:
                con.execute("PRAGMA query_only = ON")
                sql = """
                    SELECT n.Id, h.PrimaryId, n.Payload
                    FROM Notification n
                    LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
                    WHERE n.Type = ? AND (? IS NULL OR n.Id > ?)
                    ORDER BY n.Id ASC LIMIT 5
                """
                rows = con.execute(sql, ("toast", self.last_seen_id, self.last_seen_id)).fetchall()

                for nid, app_id, payload in rows:
                    if self.last_seen_id is None or nid > self.last_seen_id:
                        self.last_seen_id = nid

                    title = ""            # the bubble uses a translated "new notification"
                    body = ""
                    try:
                        if payload:
                            root = ET.fromstring(payload.decode("utf-8", errors="ignore"))
                            texts = [el.text.strip() for el in root.findall(".//text") if el.text and el.text.strip()]
                            if len(texts) > 0:
                                title = texts[0]
                            if len(texts) > 1:
                                # Clean and preserve ALL subsequent lines (sender, subject, body preview)
                                body_lines = []
                                for t in texts[1:]:
                                    for line in t.split("\n"):
                                        line = line.strip()
                                        # Skip pure divider lines (e.g. "_______" or "-------")
                                        if line and not set(line).issubset({"_", "-", "=", " "}):
                                            body_lines.append(line)
                                body = "\n".join(body_lines)
                    except Exception:
                        pass

                    app_name = resolve_friendly_app_name(app_id or "Windows")

                    results.append({
                        "id": str(nid),
                        "app": app_name,
                        "title": title,
                        "body": body,
                    })
        except Exception:
            pass

        return results


def notif_text(translate: Callable[..., str], key: str, lang: str, **kw) -> str:
    """translate(key) for the notification texts (all keys live in app/i18n.py)."""
    return translate(key, lang, **kw)


def drawer_entry(item: dict[str, str], now: datetime.datetime) -> dict[str, str]:
    """One RAM drawer row: {id, time "HH:MM:SS", app, title, body}."""
    return {"id": str(item.get("id", "")), "time": now.strftime("%H:%M:%S"),
            "app": str(item.get("app", "")), "title": str(item.get("title", "")),
            "body": str(item.get("body", ""))}


def relay_bubble(items: Sequence[dict[str, str]], lang: str, privacy: bool,
                 translate: Callable[..., str]) -> tuple[str, str]:
    """(header, text) of the single bubble for one poll: the first item, then "N more".

    Privacy mode shows only which app sent it, never the title or body.
    """
    top = items[0]
    app = top.get("app") or "Windows"
    header = translate("windows_notif_header", lang, app=app)
    if privacy:
        text = notif_text(translate, "windows_notif_privacy_msg", lang, app=app)
    else:
        title = top.get("title") or notif_text(translate, "windows_notif_default_title", lang)
        lines = [line.strip() for line in (top.get("body") or "").splitlines() if line.strip()]
        preview = "\n".join(lines[:PREVIEW_LINES]) + ("\n..." if len(lines) > PREVIEW_LINES else "")
        text = f"{title}\n{preview}" if preview else title
    if len(items) > 1:
        text += "\n" + notif_text(translate, "windows_notif_more_queued", lang, n=len(items) - 1)
    return header, text
