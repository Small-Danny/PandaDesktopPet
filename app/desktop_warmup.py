"""Cancellable idle preparation of desktop PIL frames; never creates Tk objects."""
from app.standby import StandbyWarmupManager, _prepare_member_pil
from app.sprites import SpriteLibrary
from app.daily_actions import (
    CHRISTMAS, LANTERN, LUNAR_NY, MID_AUTUMN_FESTIVAL, NEW_YEAR, SIGNATURE_POOL, festival_on,
)
from app.engine.contracts import MEMBER_KEYS
from app.action_frames import load_exact_action, xmas_poses

# Group celebrations and their previews (all five on stage): warmed last, after today's
# own actions, so the first party at 240 px does not decode four guests on the Tk thread.
CELEBRATION_ACTIONS = (
    "special_birthday", "special_cheer_lightstick", CHRISTMAS.action,
    "musical_pose", "musical_step", "musical_swish", "musical_bow",
    NEW_YEAR.action, LUNAR_NY.action, LANTERN.action, MID_AUTUMN_FESTIVAL.action,
)


WARM_FILL_LIMIT = 0.85


def warm_budget_exhausted() -> bool:
    """True when idle warmup should stop so it does not evict what it already prepared."""
    from app.standby import PREPARED_IMAGES
    return PREPARED_IMAGES.size_bytes >= WARM_FILL_LIMIT * PREPARED_IMAGES.limit_bytes


def celebration_actions(library: SpriteLibrary, member: str) -> tuple[str, ...]:
    """Every celebration look a guest may be given, Christmas poses included."""
    return (*CELEBRATION_ACTIONS, *xmas_poses(library, member))


class DesktopWarmupManager(StandbyWarmupManager):
    def _execute_plan(self, plan: dict) -> None:
        class Cancelled(BaseException):
            pass

        def yield_frame():
            if self._yield_step(plan["gen"], plan["busy_check"], pause_s=0.002):
                raise Cancelled()

        library = SpriteLibrary(
            plan["resource_root"],
            display_px=plan["sprite_px"],
            binary_alpha=bool(plan.get("binary_alpha", True)),
            edge_refine=bool(plan.get("edge_refine", False)),
        )
        active = plan.get("active_member") or MEMBER_KEYS[0]
        members = sorted(MEMBER_KEYS, key=lambda m: m != active)
        festival = festival_on(plan["today"])
        try:
            yield_frame()
            from app.pink_context_menu import warm_context_menu_assets
            warm_context_menu_assets(root=plan["resource_root"], yield_fn=yield_frame)
            for member in members:
                yield_frame()
                _prepare_member_pil(library, member, yield_fn=yield_frame)
                self.completed_items += 1
                actions = list(SIGNATURE_POOL.get(member, ())) if member == active else []
                if festival is not None:
                    actions.insert(0, festival.action)
                for action in dict.fromkeys(actions):
                    yield_frame()
                    if load_exact_action(library, member, action, yield_fn=yield_frame) is not None:
                        self.completed_items += 1
            # Lowest priority: celebration looks for every member at this pet size.
            # Stop once the shared PREPARED budget is nearly full: at 384-480 px (192 DPI) the
            # remaining looks would only evict today's base/signature frames warmed above.
            for member in members:
                for action in celebration_actions(library, member):
                    yield_frame()
                    if warm_budget_exhausted():
                        return
                    if load_exact_action(library, member, action, yield_fn=yield_frame) is not None:
                        self.completed_items += 1
        except Cancelled:
            return
