"""Selection and persistence records for the fortune experience."""
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import random

from app.foods import FOOD_ITEMS, get_food_kind, get_food_name
from app.fortune_cards import (
    CARD_GUARDIANS, CHORONG_EGG_CARD, CHORONG_EGG_LINES, EGG_CHANCE_DAY, EGG_CHANCE_NIGHT,
    EGG_NIGHT_HOURS, GUARDIAN_LINES_FINAL, GUARDIAN_TAGS_FINAL, TAROT_CARDS, TarotCard,
)
from app.i18n import get_member_display_name, t

CARDS = {card.key: card for card in (*TAROT_CARDS, CHORONG_EGG_CARD)}
FOODS = {food["id"]: food for food in FOOD_ITEMS}
VERSION = 1


@dataclass(frozen=True)
class Reading:
    card_id: str
    guardian_id: str
    food_id: str | None
    line_id: int

    @property
    def card(self) -> TarotCard:
        return CARDS[self.card_id]


def food_is_safe(food: dict, guardian: str) -> bool:
    return get_food_kind(food) != "alcohol" and guardian not in food.get("disliked", ())


def lucky_food(rng: random.Random, guardian: str, foods=FOOD_ITEMS) -> str | None:
    favorites, others = [], []
    for food in foods:
        if food_is_safe(food, guardian):
            bucket = favorites if food.get("universal") or guardian in food.get("favorites", ()) else others
            bucket.append(food["id"])
    preferred, fallback = (favorites, others) if rng.random() < 0.6 else (others, favorites)
    pool = preferred or fallback
    return rng.choice(sorted(pool)) if pool else None


def make_reading(rng: random.Random, last_key: str | None = None, *, egg=False) -> Reading:
    if egg:
        card_id = CHORONG_EGG_CARD.key
        guardian = "chorong"
        lines = CHORONG_EGG_LINES
    else:
        ids = sorted(card.key for card in TAROT_CARDS)
        card_id = rng.choice([key for key in ids if key != last_key] or ids)
        guardian = CARD_GUARDIANS.get(card_id) or rng.choice(sorted(GUARDIAN_LINES_FINAL))
        lines = GUARDIAN_LINES_FINAL[guardian]
    return Reading(card_id, guardian, lucky_food(rng, guardian), rng.randrange(len(lines)))


def daily_fortune(day: date, salt: str, saved: object) -> tuple[Reading, dict]:
    """Reuse valid IDs. Repair mismatched guardian or unsafe food without replacing the card."""
    stamp = day.isoformat()
    seed = hashlib.sha256(json.dumps([VERSION, stamp, salt], ensure_ascii=False).encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(seed, "big"))
    if isinstance(saved, dict) and saved.get("version") == VERSION and saved.get("date") == stamp:
        card = saved.get("card_id")
        guardian = saved.get("guardian_id")
        food_id = saved.get("food_id")
        line_id = saved.get("line_id")
        if (isinstance(card, str) and card in CARDS and card != CHORONG_EGG_CARD.key
                and isinstance(guardian, str) and guardian in GUARDIAN_LINES_FINAL
                and type(line_id) is int and 0 <= line_id < len(GUARDIAN_LINES_FINAL[guardian])):
            expected_guardian = CARD_GUARDIANS.get(card)
            if expected_guardian is not None and guardian != expected_guardian:
                guardian = expected_guardian
                line_id = line_id % len(GUARDIAN_LINES_FINAL[guardian])
            food = FOODS.get(food_id) if isinstance(food_id, str) else None
            if food is None or not food_is_safe(food, guardian):
                food_id = lucky_food(rng, guardian)
            reading = Reading(card, guardian, food_id, line_id)
            return reading, {"version": VERSION, "date": stamp, **asdict(reading)}
    reading = make_reading(rng)
    return reading, {"version": VERSION, "date": stamp, **asdict(reading)}


def egg_chance(hour: int) -> float:
    return EGG_CHANCE_NIGHT if hour in EGG_NIGHT_HOURS else EGG_CHANCE_DAY


def daily_bubble_content(reading: Reading, lang: str) -> dict[str, str]:
    """Speech-bubble fields that tell the same story as the Fortune Studio reveal.

    The header becomes the first chip next to the category + stars chip (see
    ``bubble_title``); the body carries the card title and its meaning, and the
    footer the lucky hints and the guardian. The guardian's full line stays in
    the studio: with it the decorated frames outgrow a 1080p screen at 150 %.
    """
    card = reading.card
    guardian = get_member_display_name(reading.guardian_id, lang)
    tag = GUARDIAN_TAGS_FINAL[reading.guardian_id][lang]
    hints = [card.lucky[lang]]
    food = FOODS.get(reading.food_id) if reading.food_id else None
    if food:
        hints.append(t("fortune_lucky_food", lang, food=get_food_name(food, lang)))
    hints.append(t("fortune_guardian_row", lang, name=f"{guardian} · {tag}"))
    return {
        "header": t("fortune_daily_title", lang),
        "sub_badge": f"{card.badge[lang]} {card.stars}",
        "message": f"{card.title[lang]}\n{card.message[lang]}",
        "badge_text": "\n".join(hints),
    }
