"""Headless regression tests for the 2026-11-16 integration (no Tk roots)."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from app.sprites import SpriteLibrary, MemberSprites, directional_action
from app.action_frames import load_exact_action, xmas_head_factor, XMAS_HEAD_WIDTHS, FESTIVAL_FACE_WIDTHS
from app.action_frames import XMAS_REFERENCE_HEAD_WIDTH
from tests.visual_helpers import white_face_width
from app.main import PandaPet
from app.cameo_view import CameoActorWindow
from app.standby import PandaStandbyOverlay, walk_feet_point, _prepare_action_pil, _measure_member_scale
from app.group_celebration import guest_frame_slots
from app import dome_stage as dome

ROOT = Path(__file__).resolve().parents[1]

class Photo:
    def __init__(self, image, **kw): self.im = image
    def width(self): return self.im.width
    def height(self): return self.im.height

def dome_fixture(W,H,k,scene):
    ov=PandaStandbyOverlay.__new__(PandaStandbyOverlay);ov.scene=scene;ov.sw=W;ov.sh=H;ov.k=k;ov.win=None
    ov.sprite_px=max(96,min(round(192*k),int(H*.22)));lib=SpriteLibrary(ROOT,display_px=ov.sprite_px);ov._library=lib;ov.pandas=[]
    for m in dome.DOME_STAGE_MEMBERS:
        acts=(dome.DOME_BASEBALL_ACTION,) if scene==dome.DOME_BASEBALL_SCENE else (dome.EUNJI_DOME_CONCERT_OUTFITS if m=="eunji" else (dome.DOME_FLANK_CHEER_ACTION,))
        info={};scale=_measure_member_scale(lib,m)
        for act in acts:
            spec=lib.registry.resolve(m,act);ims,anchor=_prepare_action_pil(lib,spec,scale)
            info[act]={"frames":[Photo(im) for im in ims],"anchor":anchor,"alpha_bboxes":tuple(im.getchannel("A").getbbox() for im in ims)}
        ov.pandas.append({"key":m,"actions":info,"pw":round(ov.sprite_px*296/256),"ph":ov.sprite_px})
    with patch("app.standby.ImageTk.PhotoImage",side_effect=Photo):ov._fit_dome_scene_actions_to_width()
    sizes={}
    for p in ov.pandas:
        act=next(iter(p["actions"]));info=p["actions"][act];f0=info["frames"][0];fw,fh=f0.width(),f0.height()
        if fw*5>W-round(64*k):fw=max(48,max(b[2]-b[0] for b in info["alpha_bboxes"] if b)+max(4,round(6*k)))
        sizes[p["key"]]=(fw,fh)
    slots=(dome.dome_baseball_standby_slots if scene==dome.DOME_BASEBALL_SCENE else dome.eunji_dome_standby_slots)(W,H,sizes,ui_scale_factor=k)
    draws=[]
    for p in ov.pandas:
        act=next(iter(p["actions"]));cx,fy=slots[p["key"]];photo,x,y,bb=ov._dome_action_draw_spec(p,act,2,cx,fy);draws.append((p["key"],photo.im,x,y,bb))
    return ov,slots,draws

class Wave2IntegrationTests(unittest.TestCase):
    def test_incremental_preparation_yields_after_each_frame_and_reuses_complete_cache(self):
        from app.standby import _iter_prepare_action_pil, PREPARED_ACTIONS
        from app.sprite_polish import polish_frame
        lib = SpriteLibrary(ROOT, display_px=192, polish=True)
        spec = lib.registry.resolve("eunji", "dome_concert_white_dress")
        scale = _measure_member_scale(lib, "eunji")
        PREPARED_ACTIONS.clear()
        with patch("app.sprite_polish.polish_frame", wraps=polish_frame) as polished:
            steps = _iter_prepare_action_pil(lib, spec, scale)
            for count in range(1, len(spec.frames) + 1):
                self.assertIsNone(next(steps))
                self.assertEqual(polished.call_count, count)
            with self.assertRaises(StopIteration) as done:
                next(steps)
            frames, feet = done.exception.value
            self.assertEqual(len(frames), len(spec.frames))
            cached = _iter_prepare_action_pil(lib, spec, scale)
            with self.assertRaises(StopIteration) as hit:
                next(cached)
            self.assertEqual(polished.call_count, len(spec.frames))
            self.assertEqual(hit.exception.value[1], feet)
            self.assertEqual([im.tobytes() for im in hit.exception.value[0]], [im.tobytes() for im in frames])
            desktop = load_exact_action(lib, "eunji", spec.action)
            self.assertIsNotNone(desktop)
            self.assertEqual(polished.call_count, len(spec.frames))
            self.assertEqual([im.tobytes() for im in desktop.frames], [im.tobytes() for im in frames])

    def test_approved_bomi_basic_animations_do_not_fallback(self):
        lib = SpriteLibrary(ROOT)
        for action in ("idle", "cheer", "sleep", "walk"):
            spec = lib.registry.resolve("bomi", action)
            actual, frames = lib.cache.load_animation(spec)
            self.assertEqual(actual.asset_id, "bomi." + action)
            self.assertEqual(len(frames), 4)

    def test_bomi_directional_pixels_anchor_and_no_transpose(self):
        lib = SpriteLibrary(ROOT, polish=False)
        exact = load_exact_action(lib, "bomi", "walk_left")
        with patch("app.sprites.ImageTk.PhotoImage", side_effect=Photo):
            spr = lib.load_member("bomi", None)
        with patch.object(Image.Image, "transpose", side_effect=AssertionError("Bomi must not mirror")):
            for action in ("walk", "walk_left"):
                frames = spr.flipped(action)
                self.assertEqual(frames[0].im.tobytes(), exact.frames[0].tobytes())
            for action in ("walk_v2_01", "walk_v3_02", "walk_v4_04"):
                static = [Photo(Image.new("RGBA", (222, 192), (20, 30, 40, 255)))]
                spr.frames[action] = static
                self.assertEqual(directional_action("bomi", action, -1), action)
                self.assertIs(spr.get(action, -1), static)
                self.assertIs(spr.flipped(action), static)
            self.assertIs(spr.get("idle", -1), spr.frames["idle"])
        self.assertEqual(exact.frames[0].size, (222, 192))
        self.assertEqual(spr.offset("walk", -1), exact.offset)
        self.assertAlmostEqual(spr.frame_ms("walk", -1, 140), 140)
        base_feet = walk_feet_point(192)
        self.assertEqual(exact.offset, (0, 0))
        self.assertEqual(lib.registry.resolve("bomi", "walk_left").canvas, (256, 256))
        self.assertEqual(lib.registry.resolve("bomi", "walk_left").anchor, (128, 244))

    def test_step_walk_keeps_left_and_right_speed_and_arrival_consistent(self):
        from app.engine.contracts import ActorState
        from app.platform.win32 import WorkArea
        pet=PandaPet.__new__(PandaPet)
        pet.coord=SimpleNamespace(actor_state=ActorState.WALK)
        pet.sprites = SimpleNamespace(display_px=192)
        pet.char_key="bomi";pet.x=1000;pet.y=300;pet.width=222;pet.height=192
        pet.active_bubble=None;pet.settings={};pet.target_roam_x=None
        pet.desktop=SimpleNamespace(work_area_for_point=lambda *args:WorkArea(0,0,4000,1200))
        pet._place_pet=Mock();pet._set_ambient=Mock()
        pet._visual_action=lambda:"walk_left" if pet.direction<0 else None
        pet._action_frames=lambda *args:([object()],180,(-20,-80))
        pet.direction=1;pet.step_walk();self.assertEqual(pet.x,1007)
        pet.direction=-1;pet.step_walk();self.assertEqual(pet.x,998)
        self.assertEqual(7/140,9/180)
        # The target determines the new direction before computing its cadence.
        pet.direction=1;pet.target_roam_x=990;pet.step_walk()
        self.assertEqual(pet.x,990);self.assertIsNone(pet.target_roam_x)
        pet._set_ambient.assert_called_with("idle")

    def test_celebrate_together_expands_host_before_real_guest_layout(self):
        import re
        from app.engine.coordinator import StateCoordinator
        from app.platform.win32 import WorkArea

        class Window:
            def __init__(self,*args,**kwargs):self.rect=(900,300,222,192)
            def geometry(self,value):
                w,h,x,y=map(int,re.fullmatch(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)",value).groups())
                self.rect=(x,y,w,h)
            def winfo_x(self):return self.rect[0]
            def winfo_y(self):return self.rect[1]
            def winfo_width(self):return self.rect[2]
            def winfo_height(self):return self.rect[3]
            def winfo_viewable(self):return False  # This geometry-only double has no mapped surface.
            def __getattr__(self,name):return Mock()

        lib=SpriteLibrary(ROOT)
        for action in ("festival_lunar_ny","festival_mid_autumn","festival_christmas","special_birthday"):
            for member in dome.DOME_STAGE_MEMBERS:
                with self.subTest(action=action,member=member):
                    pet=PandaPet.__new__(PandaPet)
                    pet.coord=StateCoordinator(member=member);pet.char_key=member;pet.sprites=lib
                    pet.x=900;pet.y=300;pet.width=222;pet.height=192
                    pet.root=Window();pet.window=Window();pet.canvas=Mock();pet.image=1
                    pet.dragging=False;pet.face_override=1;pet.frame_idx=0
                    pet._frame_pad=(0,0,0,0);pet._shown_action=None;pet._shown_member=member
                    pet._action_cache={};pet._action_pil_cache={}
                    pet._close_group_celebration=Mock();pet.record_activity=Mock()
                    pet._pointer_over_pet_now=lambda:False
                    pet._on_group_celebration_done=Mock();pet._lift_bubble=Mock()
                    pet.desktop=SimpleNamespace(work_area_for_point=lambda *args:WorkArea(0,0,2200,1200))
                    with patch("app.main.ImageTk.PhotoImage",side_effect=Photo), \
                         patch("app.group_celebration.SYNC_BUDGET_S",60.0), \
                         patch("app.group_celebration.tk.Toplevel",side_effect=Window), \
                         patch("app.group_celebration.tk.Canvas",side_effect=lambda *args,**kw:Mock()):
                        # Real submit, visual refresh, sync_frame_box and real
                        # GroupCelebration. Only Tk surfaces are replaced.
                        pet.celebrate_together(host_action=action,guest_action=action)
                    self.assertEqual(pet.coord.action,action)
                    self.assertGreater(pet.window.winfo_width(),222)
                    self.assertGreater(pet.window.winfo_height(),192)
                    party=pet.group_celebration;self.assertIsNotNone(party)
                    self.assertEqual(party.members_shown,4)
                    host=(pet.window.winfo_x(),pet.window.winfo_x()+pet.window.winfo_width())
                    boxes=[host]
                    for win,*_ in party.windows:
                        boxes.append((win.winfo_x(),win.winfo_x()+win.winfo_width()))
                    boxes.sort()
                    for left,right in zip(boxes,boxes[1:]):self.assertGreaterEqual(right[0]-left[1],12)

    def test_main_routes_left_walk_to_exact_action_and_expansion(self):
        pet = PandaPet.__new__(PandaPet)
        pet.dragging=False; pet.char_key="bomi"; pet.direction=-1
        from app.engine.contracts import ActorState
        pet.coord=SimpleNamespace(action=None,actor_state=ActorState.WALK); pet._active_festival_costume=lambda:None
        pet._action_frames=Mock(return_value=([Photo(Image.new("RGBA", (280,280)))],180,(-30,-90)))
        self.assertEqual(pet._visual_action(), "walk_left")
        pet._active_festival_costume=lambda:"festival_lunar_ny"
        self.assertEqual(pet._visual_action(), "walk_left")
        self.assertEqual(pet._visual_facing("walk_left"), 1)
        pet.frames={"walk": [object()]}; pet.frame_idx=0
        self.assertIs(pet.current_frame(),pet._action_frames.return_value[0][0])
        with patch.object(Image.Image,"transpose",side_effect=AssertionError("mirror")):
            pet._flipped_action_frames("bomi", "walk")
        pet._action_frames.assert_called_with("bomi", "walk_left")

    def test_cameo_left_walk_expands_window_and_offsets_origin(self):
        left = Photo(Image.new("RGBA",(280,280)))
        spr = MemberSprites("bomi",{"idle":[Photo(Image.new("RGBA",(222,192)))],"walk":[object()],"walk_left":[left]},"registry",offsets={"walk_left":(-29,-89)},durations={"walk_left":180})
        actor=CameoActorWindow.__new__(CameoActorWindow); actor.sprites=spr
        actor.canvas=Mock(); actor.win=Mock(); actor.image=1; actor._shown=True; actor._alpha=1
        actor.w, actor.h = 222, 192
        actor._photo = actor._geometry = None
        actor.render(SimpleNamespace(action="walk",facing=-1,x=100,y=200,alpha=1),200)
        actor.canvas.itemconfigure.assert_called_with(1,image=left)
        actor.win.geometry.assert_called_with("280x280+71+111")

    def test_standby_cached_bomi_reuses_full_directional_loader_and_offsets(self):
        ov=PandaStandbyOverlay.__new__(PandaStandbyOverlay);ov.win=object()
        from app.standby import _prepare_member_pil, clear_standby_caches
        clear_standby_caches(); self.addCleanup(clear_standby_caches)
        producer=SpriteLibrary(ROOT,polish=False)
        prepared,_=_prepare_member_pil(producer,"bomi")
        lib=SpriteLibrary(ROOT,polish=False)
        with patch.object(lib,"load_member_pil",side_effect=AssertionError("must use prepared Bomi")), \
                patch("app.standby.ImageTk.PhotoImage",side_effect=Photo):
            cached=ov._member_sprites(lib,"bomi")
        self.assertEqual(cached.get("walk",-1)[0].im.tobytes(),prepared["walk_left"][0].tobytes())
        self.assertEqual(cached.offset("walk",-1),(0,0))
        self.assertAlmostEqual(cached.frame_ms("walk",-1,140),140)
        self.assertIn("idle",cached.frames)
        ov.pandas=[{"pw":222,"walk":[object()],"flipped_walk":[object()],"left_walk_offset":(-29,-89),"left_walk_ms":180,"img_item":1}]
        ov.px=100;ov.py=200;ov.gap=20;ov.p_dir=-1;ov.p_frame_idx=0;ov.canvas=Mock()
        ov._restore_parade_layout()
        ov.canvas.coords.assert_called_with(1,71,111)
        ov.canvas.itemconfigure.assert_called_with(1,image=ov.pandas[0]["flipped_walk"][0])

    def test_concert_and_front_faces_share_actual_pixel_reference(self):
        from app.visual_calibration import FACE_WIDTHS
        for px in (192,240):
            lib=SpriteLibrary(ROOT,display_px=px,polish=True)
            for member in dome.DOME_STAGE_MEMBERS:
                for action in ("special_birthday","dome_baseball_cheer","festival_new_year","daily_greeting","musical_pose"):
                    with self.subTest(px=px,member=member,action=action):
                        loaded=load_exact_action(lib,member,action)
                        expected=(108 if action.startswith("musical_") else 111 if member=="eunji" and action=="dome_baseball_cheer" else 114)*px/192
                        self.assertAlmostEqual(white_face_width(loaded.frames[0]),expected,delta=6*px/192)
            widths=[]
            for action in dome.EUNJI_DOME_CONCERT_OUTFITS:
                loaded=load_exact_action(lib,"eunji",action)
                widths.append(white_face_width(loaded.frames[0]))
            self.assertLessEqual(max(widths)-min(widths),5*px/192)
            for width in widths:self.assertAlmostEqual(width,112.5*px/192,delta=5*px/192)

    def test_chorong_baseball_f3_preserves_face_and_feet_without_tall_torso(self):
        lib=SpriteLibrary(ROOT,polish=False)
        loaded=load_exact_action(lib,"chorong","dome_baseball_cheer")
        one,three=loaded.frames[0],loaded.frames[2]
        a,b=one.getchannel("A").getbbox(),three.getchannel("A").getbbox()
        self.assertAlmostEqual(white_face_width(one),white_face_width(three),delta=3)
        self.assertEqual(a[3],b[3])
        self.assertAlmostEqual(a[3]-a[1],b[3]-b[1],delta=3)

    def test_xmas_head_calibration_keeps_expanded_canvas_and_floor(self):
        lib=SpriteLibrary(ROOT,polish=False)
        for name,head in XMAS_HEAD_WIDTHS.items():
            action="xmas_special_v6/"+name;member=name.split("_")[0]
            spec=lib.registry.resolve(None,action);rec=lib.registry._record(spec.frames[0])
            equal=lib._equal_scale(member,lib._load_registry(member))
            factor=xmas_head_factor(lib.registry,spec,equal)
            self.assertAlmostEqual(head*rec["normalization_scale"]*factor*equal,XMAS_REFERENCE_HEAD_WIDTH)
            loaded=load_exact_action(lib,member,action)
            normalized=lib.cache.load_animation(spec)[1][0]
            scale=lib._equal_scale(member,lib._load_registry(member))*192/256*factor
            self.assertEqual(loaded.frames[0].size,(round(normalized.width*scale),round(normalized.height*scale)))
            self.assertEqual(loaded.offset[1]+round(244*scale),walk_feet_point(192)[1])
            self.assertIsNotNone(loaded.frames[0].getchannel("A").getbbox())

    def test_holiday_faces_measured_on_rendered_pixels_and_standby_match(self):
        lib=SpriteLibrary(ROOT,polish=True)
        for action in FESTIVAL_FACE_WIDTHS:
            widths=[]
            for member in dome.DOME_STAGE_MEMBERS:
                spec=lib.registry.resolve(member,action)
                actual,source=lib.cache.load_animation(spec)
                # Independently probe each face contour below its ears/hat.
                # New Year needs manually isolated face landmarks because the
                # contiguous alpha silhouette includes the fur hood/earmuffs.
                def span(im,scale):
                    probes={
                        "festival_lunar_ny":(210,200,230,200,220),
                        "festival_mid_autumn":(230,220,240,230,230),
                        "festival_christmas":(210,210,230,210,230),
                        "festival_lantern":(220,220,230,220,230),
                    }
                    idx=dome.DOME_STAGE_MEMBERS.index(member)
                    if action=="festival_new_year":
                        # Measured face widths inside hood/muffs; scale the
                        # isolated landmark region, never the full white run.
                        return round((160,154,160,172,163)[idx]*scale)
                    y=round(probes[action][idx]*scale);x=round(192*scale)
                    left=right=x
                    while left>0 and im.getpixel((left-1,y))[3]>128:left-=1
                    while right<im.width and im.getpixel((right,y))[3]>128:right+=1
                    return right-left
                loaded=load_exact_action(lib,member,action)
                scale=loaded.frames[0].width/spec.canvas[0]
                widths.append(white_face_width(loaded.frames[0]))
                self.assertAlmostEqual(widths[-1],114,delta=6)
                prepared,anchor=_prepare_action_pil(lib,spec,_measure_member_scale(lib,member))
                self.assertEqual([im.tobytes() for im in prepared],[im.tobytes() for im in loaded.frames])
                self.assertEqual(tuple(loaded.offset[i]+anchor[i] for i in (0,1)),walk_feet_point(192))
                for im in loaded.frames:
                    box=im.getchannel("A").getbbox()
                    self.assertGreater(box[0],0);self.assertGreater(box[1],0)
                    self.assertLess(box[2],im.width);self.assertLess(box[3],im.height)
            self.assertLessEqual(max(widths)-min(widths),8)

    def test_wrong_member_art_is_not_in_public_runtime_and_jajang_uses_exact_art(self):
        import json
        from app.daily_actions import FOOD_MEMBER_ANIMATIONS
        from tools.runtime_manifest import runtime_files
        from tests.test_food_prop_mapping import FoodActor
        names=("bomi_camp_sugar_puppy","bomi_chef_jajang_bowl","eunji_sing_handheld_mic",
               "eunji_sing_vintage_mic","eunji_sit_listen_music","eunji_sleep_duvet")
        registry=json.loads((ROOT/"work/asset_registry.json").read_text(encoding="utf-8"))
        published=set(runtime_files(ROOT))
        for name in names:
            key="shared/situational_all_v2/"+name
            # 2026-11-22: the Chorong art was renamed to chorong_*; the wrong-member name must
            # either be gone or stay blocked.
            if key in registry["files"]:
                self.assertEqual(registry["files"][key]["review_status"],"blocked")
                self.assertFalse(registry["files"][key]["runtime_ok"])
            self.assertNotIn("work/characters/"+key+".png",published)
        self.assertNotIn(("bomi","jajangmyeon"),FOOD_MEMBER_ANIMATIONS)
        actor=FoodActor({"feed_jajangmyeon","situational_v3/bomi_eat_jajang_bowl"})
        actor.char_key="bomi"
        PandaPet.feed(actor,"jajangmyeon")
        self.assertEqual(actor.requested,["feed_jajangmyeon"])

    def test_all_280_food_routes_in_memory_with_real_approved_action_names(self):
        from tests.test_food_prop_mapping import FoodActor
        from app.foods import FOOD_ITEMS
        lib=SpriteLibrary(ROOT)
        for member in dome.DOME_STAGE_MEMBERS:
            actions=set(lib.registry.actions(member))
            for food in FOOD_ITEMS:
                actor=FoodActor(actions);actor.char_key=member
                PandaPet.feed(actor,food["id"])
                for action in actor.requested:self.assertIn(action,actions)

    def test_document_languages_scene_counts_and_no_encoding_damage(self):
        import json
        for name in ("README.md","ASSETS-LICENSE.md"):
            payload=(ROOT/name).read_bytes();self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))
            text=payload.decode("utf-8")
            for label in ("\u7e41\u9ad4\u4e2d\u6587","\ud55c\uad6d\uc5b4","English"):self.assertIn(label,text)
            self.assertNotIn("???",text);self.assertNotIn("Eunji?s",text);self.assertNotIn("members?",text)
        text=(ROOT/"README.md").read_text(encoding="utf-8")
        from app.standby import SCENES, load_wallpapers
        total = len(SCENES) + len(load_wallpapers(ROOT))
        for label in (f"{total} 個待機畫面", f"대기 화면 {total}개", f"{total} standby views"):
            self.assertIn(label, text)
        quotes=json.loads((ROOT/"work/quotes.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(map(len,quotes.values())),309)
        self.assertEqual(quotes["eunji"][-1]["en"],"I want to be someone you need. I won't let you regret liking me.")

    def test_nine_reapprovals_are_exact_bytes_and_manifest_is_covered(self):
        import hashlib,json
        policy=json.loads((ROOT/"work/asset_review_policy.json").read_text(encoding="utf-8"))
        registry=json.loads((ROOT/"work/asset_registry.json").read_text(encoding="utf-8"))
        records=policy["file_reapproval_history"]["20261116_bomi"]["files"]
        self.assertEqual(len(records),9)
        for name,record in records.items():
            digest=hashlib.sha256((ROOT/"work/characters"/name).read_bytes()).hexdigest()
            self.assertEqual(digest,record["sha256"]);self.assertEqual(digest,policy["approved"][name])
            self.assertEqual(digest,registry["files"][name.removesuffix(".png")]["sha256"])
        manifest=json.loads((ROOT/"work/characters/bomi/manifest.json").read_text(encoding="utf-8"))
        for action in ("idle","cheer","sleep","walk"):
            self.assertEqual(len(manifest["frames"][action]),4)

    def test_variable_guest_canvases_never_overlap_host_or_each_other(self):
        extents=[(-100,430),(-25,250),(-80,360),(-10,230)]
        slots=guest_frame_slots((900,1200),(0,2200),extents)
        boxes=[(900,1200)]
        for slot,(dx,w) in zip(slots,extents):
            if slot is not None:
                boxes.append((slot+dx,slot+dx+w))
        self.assertEqual(len(boxes),5)
        boxes.sort()
        self.assertGreaterEqual(boxes[0][0],0);self.assertLessEqual(boxes[-1][1],2200)
        for a,b in zip(boxes,boxes[1:]):self.assertLessEqual(a[1]+12,b[0])
        self.assertEqual(guest_frame_slots((0,200),(0,300),[(0,400)]),[None])

    def test_real_dome_assets_fit_all_resolutions_and_dpis(self):
        for w,h in ((1280,720),(1920,1080),(2560,1440)):
            for k in (1,2):
                for scene in (dome.DOME_EUNJI_SCENE,dome.DOME_BASEBALL_SCENE):
                    ov,slots,draws=dome_fixture(w,h,k,scene)
                    boxes=[entry[4] for entry in draws]
                    for i,a in enumerate(boxes):
                        self.assertGreaterEqual(a[0],0);self.assertLessEqual(a[2],w)
                        self.assertGreaterEqual(a[1],80*k);self.assertLessEqual(a[3],h)
                        for b in boxes[i+1:]:self.assertTrue(a[2]<=b[0] or b[2]<=a[0] or a[3]<=b[1] or b[3]<=a[1])
                    if scene==dome.DOME_BASEBALL_SCENE:
                        bw,bh=dome.available_dome_bubble_space(boxes,(0,0,w,h),gap=18*k,top_safe_y=80*k)
                        self.assertGreaterEqual(bh,100*k)
                        for lang in ("zh_TW","ko","en"):
                            bubble=dome.render_dome_bubble_pil(2,lang,dpi_scale=k,max_width=min(560*k,bw),max_height=bh)
                            self.assertGreaterEqual(bubble.height,60*k)
                            x,y,bw,bh_=dome.compute_dome_bubble_rect(boxes,bubble.size,(0,0,w,h),gap=18*k,top_safe_y=80*k)
                            self.assertGreaterEqual(y,80*k)
                            self.assertLessEqual(y+bh_,min(b[1] for b in boxes)-18*k)

    def test_dome_pitcher_and_spotlight_lines_across_sizes_and_dpi(self):
        for w,h in ((1280,720),(1920,1080),(2560,1440)):
            for k in (1,2):
                # Real standby caps the base height to 22% of screen height.
                sprite=max(96,min(round(192*k),int(h*.22)))
                sizes={m:(round(sprite*1.2),round(sprite*1.35)) for m in dome.DOME_STAGE_MEMBERS}
                for scene,ny in (("baseball",.7708),("eunji",.73)):
                    fn=dome.dome_baseball_standby_slots if scene=="baseball" else dome.eunji_dome_standby_slots
                    slots=fn(w,h,sizes,ui_scale_factor=k)
                    self.assertAlmostEqual(slots["eunji"][1],dome.map_cover_point(.5,ny,w,h)[1],delta=1)
                    boxes=[(cx-sizes[m][0]/2,fy-sizes[m][1],cx+sizes[m][0]/2,fy) for m,(cx,fy) in slots.items()]
                    for i,a in enumerate(boxes):
                        self.assertGreaterEqual(a[1],80*k)
                        for b in boxes[i+1:]:self.assertTrue(a[2]<=b[0] or b[2]<=a[0] or a[3]<=b[1] or b[3]<=a[1])
                    if scene=="eunji":
                        for m in dome.EUNJI_FLANK_MEMBERS:self.assertGreaterEqual(slots[m][1]-slots["eunji"][1],36*k)
                    else:
                        for cx,fy in slots.values():self.assertAlmostEqual(fy,dome.map_cover_point(.5,.7708,w,h)[1],delta=1)
                        _,bh=dome.available_dome_bubble_space(boxes,(0,0,w,h),gap=16*k,top_safe_y=80*k)
                        self.assertGreaterEqual(bh,64*k)

if __name__ == "__main__": unittest.main()
