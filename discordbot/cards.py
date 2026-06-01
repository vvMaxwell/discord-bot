from __future__ import annotations

from io import BytesIO
from pathlib import Path
from time import time

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps

from discordbot.deadlock import DeadlockHeroInfo, DeadlockHeroStat, DeadlockPlayer


CARD_WIDTH = 1100
CARD_HEIGHT = 830
BACKGROUND = "#17161d"
PANEL = "#23212b"
PANEL_ALT = "#2a2734"
ACCENT = "#f0ad2c"
TEXT = "#f8f7fb"
MUTED = "#beb8cd"
PILL = "#121017"
OUTLINE = "#3a3447"
SHADOW = "#0d0b12"
HERO_HEADER = "#353142"
HERO_PANEL = "#2d2939"


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text

    trimmed = text
    while trimmed and draw.textlength(trimmed + "...", font=font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + "...") if trimmed else text


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def _vertical_gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    width, height = size
    top_rgb = tuple(int(top[i : i + 2], 16) for i in (1, 3, 5))
    bottom_rgb = tuple(int(bottom[i : i + 2], 16) for i in (1, 3, 5))
    image = Image.new("RGBA", size)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(
            int(top_rgb[i] + (bottom_rgb[i] - top_rgb[i]) * ratio)
            for i in range(3)
        ) + (255,)
        ImageDraw.Draw(image).line((0, y, width, y), fill=color)
    return image


def _draw_panel(
    base: Image.Image,
    box: tuple[int, int, int, int],
    *,
    radius: int,
    fill: str,
    outline: str | None = None,
    shadow_offset: int = 8,
) -> None:
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(
        (x0 + shadow_offset, y0 + shadow_offset, x1 + shadow_offset, y1 + shadow_offset),
        radius=radius,
        fill=SHADOW,
    )
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1 if outline else 0)


async def _fetch_image(url: str | None) -> Image.Image | None:
    if not url:
        return None

    timeout = aiohttp.ClientTimeout(total=10)
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as response:
                if response.status >= 400:
                    return None
                data = await response.read()
    except Exception:
        return None

    try:
        image = Image.open(BytesIO(data)).convert("RGBA")
    except Exception:
        return None
    return image


def _paste_cover(base: Image.Image, image: Image.Image, box: tuple[int, int, int, int], radius: int) -> None:
    x0, y0, x1, y1 = box
    width = x1 - x0
    height = y1 - y0
    fitted = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
    mask = _rounded_mask((width, height), radius)
    base.paste(fitted, (x0, y0), mask)


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    label: str,
    value: str,
    label_font: ImageFont.ImageFont,
    value_font: ImageFont.ImageFont,
) -> int:
    height = 46
    draw.rounded_rectangle(
        (x, y, x + width, y + height),
        radius=18,
        fill=PILL,
        outline="#342e3f",
        width=1,
    )
    label_width = draw.textlength(f"{label}:", font=label_font)
    draw.text((x + 16, y + 11), f"{label}:", font=label_font, fill=MUTED)
    draw.text((x + 24 + label_width, y + 9), value, font=value_font, fill=TEXT)
    return height


def _draw_banner(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    text: str,
    font: ImageFont.ImageFont,
) -> None:
    draw.rounded_rectangle(
        (x, y, x + width, y + 38),
        radius=19,
        fill="#302b3d",
        outline="#433d53",
        width=1,
    )
    draw.text((x + 18, y + 7), text, font=font, fill=TEXT)


def _relative_time_text(timestamp: int | None) -> str:
    if not timestamp:
        return "Unknown"

    delta = max(0, int(time()) - int(timestamp))
    if delta < 60:
        return "just now"
    if delta < 3600:
        minutes = delta // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if delta < 86400:
        hours = delta // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if delta < 604800:
        days = delta // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"
    weeks = delta // 604800
    return f"{weeks} week{'s' if weeks != 1 else ''} ago"


async def render_deadlock_profile_card(
    player: DeadlockPlayer,
    rank_name: str,
    internal_rating: str,
    top_heroes: list[DeadlockHeroStat],
    hero_info: dict[int, DeadlockHeroInfo],
    rem_path: Path,
    cache_updated_ts: int | None,
) -> BytesIO:
    card = _vertical_gradient((CARD_WIDTH, CARD_HEIGHT), "#1a1821", BACKGROUND)
    draw = ImageDraw.Draw(card)

    title_font = _load_font(40, bold=True)
    heading_font = _load_font(22, bold=True)
    body_font = _load_font(22)
    small_font = _load_font(18)
    value_font = _load_font(20, bold=True)

    _draw_panel(
        card,
        (24, 24, CARD_WIDTH - 24, CARD_HEIGHT - 24),
        radius=30,
        fill=PANEL,
        outline=OUTLINE,
        shadow_offset=10,
    )
    draw.text((56, 54), f"Deadlock Profile: {player.personaname}", font=title_font, fill=TEXT)

    avatar = await _fetch_image(player.avatarfull)
    if avatar is not None:
        _paste_cover(card, avatar, (CARD_WIDTH - 260, 52, CARD_WIDTH - 100, 212), radius=24)

    detail_labels = [
        ("Account ID", str(player.account_id)),
        ("Country", player.countrycode or "Unknown"),
        ("Profile Cache Updated", _relative_time_text(cache_updated_ts)),
    ]
    x_positions = [56, 292, 528]
    for (label, value), x in zip(detail_labels, x_positions, strict=False):
        draw.text((x, 132), label, font=heading_font, fill=TEXT)
        draw.text((x, 164), value, font=body_font, fill=TEXT)

    draw.text((56, 232), "Rank Snapshot", font=heading_font, fill=TEXT)
    draw.text((56, 264), f"Rank: {rank_name}", font=body_font, fill=TEXT)
    draw.text((56, 297), f"Internal Rating: {internal_rating}", font=body_font, fill=TEXT)

    _draw_banner(draw, 56, 332, 278, "Top Heroes by Matches", small_font)

    panel_top = 384
    panel_width = 308
    panel_height = 312
    gap = 20
    rem_image = None
    if rem_path.exists():
        try:
            rem_image = Image.open(rem_path).convert("RGBA")
        except Exception:
            rem_image = None

    for index, stat in enumerate(top_heroes[:3]):
        x = 56 + index * (panel_width + gap)
        y = panel_top
        _draw_panel(
            card,
            (x, y, x + panel_width, y + panel_height),
            radius=26,
            fill=HERO_PANEL,
            outline="#3d374b",
            shadow_offset=6,
        )
        draw.rounded_rectangle(
            (x + 14, y + 14, x + panel_width - 14, y + 78),
            radius=20,
            fill=HERO_HEADER,
        )

        hero = hero_info.get(stat.hero_id)
        hero_name = hero.name if hero else f"Hero {stat.hero_id}"
        title = _fit_text(draw, hero_name, heading_font, panel_width - 110)
        draw.text((x + 28, y + 30), title, font=heading_font, fill=TEXT)

        hero_icon = await _fetch_image(hero.icon_small if hero else None)
        icon_box = (x + panel_width - 90, y + 16, x + panel_width - 26, y + 80)
        if hero_icon is not None:
            _paste_cover(card, hero_icon, icon_box, radius=18)
        else:
            draw.rounded_rectangle(icon_box, radius=18, fill="#3b3648")
            initials = hero_name[:2].upper()
            initials_width = draw.textlength(initials, font=small_font)
            draw.text(
                (icon_box[0] + ((icon_box[2] - icon_box[0] - initials_width) / 2), icon_box[1] + 22),
                initials,
                font=small_font,
                fill=TEXT,
            )

        kda_value = f"{int(stat.kills or 0)}/{int(stat.deaths or 0)}/{int(stat.assists or 0)}"
        win_rate = "0.00"
        if stat.matches_played:
            win_rate = f"{stat.wins / stat.matches_played:.2f}"

        _draw_pill(draw, x + 24, y + 108, panel_width - 48, "Matches", str(stat.matches_played), small_font, value_font)
        _draw_pill(draw, x + 24, y + 178, panel_width - 48, "Win Rate", win_rate, small_font, value_font)
        _draw_pill(draw, x + 24, y + 248, panel_width - 48, "KDA", kda_value, small_font, value_font)

    if rem_image is not None:
        rem_thumb = ImageOps.contain(rem_image, (60, 60), method=Image.Resampling.LANCZOS)
        rem_x = 56
        rem_y = CARD_HEIGHT - 110
        card.paste(rem_thumb, (rem_x, rem_y), rem_thumb)

    output = BytesIO()
    card.save(output, format="PNG")
    output.seek(0)
    return output
