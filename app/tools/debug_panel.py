"""Injected developer controls; no access to user files or global OS time.

The panel only talks to the pet through ``DebugBindings``. The ten original
fields stay required; everything newer is optional so older hosts still work.
"""
from __future__ import annotations

import datetime as _dt
import json
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable

REFRESH_MS = 250

TEXT = {
    "zh_TW": {
        "title": "🛠️ 熊貓開發者除錯面板",
        "sec_member": "成員與動作", "member": "成員", "switch": "切換成員",
        "action": "動作", "play": "強制播放",
        "sec_play": "播放與單幀", "pause": "⏸ 暫停", "resume": "▶ 繼續",
        "prev": "◀ 上一幀", "next": "下一幀 ▶", "release": "↺ 解除強制",
        "sec_time": "虛擬時鐘（只影響本程式的行事曆）",
        "plus_hour": "+1 小時", "plus_day": "+1 天", "minus_day": "-1 天", "real": "回到真實時間",
        "jump": "節日快速跳轉", "j_419": "4/19 週年", "j_xmas": "12/25 聖誕", "j_nye": "12/31 23:59 跨年",
        "sec_hud": "即時診斷 HUD", "hud_pause": "暫停更新", "copy": "複製 JSON",
        "restore": "關閉時自動恢復真實時間與狀態",
        "ready": "就緒", "ok": "完成", "copied": "已複製 JSON 到剪貼簿",
        "base_group": "基本", "special_group": "特殊／節慶",
    },
    "ko": {
        "title": "🛠️ 판다 개발자 디버그 패널",
        "sec_member": "멤버와 동작", "member": "멤버", "switch": "멤버 전환",
        "action": "동작", "play": "강제 재생",
        "sec_play": "재생과 프레임", "pause": "⏸ 일시정지", "resume": "▶ 계속",
        "prev": "◀ 이전 프레임", "next": "다음 프레임 ▶", "release": "↺ 강제 해제",
        "sec_time": "가상 시계 (이 앱의 캘린더에만 적용)",
        "plus_hour": "+1시간", "plus_day": "+1일", "minus_day": "-1일", "real": "실제 시간으로",
        "jump": "기념일 바로 가기", "j_419": "4/19 데뷔 기념일", "j_xmas": "12/25 크리스마스", "j_nye": "12/31 23:59 카운트다운",
        "sec_hud": "실시간 진단 HUD", "hud_pause": "갱신 일시정지", "copy": "JSON 복사",
        "restore": "닫을 때 실제 시간과 상태로 자동 복원",
        "ready": "준비됨", "ok": "완료", "copied": "JSON을 클립보드에 복사했어요",
        "base_group": "기본", "special_group": "특수/명절",
    },
    "en": {
        "title": "🛠️ Panda Developer Debug Panel",
        "sec_member": "Member & action", "member": "Member", "switch": "Switch member",
        "action": "Action", "play": "Force play",
        "sec_play": "Playback & frames", "pause": "⏸ Pause", "resume": "▶ Resume",
        "prev": "◀ Prev frame", "next": "Next frame ▶", "release": "↺ Release",
        "sec_time": "Virtual clock (this app's calendar only)",
        "plus_hour": "+1 hour", "plus_day": "+1 day", "minus_day": "-1 day", "real": "Real time",
        "jump": "Holiday jump", "j_419": "4/19 Anniversary", "j_xmas": "12/25 Christmas", "j_nye": "12/31 23:59 Countdown",
        "sec_hud": "Live diagnostics HUD", "hud_pause": "Pause updates", "copy": "Copy JSON",
        "restore": "Restore real time and state on close",
        "ready": "Ready", "ok": "OK", "copied": "JSON copied to clipboard",
        "base_group": "base", "special_group": "special/festival",
    },
}

# (text key, month, day, hour, minute, second)
HOLIDAY_JUMPS = (
    ("j_419", 4, 19, 12, 0, 0),
    ("j_xmas", 12, 25, 12, 0, 0),
    ("j_nye", 12, 31, 23, 59, 0),
)


def panel_text(lang: str) -> dict[str, str]:
    return TEXT.get(lang, TEXT["zh_TW"])


@dataclass(frozen=True)
class DebugBindings:
    snapshot: Callable[[], dict]
    members: tuple[str, ...]
    switch_member: Callable[[str], None]
    actions: Callable[[], tuple[str, ...]]
    play: Callable[[str], None]
    pause: Callable[[bool], None]
    step: Callable[[int], None]
    shift_hours: Callable[[float], None]
    reset_time: Callable[[], None]
    release: Callable[[], None]
    # Optional, newer hosts only.
    lang: str = "zh_TW"
    special_actions: Callable[[], tuple[str, ...]] | None = None
    set_time: Callable[[_dt.datetime], None] | None = None
    extra_snapshot: Callable[[], dict] | None = None
    member_label: Callable[[str], str] | None = None


def _plain(value):
    """JSON-friendly HUD values: readable times, cache in MB, tuples as lists."""
    if isinstance(value, _dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def format_snapshot(state: dict) -> dict:
    out = {}
    for key, value in state.items():
        if key == "cache_bytes":
            out["cache_mb"] = None if value is None else round(value / (1024 * 1024), 2)
        else:
            out[key] = _plain(value)
    return out


class DeveloperDebugPanel:
    def __init__(self, parent: tk.Misc, bindings: DebugBindings):
        self.bindings = bindings
        self.tx = panel_text(bindings.lang)
        self._closed = False
        self._timer = None
        self._hud_text = ""
        self._last_member = None
        self.window = tk.Toplevel(parent)
        self.window.title(self.tx["title"])
        self.window.attributes("-topmost",True)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.resizable(True, True)
        tx = self.tx
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        # 1) Member and action.
        box = ttk.LabelFrame(frame, text=tx["sec_member"], padding=8)
        box.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        box.columnconfigure(1, weight=1)
        self.member = tk.StringVar(self.window, bindings.members[0])
        ttk.Label(box, text=tx["member"]).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.member_box = ttk.Combobox(box, textvariable=self.member, values=bindings.members, state="readonly")
        self.member_box.grid(row=0, column=1, sticky="ew")
        ttk.Button(box, text=tx["switch"], command=lambda: self._call(self._switch)).grid(row=0, column=2, padx=(6, 0))
        self.action = tk.StringVar(self.window)
        ttk.Label(box, text=tx["action"]).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(6, 0))
        self.action_box = ttk.Combobox(box, textvariable=self.action, state="readonly", height=18)
        self.action_box.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        ttk.Button(box, text=tx["play"], command=lambda: self._call(self._play)).grid(
            row=1, column=2, padx=(6, 0), pady=(6, 0))

        # 2) Playback and single frames.
        box = ttk.LabelFrame(frame, text=tx["sec_play"], padding=8)
        box.grid(row=1, column=0, sticky="ew", pady=6)
        for text, callback in (
            (tx["pause"], lambda: bindings.pause(True)), (tx["resume"], lambda: bindings.pause(False)),
            (tx["prev"], lambda: bindings.step(-1)), (tx["next"], lambda: bindings.step(1)),
            (tx["release"], bindings.release),
        ):
            ttk.Button(box, text=text, command=lambda cb=callback: self._call(cb)).pack(side="left", padx=2)

        # 3) Virtual clock and holiday jumps.
        box = ttk.LabelFrame(frame, text=tx["sec_time"], padding=8)
        box.grid(row=2, column=0, sticky="ew", pady=6)
        row = ttk.Frame(box)
        row.pack(fill="x")
        for key, hours in (("plus_hour", 1), ("plus_day", 24), ("minus_day", -24)):
            ttk.Button(row, text=tx[key], command=lambda h=hours: self._call(lambda: bindings.shift_hours(h))).pack(
                side="left", padx=2)
        ttk.Button(row, text=tx["real"], command=lambda: self._call(bindings.reset_time)).pack(side="left", padx=2)
        if bindings.set_time is not None:
            row = ttk.Frame(box)
            row.pack(fill="x", pady=(6, 0))
            ttk.Label(row, text=tx["jump"]).pack(side="left", padx=(2, 8))
            for key, *when in HOLIDAY_JUMPS:
                ttk.Button(row, text=tx[key], command=lambda w=tuple(when): self._call(lambda: self.jump_to(*w))).pack(
                    side="left", padx=2)

        # 4) Live HUD.
        box = ttk.LabelFrame(frame, text=tx["sec_hud"], padding=8)
        box.grid(row=3, column=0, sticky="nsew", pady=6)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(1, weight=1)
        tools = ttk.Frame(box)
        tools.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.hud_paused = tk.BooleanVar(self.window, False)
        ttk.Checkbutton(tools, text=tx["hud_pause"], variable=self.hud_paused).pack(side="left")
        ttk.Button(tools, text=tx["copy"], command=lambda: self._call(self.copy_json, tx["copied"])).pack(side="right")
        self.hud = tk.Text(box, width=66, height=16, state="disabled", wrap="none", font=("Consolas", 9))
        self.hud.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.hud.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.hud.configure(yscrollcommand=scroll.set)
        frame.rowconfigure(3, weight=1)

        self.restore_on_close = tk.BooleanVar(self.window, True)
        ttk.Checkbutton(frame, text=tx["restore"], variable=self.restore_on_close).grid(row=4, column=0, sticky="w")
        self.status = tk.StringVar(self.window, tx["ready"])
        ttk.Label(frame, textvariable=self.status).grid(row=5, column=0, sticky="w", pady=(4, 0))
        self._refresh_actions()
        self._refresh()
        self.window.update_idletasks()
        self.window.minsize(self.window.winfo_reqwidth(), self.window.winfo_reqheight())

    # -- helpers -------------------------------------------------------------
    def _call(self, callback, done: str | None = None):
        try:
            callback()
            self.status.set(done or self.tx["ok"])
        except Exception as error:
            self.status.set(f"{type(error).__name__}: {error}")

    def place_in(self, area) -> None:
        """Keep the whole panel inside a monitor work area (left/top/right/bottom)."""
        self.window.update_idletasks()
        w = min(max(self.window.winfo_reqwidth(), self.window.winfo_width()), area.right - area.left)
        h = min(max(self.window.winfo_reqheight(), self.window.winfo_height()), area.bottom - area.top)
        x = max(area.left, min(self.window.winfo_x(), area.right - w))
        y = max(area.top, min(self.window.winfo_y(), area.bottom - h))
        self.window.geometry(f"{w}x{h}+{x}+{y}")

    def _action_values(self) -> tuple[str, ...]:
        base = tuple(self.bindings.actions())
        extra = tuple(self.bindings.special_actions()) if self.bindings.special_actions else ()
        return base + tuple(a for a in extra if a not in base)

    def _refresh_actions(self):
        actions = self._action_values()
        self.action_box.configure(values=actions)
        if self.action.get() not in actions:
            self.action.set(actions[0] if actions else "")

    def _switch(self):
        self.bindings.switch_member(self.member.get())
        self._last_member = self.member.get()
        self._refresh_actions()

    def _play(self):
        self.bindings.play(self.action.get())

    def jump_to(self, month: int, day: int, hour: int = 12, minute: int = 0, second: int = 0) -> None:
        """Jump the virtual clock to this year's (virtual) date and time."""
        now = self.bindings.snapshot().get("wall_time")
        year = now.year if isinstance(now, _dt.datetime) else _dt.datetime.now().year
        self.bindings.set_time(_dt.datetime(year, month, day, hour, minute, second))

    def snapshot_text(self) -> str:
        state = dict(self.bindings.snapshot())
        if self.bindings.extra_snapshot is not None:
            state.update(self.bindings.extra_snapshot())
        return json.dumps(format_snapshot(state), ensure_ascii=False, indent=2)

    def copy_json(self):
        self.window.clipboard_clear()
        self.window.clipboard_append(self.snapshot_text())

    def _sync_member(self, member) -> None:
        """Follow members switched elsewhere; never undo a pick the user has not applied."""
        if member == self._last_member or member not in self.bindings.members:
            return
        self._last_member = member
        self.member.set(member)
        self._refresh_actions()

    def _refresh(self):
        if self._closed:
            return
        if self._timer:   # a direct call must not leave a second polling chain behind
            self.window.after_cancel(self._timer)
            self._timer = None
        try:
            state = self.bindings.snapshot()
            self._sync_member(state.get("member"))
            if not self.hud_paused.get():
                text = self.snapshot_text()
                if text != self._hud_text:
                    self._hud_text = text
                    top = self.hud.yview()[0]
                    self.hud.configure(state="normal")
                    self.hud.delete("1.0", "end")
                    self.hud.insert("end", text)
                    self.hud.configure(state="disabled")
                    self.hud.yview_moveto(top)
        except Exception as error:
            self.status.set(f"HUD: {error}")
        self._timer = self.window.after(REFRESH_MS, self._refresh)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._timer:
            self.window.after_cancel(self._timer)
            self._timer = None
        restore = bool(self.restore_on_close.get())
        try:
            if restore:
                self.bindings.release()
        finally:
            try:
                if restore:
                    self.bindings.reset_time()
            finally:
                self.window.destroy()
