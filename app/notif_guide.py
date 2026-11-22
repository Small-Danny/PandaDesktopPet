"""notif_guide.py - "How do I get LINE / Telegram / Teams / Outlook / Gmail onto the pet?" help window.

The pet reads the Windows notification centre (app/notifications.py), so an app only reaches
the pet when it sends real Windows notifications. This window explains, per app, where that
switch is and how to keep the corner of the screen quiet (banners off, notification centre on).
App menus move between versions, so the texts name the setting rather than promise a path.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from app.platform.win32 import WindowsDesktopAdapter, WorkArea, ui_scale

# lang -> [(heading, body)]
GUIDE: dict[str, list[tuple[str, str]]] = {
    "zh_TW": [
        ("🐾 原理：桌寵讀的是 Windows 通知中心",
         "App 必須發出「Windows 通知」，桌寵才收得到；不需要另外接 API。\n"
         "快速測試：用手機傳訊息給自己，按 Win + N 打開通知中心。訊息有出現在那裡，桌寵就會念出來；"
         "沒出現，就是那個 App 自己的通知設定要調整（見下方）。"),
        ("🔕 只讓桌寵播報，右下角不跳橫幅",
         "全部 App：設定 › 系統 › 通知 → 開啟「請勿打擾」。通知照樣進通知中心，由桌寵念出。"
         "放在「設定優先通知」清單裡的 App 仍會跳橫幅，不想要可以從清單移除。\n"
         "只換某些 App：設定 › 系統 › 通知 → 點該 App → 關閉「顯示通知橫幅」，保留「在通知中心顯示通知」。\n"
         "注意：不要關掉該 App 的通知總開關，關掉後桌寵也收不到。"),
        ("💬 LINE",
         "LINE 電腦版 › 設定 › 通知 → 開啟通知。LINE 要保持登入，縮到工作列右下角即可，不要登出或完全關閉。"),
        ("✈️ Telegram",
         "Telegram Desktop › 設定 › 通知 → 開啟「使用 Windows 通知」（Use Windows notifications / 系統通知）。"
         "沒開時 Telegram 會用自己的小視窗，桌寵收不到。"),
        ("👥 Teams",
         "Teams › 設定 › 通知和活動 → 「通知樣式」選擇「Windows」。選「Teams 內建」時通知不會進 Windows 通知中心。"),
        ("📧 Outlook",
         "新版 Outlook：設定 › 一般 › 通知 → 開啟桌面通知，Outlook 要保持開啟。\n"
         "傳統版 Outlook：檔案 › 選項 › 郵件 → 勾選「顯示桌面通知」。"),
        ("✉️ Gmail",
         "Gmail 沒有電腦版 App，有兩種做法：\n"
         "① 在 Chrome 或 Edge 開著 Gmail：Gmail 設定 › 一般 › 「桌面通知」→ 開啟新郵件通知，並允許瀏覽器顯示通知。\n"
         "② 把 Gmail 帳號加進 Outlook，由 Outlook 發通知。"),
        ("🔒 直播或分享畫面時",
         "打開「直播隱私遮罩」：桌寵只說「某某 App 有新通知」，不顯示標題與內文。通知只存在記憶體，不寫入硬碟。"),
    ],
    "ko": [
        ("🐾 원리: 펫은 Windows 알림 센터를 읽어요",
         "앱이 'Windows 알림'을 보내야 펫이 받을 수 있어요. 따로 API를 연결할 필요는 없어요.\n"
         "빠른 테스트: 휴대폰으로 자신에게 메시지를 보내고 Win + N으로 알림 센터를 여세요. "
         "거기에 보이면 펫이 알려 주고, 안 보이면 그 앱의 알림 설정을 바꿔야 해요(아래 참고)."),
        ("🔕 펫만 알려 주고 배너는 끄기",
         "모든 앱: 설정 › 시스템 › 알림 → '방해 금지' 켜기. 알림은 알림 센터로 가고 펫이 읽어 줘요. "
         "'우선 순위 알림' 목록의 앱은 배너가 계속 뜨니, 원하지 않으면 목록에서 빼세요.\n"
         "일부 앱만: 설정 › 시스템 › 알림 → 앱 선택 → '알림 배너 표시' 끄기, '알림 센터에 알림 표시'는 유지.\n"
         "주의: 앱의 알림 자체를 끄면 펫도 받을 수 없어요."),
        ("💬 LINE",
         "LINE PC › 설정 › 알림 → 알림 켜기. 로그인 상태로 작업 표시줄에 최소화해 두세요(로그아웃·완전 종료 X)."),
        ("✈️ Telegram",
         "Telegram Desktop › 설정 › 알림 → 'Windows 알림 사용'(Use Windows notifications) 켜기. "
         "꺼져 있으면 Telegram 자체 팝업을 써서 펫이 받을 수 없어요."),
        ("👥 Teams",
         "Teams › 설정 › 알림 및 활동 → '알림 스타일'을 'Windows'로. 'Teams 기본 제공'이면 Windows 알림 센터로 가지 않아요."),
        ("📧 Outlook",
         "새 Outlook: 설정 › 일반 › 알림 → 데스크톱 알림 켜기, Outlook은 켜 두세요.\n"
         "클래식 Outlook: 파일 › 옵션 › 메일 → '데스크톱 알림 표시' 체크."),
        ("✉️ Gmail",
         "Gmail은 PC 앱이 없어서 두 가지 방법이 있어요:\n"
         "① Chrome·Edge에서 Gmail을 열어 두기: Gmail 설정 › 기본설정 › '데스크톱 알림' → 새 메일 알림 켜기, 브라우저 알림 허용.\n"
         "② Gmail 계정을 Outlook에 추가해 Outlook이 알림을 보내게 하기."),
        ("🔒 방송·화면 공유할 때",
         "'방송 프라이버시 마스크'를 켜면 펫은 '앱에 새 알림'만 말하고 제목·내용은 숨겨요. 알림은 메모리에만 있고 디스크에 저장되지 않아요."),
    ],
    "en": [
        ("🐾 How it works: the pet reads the Windows notification center",
         "An app reaches the pet only when it sends real Windows notifications - no extra API is needed.\n"
         "Quick test: message yourself from your phone and press Win + N. If the message is in the notification "
         "center, the pet reads it out; if not, that app's own notification setting needs changing (see below)."),
        ("🔕 Only the pet, no banners in the corner",
         "All apps: Settings › System › Notifications → turn on 'Do not disturb'. Alerts still reach the notification "
         "center and the pet reads them. Apps on the 'Set priority notifications' list still show banners; remove them "
         "there if you like.\n"
         "Some apps only: Settings › System › Notifications → pick the app → turn off 'Show notification banners', keep "
         "'Show notifications in notification center'.\n"
         "Note: don't switch the app's notifications off completely - then the pet gets nothing either."),
        ("💬 LINE",
         "LINE for PC › Settings › Notifications → turn notifications on. Stay logged in and minimise it to the tray "
         "(don't log out or quit)."),
        ("✈️ Telegram",
         "Telegram Desktop › Settings › Notifications → turn on 'Use Windows notifications'. When it is off, "
         "Telegram uses its own pop-ups and the pet never sees them."),
        ("👥 Teams",
         "Teams › Settings › Notifications and activity → set 'Notification style' to 'Windows'. With 'Teams built-in' "
         "nothing reaches the Windows notification center."),
        ("📧 Outlook",
         "New Outlook: Settings › General › Notifications → turn desktop notifications on and keep Outlook open.\n"
         "Classic Outlook: File › Options › Mail → tick 'Display a Desktop Alert'."),
        ("✉️ Gmail",
         "Gmail has no PC app, so either:\n"
         "① keep Gmail open in Chrome or Edge: Gmail Settings › General › 'Desktop notifications' → new mail "
         "notifications on, and allow the browser to show notifications; or\n"
         "② add the Gmail account to Outlook and let Outlook notify you."),
        ("🔒 When streaming or sharing your screen",
         "Turn on the stream privacy mask: the pet only says '<App> has a new notification' and hides the title and "
         "text. Notifications stay in memory only and are never written to disk."),
    ],
}
TITLE = {"zh_TW": "📖 各 App 通知設定指南", "ko": "📖 앱별 알림 설정 가이드", "en": "📖 App Notification Setup Guide"}
CLOSE = {"zh_TW": "知道了", "ko": "확인", "en": "Got it"}


class NotifGuideWindow:
    """Scrollable read-only guide; one per settings panel."""

    W, H = 540, 580

    def __init__(self, parent: tk.Misc, lang: str = "zh_TW", theme: Optional[dict] = None,
                 font_family: str = "Microsoft JhengHei UI", near: Optional[tuple[int, int]] = None,
                 on_close: Optional[Callable[[], None]] = None) -> None:
        self.lang = lang if lang in GUIDE else "zh_TW"
        theme = theme or {"primary": "#d6457f", "accent": "#b03366", "soft_bg": "#fff5f9", "badge_border": "#f3b6cd"}
        self.on_close = on_close
        self.closed = False
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.title(TITLE[self.lang])
        self.window.attributes("-topmost", True)
        self.window.configure(bg=theme["soft_bg"])
        raw_x, raw_y = near if near else (200, 120)
        k = ui_scale(self.window)
        desktop = WindowsDesktopAdapter(
            fallback_bounds=lambda: WorkArea(
                0, 0, max(640, int(self.window.winfo_screenwidth())), max(480, int(self.window.winfo_screenheight()))
            )
        )
        try:
            area = desktop.work_area_for_point(int(raw_x), int(raw_y))
        except Exception:
            area = WorkArea(0, 0, max(640, int(self.window.winfo_screenwidth())), max(480, int(self.window.winfo_screenheight())))
        avail_w = max(280, area.width - 24)
        avail_h = max(300, area.height - 48)
        self.w = max(280, min(avail_w, round(self.W * k)))
        self.h = max(300, min(avail_h, round(self.H * k)))
        cx, cy = area.clamp(int(raw_x), int(raw_y), self.w, self.h)
        self.last_clamped_pos = (cx, cy)
        self.window.geometry(f"{self.w}x{self.h}+{max(0, cx)}+{max(0, cy)}")
        try:
            self.window.update_idletasks()
            frame = self.window.wm_frame()
            hwnd = (int(frame, 16) if frame.startswith("0x") else int(frame)) if frame else int(self.window.winfo_id())
            if not desktop.position_without_activation(hwnd, cx, cy) and cx >= 0 and cy >= 0:
                self.window.geometry(f"{self.w}x{self.h}+{cx}+{cy}")
        except Exception:
            pass
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", lambda _e: self.close())

        tk.Label(self.window, text=TITLE[self.lang], font=(font_family, 12, "bold"), fg=theme["primary"],
                 bg=theme["soft_bg"]).pack(anchor="w", padx=16, pady=(12, 6))
        # Packed before the text so the button always keeps its row at the bottom.
        tk.Button(self.window, text=CLOSE[self.lang], font=(font_family, 9, "bold"), fg="#ffffff",
                  bg=theme["primary"], activebackground=theme["accent"], relief="flat", padx=18,
                  command=self.close).pack(side="bottom", pady=10)
        body = tk.Frame(self.window, bg="#ffffff", highlightthickness=1, highlightbackground=theme["badge_border"])
        body.pack(fill="both", expand=True, padx=14)
        bar = tk.Scrollbar(body)
        bar.pack(side="right", fill="y")
        self.text = tk.Text(body, wrap="word", relief="flat", bg="#ffffff", fg="#444444", padx=12, pady=10,
                            font=(font_family, 9), spacing1=2, spacing3=2, yscrollcommand=bar.set, cursor="arrow")
        self.text.pack(side="left", fill="both", expand=True)
        bar.configure(command=self.text.yview)
        self.text.tag_configure("h", font=(font_family, 10, "bold"), foreground=theme["accent"],
                                spacing1=12, spacing3=3)
        for heading, para in GUIDE[self.lang]:
            self.text.insert("end", heading + "\n", "h")
            self.text.insert("end", para + "\n")
        self.text.configure(state="disabled")
        self.window.deiconify()
        self.window.lift()

    def lift(self) -> None:
        if not self.closed:
            self.window.deiconify()
            self.window.lift()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        if self.on_close is not None:
            self.on_close()
