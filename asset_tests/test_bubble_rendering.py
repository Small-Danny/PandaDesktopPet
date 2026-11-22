"""Windows/Tk integration checks confined to bubble windows, never PandaPet data."""
from __future__ import annotations

import tkinter as tk
import unittest
from pathlib import Path

from app.bubble import KawaiiSpeechBubble, emoji_icon
from app.bubble_layout import is_emoji, iter_clusters
from app.platform.win32 import WorkArea


class BubbleRenderingTests(unittest.TestCase):
    def test_semantic_emoji_families_replace_sparkle(self):
        families = (
            ("❤", "💛🥰"), ("☕", "🍻🥛🧊"), ("🍲", "🍜🥗🥣🥓🥚"),
            ("🎂", "🍨"), ("💬", "📬📌"), ("🌸", "🌿🌱🎍"),
            ("☀", ("☀️", "⚡")), ("🎮", ()), ("🔥", "🌶"),
            ("🎉", "🎆🎁🏆👑🎄"), ("😋", "😆🥺😫💪🥋🥊⚽"),
        )
        sparkle = emoji_icon("✨", 72).tobytes()
        shapes = set()
        for representative, variants in families:
            with self.subTest(representative=representative):
                image = emoji_icon(representative, 72)
                self.assertIsNotNone(image.getbbox())
                pixels = image.tobytes()
                self.assertNotEqual(pixels, sparkle)
                self.assertNotIn(pixels, shapes)
                shapes.add(pixels)
                for variant in variants:
                    self.assertEqual(emoji_icon(variant, 72).tobytes(), pixels, variant)

    def test_rating_stars_show_lit_and_unlit(self):
        """Fortune ratings like ★★★★☆ must not collapse into five identical sparkles."""
        lit, unlit = emoji_icon("★", 72), emoji_icon("☆", 72)
        sparkle = emoji_icon("✨", 72).tobytes()
        self.assertTrue(is_emoji("★") and is_emoji("☆"))
        self.assertEqual(list(iter_clusters("★★☆")), ["★", "★", "☆"])
        self.assertNotIn(lit.tobytes(), (sparkle, unlit.tobytes()))
        self.assertNotEqual(unlit.tobytes(), sparkle)
        self.assertEqual(emoji_icon("⭐", 72).tobytes(), lit.tobytes())

    def test_negative_monitor_work_area_and_absolute_placement(self):
        from unittest.mock import Mock
        area = WorkArea(-1600,-200,0,860)
        desktop = Mock()
        desktop.work_area_for_point.return_value = area
        card = self.bubble(target_x=-1400,target_y=500,desktop=desktop)
        x,y = card.target_position
        self.assertGreaterEqual(x,area.left+10)
        self.assertGreaterEqual(y,area.top+10)
        self.assertLessEqual(x+card.width,area.right-10)
        self.assertLessEqual(y+card.height,area.bottom-10)
        desktop.position_without_activation.assert_called_once()
        self.assertEqual(desktop.position_without_activation.call_args.args[1:],(x,y))

    def test_below_sprite_uses_supplied_height_and_taskbar_bound(self):
        from unittest.mock import Mock
        area = WorkArea(0,40,1280,1000)
        desktop = Mock()
        desktop.work_area_for_point.return_value = area
        card = self.bubble(target_y=60,sprite_h=256,desktop=desktop)
        self.assertEqual(card.target_position[1],60+256+8)
        self.assertLessEqual(card.target_position[1]+card.height,area.bottom-10)

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def bubble(self, **kwargs):
        params = dict(parent=self.root,target_x=400,target_y=700,sprite_w=192,
                      header="普美 Bomi / 보미",message="一起休息一下吧！ Let's rest. 함께 쉬어요 🐼💖",
                      duration_ms=60000)
        params.update(kwargs)
        card = KawaiiSpeechBubble(**params)
        self.addCleanup(card.dismiss)
        self.root.update()
        return card

    def test_multiline_header_and_chips_do_not_overlap(self):
        card = self.bubble(header="普美的很長很長通知標題 Bomi notification "*4,
                           sub_badge="🐶 狗狗狂熱｜🏕️ 露營愛好者｜🚙 露營車車長｜" + "長標籤"*30,
                           icon_path=Path("work/characters/bomi/idle_01.png"))
        boxes = card.chip_boxes
        for i,(x,y,w,h,_) in enumerate(boxes):
            self.assertGreaterEqual(x,24)
            self.assertLessEqual(x+w,card.width-24)
            for ox,oy,ow,oh,_ in boxes[i+1:]:
                self.assertFalse(x<ox+ow and x+w>ox and y<oy+oh and y+h>oy)
        msg_window = next(item for item in card.canvas.find_all()
                          if card.canvas.type(item)=="window")
        self.assertGreater(card.canvas.coords(msg_window)[1], max(y+h for _,y,_,h,_ in boxes))

    def test_emoji_clusters_are_images_not_font_glyphs(self):
        card = self.bubble(message="家庭 👨‍👩‍👧‍👦 比讚 👍🏽 國旗 🇰🇷 喝水 ☕ 愛心 ❤️")
        self.assertGreater(len(card._emoji_images),3)
        for surface in (card.canvas,card.message_canvas):
            for item in surface.find_all():
                if surface.type(item)=="text":
                    self.assertFalse(any(is_emoji(c) for c in iter_clusters(surface.itemcget(item,"text"))))

    def test_long_notice_scrolls_and_stays_inside_screen(self):
        card = self.bubble(message=("長通知 English 한국어 🐼 https://example.test/" + "abc"*60 + "\n")*24)
        self.assertTrue(card.scrollable)
        self.assertGreaterEqual(card.window.winfo_x(),0)
        self.assertGreaterEqual(card.window.winfo_y(),0)
        self.assertLessEqual(card.window.winfo_x()+card.width,card.window.winfo_screenwidth())
        self.assertLessEqual(card.window.winfo_y()+card.height,card.window.winfo_screenheight())
        card.message_canvas.yview_moveto(1.0)
        self.root.update()
        self.assertAlmostEqual(card.message_canvas.yview()[1],1.0,places=2)

    def test_dismiss_invokes_callback_once_and_keeps_parent(self):
        calls = []
        card = self.bubble(on_close=lambda:calls.append(1))
        card.dismiss()
        card.dismiss()
        self.assertEqual(calls,[1])
        self.assertTrue(self.root.winfo_exists())

    def test_missing_icon_is_optional(self):
        card = self.bubble(icon_path=Path("does-not-exist.png"))
        self.assertIsNone(card.icon_thumb)
        self.assertTrue(card.window.winfo_exists())


if __name__=="__main__":
    unittest.main()
