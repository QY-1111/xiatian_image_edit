from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import json
import math
import os
import random
import re
from typing import Iterable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


BUNDLED_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "NotoSansSC-VariableFont_wght.ttf")


@dataclass(frozen=True)
class PosterOptions:
    width: int = 520
    height: int = 1136
    font_size: int = 43
    highlight_color: str = "#FFE08A"
    author_color: str = "#FFF06A"
    author_font_size: int = 27
    author_offset_x: int = 0
    author_offset_y: int = 0
    author_rotation: float = 4.0
    line_spacing: float = 1.92
    content_width: float = 0.78
    vertical_position: float = 0.51
    darkness: float = 0.48
    show_border: bool = True
    show_doodles: bool = True
    show_app_ui: bool = True
    style: str = "清新手绘"
    seed: int = 1257

    def with_seed(self, seed: int) -> "PosterOptions":
        return replace(self, seed=seed)


STYLE = {
    "清新手绘": {
        "text": (255, 255, 255, 255),
        "highlight": (255, 224, 138, 255),
        "doodle": (111, 242, 235, 255),
        "accent": (255, 242, 109, 255),
        "line": (245, 247, 245, 242),
        "gradient": ((25, 45, 52), (75, 97, 94)),
    },
    "温暖日记": {
        "text": (255, 251, 241, 255),
        "highlight": (255, 211, 139, 255),
        "doodle": (255, 189, 153, 255),
        "accent": (255, 159, 126, 255),
        "line": (255, 246, 227, 238),
        "gradient": ((65, 42, 38), (145, 102, 72)),
    },
    "极简白字": {
        "text": (255, 255, 255, 255),
        "highlight": (255, 255, 255, 255),
        "doodle": (255, 255, 255, 255),
        "accent": (255, 255, 255, 255),
        "line": (255, 255, 255, 230),
        "gradient": ((30, 32, 35), (82, 87, 92)),
    },
}


def _parse_hex_color(value: str, fallback: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Convert #RGB or #RRGGBB to RGBA; invalid input falls back safely."""
    value = (value or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return fallback
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4)) + (255,)


def _extract_copy_text(value: str) -> str:
    """Extract the copy string when an upstream node supplies a JSON payload."""
    if not isinstance(value, str):
        return str(value)

    candidate = value.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    try:
        payload = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return value

    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("text", "文案内容", "文案", "content"):
            text_value = payload.get(key)
            if isinstance(text_value, str):
                return text_value
    return value


def _draw_rotated_text(
    layer: Image.Image,
    text: str,
    font: ImageFont.ImageFont,
    fill,
    center: tuple[float, float],
    angle: float,
    stroke_width: int,
    stroke_fill,
) -> None:
    """Draw text around a stable visual center with antialiased rotation."""
    probe = ImageDraw.Draw(Image.new("L", (1, 1), 0))
    bbox = probe.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    pad = max(4, stroke_width + 4)
    patch = Image.new(
        "RGBA",
        (max(1, bbox[2] - bbox[0] + pad * 2), max(1, bbox[3] - bbox[1] + pad * 2)),
        (0, 0, 0, 0),
    )
    patch_draw = ImageDraw.Draw(patch)
    patch_draw.text(
        (pad - bbox[0], pad - bbox[1]),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
    if abs(angle) > 0.01:
        patch = patch.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    x = round(center[0] - patch.width / 2)
    y = round(center[1] - patch.height / 2)
    layer.alpha_composite(patch, (x, y))


FONT_CANDIDATES_BOLD = [
    os.environ.get("COPY_POSTER_FONT", ""),
    BUNDLED_FONT,
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyhbd.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/Dengb.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

FONT_CANDIDATES_REGULAR = [
    os.environ.get("COPY_POSTER_FONT", ""),
    BUNDLED_FONT,
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/Deng.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


@lru_cache(maxsize=64)
def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                font = ImageFont.truetype(path, size=size)
                if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(BUNDLED_FONT)):
                    variation_name = "Bold" if bold else "Regular"
                    try:
                        font.set_variation_by_name(variation_name)
                    except (AttributeError, OSError):
                        try:
                            font.set_variation_by_axes([700 if bold else 400])
                        except (AttributeError, OSError):
                            pass
                return font
            except OSError:
                continue
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGB")
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize(
        (max(target_w, round(image.width * scale)), max(target_h, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    x = (resized.width - target_w) // 2
    y = (resized.height - target_h) // 2
    return resized.crop((x, y, x + target_w, y + target_h))


def _gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    strip = Image.new("RGB", (1, height))
    px = strip.load()
    for y in range(height):
        t = y / max(1, height - 1)
        px[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
    return strip.resize((width, height))


def _prepare_background(background: Image.Image | None, size: tuple[int, int], darkness: float, palette: dict) -> Image.Image:
    if background is None:
        base = _gradient(size, *palette["gradient"])
        # A few translucent fields keep the fallback from looking mechanically flat.
        haze = Image.new("RGBA", size, (0, 0, 0, 0))
        hd = ImageDraw.Draw(haze)
        w, h = size
        hd.ellipse((-w * 0.3, h * 0.15, w * 0.9, h * 1.0), fill=(90, 190, 180, 34))
        hd.ellipse((w * 0.25, -h * 0.2, w * 1.2, h * 0.6), fill=(255, 185, 120, 25))
        base = Image.alpha_composite(base.convert("RGBA"), haze.filter(ImageFilter.GaussianBlur(w * 0.15))).convert("RGB")
    else:
        base = _cover(background, size)
        base = ImageEnhance.Contrast(base).enhance(0.92)
        base = ImageEnhance.Color(base).enhance(0.82)

    overlay = Image.new("RGBA", size, (7, 11, 13, round(255 * darkness)))
    result = Image.alpha_composite(base.convert("RGBA"), overlay)

    # Soft vignette for white type legibility near the edges.
    w, h = size
    vignette = Image.new("L", size, 0)
    vd = ImageDraw.Draw(vignette)
    margin = int(min(w, h) * 0.10)
    vd.ellipse((-margin, -margin, w + margin, h + margin), fill=90)
    vignette = Image.eval(vignette.filter(ImageFilter.GaussianBlur(min(w, h) * 0.16)), lambda p: 90 - p)
    black = Image.new("RGBA", size, (0, 0, 0, 0))
    black.putalpha(vignette)
    return Image.alpha_composite(result, black)


def _parse_runs(text: str) -> list[tuple[str, bool]]:
    """Parse [[highlight]] spans into (text, highlighted) runs."""
    runs: list[tuple[str, bool]] = []
    pos = 0
    for match in re.finditer(r"\[\[(.+?)\]\]", text):
        if match.start() > pos:
            runs.append((text[pos : match.start()], False))
        runs.append((match.group(1), True))
        pos = match.end()
    if pos < len(text):
        runs.append((text[pos:], False))
    return runs or [(text, False)]


def _char_width(draw: ImageDraw.ImageDraw, char: str, font: ImageFont.ImageFont) -> float:
    return draw.textlength(char, font=font)


def _wrap_runs(
    draw: ImageDraw.ImageDraw,
    runs: Iterable[tuple[str, bool]],
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[list[tuple[str, bool]]]:
    lines: list[list[tuple[str, bool]]] = [[]]
    widths = [0.0]
    for text, highlighted in runs:
        buffer = ""
        for char in text:
            if char == "\n":
                if buffer:
                    lines[-1].append((buffer, highlighted))
                    buffer = ""
                lines.append([])
                widths.append(0.0)
                continue
            char_width = _char_width(draw, char, font)
            if widths[-1] + char_width > max_width and (lines[-1] or buffer):
                if buffer:
                    lines[-1].append((buffer, highlighted))
                    buffer = ""
                lines.append([])
                widths.append(0.0)
            buffer += char
            widths[-1] += char_width
        if buffer:
            lines[-1].append((buffer, highlighted))
    return [line for line in lines if line]


def _line_width(draw: ImageDraw.ImageDraw, line: list[tuple[str, bool]], font: ImageFont.ImageFont) -> float:
    return sum(draw.textlength(text, font=font) for text, _ in line)


def _draw_centered_runs(
    draw: ImageDraw.ImageDraw,
    mask_draw: ImageDraw.ImageDraw,
    line: list[tuple[str, bool]],
    center_x: float,
    y: float,
    font: ImageFont.ImageFont,
    normal_color: tuple[int, int, int, int],
    highlight_color: tuple[int, int, int, int],
    stroke_width: int,
) -> tuple[float, list[tuple[float, float, float, float]]]:
    width = _line_width(draw, line, font)
    x = center_x - width / 2
    highlights = []
    for text, highlighted in line:
        fill = highlight_color if highlighted else normal_color
        draw.text(
            (x, y),
            text,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
        )
        mask_draw.text((x, y), text, font=font, fill=255, stroke_width=stroke_width, stroke_fill=255)
        run_width = draw.textlength(text, font=font)
        if highlighted:
            bbox = draw.textbbox((x, y), text, font=font, stroke_width=stroke_width)
            highlights.append(tuple(float(v) for v in bbox))
        x += run_width
    return width, highlights


def _jittered_line(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    fill: tuple[int, int, int, int],
    width: int,
    rng: random.Random,
    jitter: float = 1.8,
) -> None:
    pts = [(x + rng.uniform(-jitter, jitter), y + rng.uniform(-jitter, jitter)) for x, y in points]
    draw.line(pts, fill=fill, width=width, joint="curve")


def _rounded_hand_border(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    color: tuple[int, int, int, int],
    width: int,
    rng: random.Random,
) -> None:
    left, top, right, bottom = box
    radius = min((right - left) * 0.08, (bottom - top) * 0.06)
    def segment(start: tuple[float, float], end: tuple[float, float], count: int = 22):
        return [
            (start[0] + (end[0] - start[0]) * i / (count - 1), start[1] + (end[1] - start[1]) * i / (count - 1))
            for i in range(count)
        ]

    # The reference uses two short top strokes instead of a closed top edge.
    top_left_end = left + (right - left) * .155
    top_right_start = right - (right - left) * .145
    _jittered_line(draw, segment((left + radius, top), (top_left_end, top), 10), color, width, rng)
    draw.arc((right - radius * 2, top, right, top + radius * 2), 270, 360, fill=color, width=width)
    _jittered_line(draw, segment((top_right_start, top), (right - radius, top), 10), color, width, rng)
    _jittered_line(draw, segment((right, top + radius), (right, bottom - radius)), color, width, rng)
    draw.arc((right - radius * 2, bottom - radius * 2, right, bottom), 0, 90, fill=color, width=width)
    _jittered_line(draw, segment((right - radius, bottom), (left + radius, bottom), 40), color, width, rng)
    draw.arc((left, bottom - radius * 2, left + radius * 2, bottom), 90, 180, fill=color, width=width)
    _jittered_line(draw, segment((left, bottom - radius), (left, top + radius)), color, width, rng)
    draw.arc((left, top, left + radius * 2, top + radius * 2), 180, 270, fill=color, width=width)


def _draw_underline(draw: ImageDraw.ImageDraw, bbox: tuple[float, float, float, float], color, width: int, rng) -> None:
    left, _, right, bottom = bbox
    y = bottom + width * 1.4
    mid = (left + right) / 2
    _jittered_line(
        draw,
        [(left - width, y), (mid, y + rng.uniform(-width, width)), (right + width, y - width * 0.3)],
        color,
        width,
        rng,
        jitter=width * 0.35,
    )


def _draw_doodles(draw: ImageDraw.ImageDraw, w: int, h: int, palette: dict, rng: random.Random, scale: float) -> None:
    cyan = palette["doodle"]
    yellow = palette["accent"]
    sw = max(3, round(4 * scale))

    # Short confetti near the heading.
    _jittered_line(draw, [(w * .302, h * .246), (w * .36, h * .259)], cyan, sw, rng)
    _jittered_line(draw, [(w * .692, h * .302), (w * .735, h * .280)], cyan, sw, rng)
    _jittered_line(draw, [(w * .720, h * .302), (w * .744, h * .291)], yellow, sw, rng)

    # Eight-ray sparkle at the right side.
    cx, cy = w * .79, h * .49
    long_r, short_r = 23 * scale, 8 * scale
    for i in range(8):
        angle = math.pi * i / 4
        r0 = short_r if i % 2 else short_r * 0.7
        r1 = long_r if i % 2 == 0 else long_r * 0.72
        _jittered_line(
            draw,
            [(cx + math.cos(angle) * r0, cy + math.sin(angle) * r0),
             (cx + math.cos(angle) * r1, cy + math.sin(angle) * r1)],
            yellow,
            max(2, round(3 * scale)),
            rng,
            jitter=0.8 * scale,
        )

    # Small orbit and dot.
    ox, oy = w * .765, h * .438
    draw.ellipse((ox - 8 * scale, oy - 8 * scale, ox + 8 * scale, oy + 8 * scale), outline=yellow, width=max(2, round(3 * scale)))
    draw.ellipse((ox + 3 * scale, oy - 4 * scale, ox + 7 * scale, oy), fill=yellow)
    draw.ellipse((w * .708, h * .447, w * .723, h * .457), fill=yellow)

    # Tiny tilted phone/music glyph beside the heading.
    phone = [
        (w * .374, h * .246),
        (w * .397, h * .241),
        (w * .408, h * .271),
        (w * .384, h * .276),
    ]
    draw.polygon(phone, fill=(20, 28, 30, 235), outline=(150, 161, 158, 210))
    draw.line((w * .383, h * .250, w * .398, h * .247, w * .404, h * .265), fill=(80, 96, 96, 220), width=max(1, round(1.4 * scale)))
    draw.arc((w * .387, h * .253, w * .400, h * .265), 120, 420, fill=cyan, width=max(1, round(1.5 * scale)))


def _draw_ambient_glows(layer: Image.Image, palette: dict, scale: float) -> None:
    """Subtle floating rings visible in the supplied reference background."""
    w, h = layer.size
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    rings = [
        (.187, .108, 7, (245, 239, 181, 155)),
        (.777, .196, 12, palette["doodle"][:3] + (185,)),
        (.221, .517, 7, (255, 246, 171, 165)),
        (.630, .810, 12, (255, 244, 148, 130)),
    ]
    for x, y, radius, color in rings:
        r = radius * scale
        sw = max(2, round(1.6 * scale))
        gd.ellipse((w * x - r, h * y - r, w * x + r, h * y + r), outline=color, width=sw)
    gd.ellipse((w * .650, h * .802, w * .657, h * .809), fill=(255, 243, 142, 150))
    gd.ellipse((w * .667, h * .824, w * .674, h * .831), fill=(255, 243, 142, 120))
    blurred = glow.filter(ImageFilter.GaussianBlur(max(1, round(2.0 * scale))))
    layer.alpha_composite(blurred)
    layer.alpha_composite(glow)


def _draw_people_icon(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, color) -> None:
    sw = max(2, round(2.2 * scale))
    r = 5.5 * scale
    draw.ellipse((cx - r, cy - 12 * scale - r, cx + r, cy - 12 * scale + r), outline=color, width=sw)
    draw.arc((cx - 13 * scale, cy - 4 * scale, cx + 13 * scale, cy + 15 * scale), 180, 360, fill=color, width=sw)
    draw.ellipse((cx + 7 * scale, cy - 16 * scale, cx + 16 * scale, cy - 7 * scale), outline=color, width=sw)
    draw.arc((cx + 7 * scale, cy - 3 * scale, cx + 23 * scale, cy + 12 * scale), 205, 350, fill=color, width=sw)


def _draw_camera_icon(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, color) -> None:
    sw = max(2, round(2.2 * scale))
    box = (cx - 14 * scale, cy - 10 * scale, cx + 14 * scale, cy + 12 * scale)
    draw.rounded_rectangle(box, radius=4 * scale, outline=color, width=sw)
    draw.ellipse((cx - 5 * scale, cy - 5 * scale, cx + 5 * scale, cy + 5 * scale), outline=color, width=sw)
    draw.line((cx - 7 * scale, cy - 10 * scale, cx - 3 * scale, cy - 15 * scale, cx + 4 * scale, cy - 15 * scale, cx + 8 * scale, cy - 10 * scale), fill=color, width=sw, joint="curve")


def _draw_status_icons(draw: ImageDraw.ImageDraw, w: int, h: int, scale: float, color) -> None:
    sw = max(2, round(3.0 * scale))
    base_x = w * .716
    base_y = h * .041
    for index, bar_h in enumerate((5, 9, 13, 17)):
        x = base_x + index * 7 * scale
        draw.rounded_rectangle((x, base_y - bar_h * scale, x + 4 * scale, base_y), radius=2 * scale, fill=color)

    wifi_x = w * .806
    wifi_y = h * .0365
    outer_r = 11 * scale
    inner_r = 6.5 * scale
    draw.arc(
        (wifi_x - outer_r, wifi_y - outer_r, wifi_x + outer_r, wifi_y + outer_r),
        210,
        330,
        fill=color,
        width=sw,
    )
    draw.arc(
        (wifi_x - inner_r, wifi_y - inner_r, wifi_x + inner_r, wifi_y + inner_r),
        215,
        325,
        fill=color,
        width=sw,
    )
    dot_r = 2.2 * scale
    dot_y = wifi_y + 3.7 * scale
    draw.ellipse((wifi_x - dot_r, dot_y - dot_r, wifi_x + dot_r, dot_y + dot_r), fill=color)

    bx, by = w * .850, h * .028
    bw, bh = 31 * scale, 14 * scale
    draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=5 * scale, outline=color, width=sw)
    draw.rounded_rectangle((bx + 3 * scale, by + 3 * scale, bx + bw - 4 * scale, by + bh - 3 * scale), radius=3 * scale, fill=color)
    draw.rounded_rectangle((bx + bw + 2 * scale, by + 5 * scale, bx + bw + 5 * scale, by + bh - 5 * scale), radius=1.5 * scale, fill=color)


def _circle_avatar(layer: Image.Image, avatar: Image.Image | None, cx: float, cy: float, radius: float, palette: dict, scale: float) -> None:
    size = max(8, round(radius * 2))
    if avatar is not None:
        portrait = _cover(avatar, (size, size)).convert("RGBA")
    else:
        portrait = Image.new("RGBA", (size, size), palette["highlight"])
        pd = ImageDraw.Draw(portrait)
        pd.ellipse((size * .34, size * .16, size * .66, size * .48), fill=(255, 246, 229, 255))
        pd.ellipse((size * .18, size * .43, size * .82, size * 1.03), fill=(245, 132, 113, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    layer.paste(portrait, (round(cx - radius), round(cy - radius)), mask)
    ld = ImageDraw.Draw(layer)
    ring = max(2, round(2.5 * scale))
    ld.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(255, 255, 255, 255), width=ring)
    ld.arc((cx - radius - ring, cy - radius - ring, cx + radius + ring, cy + radius + ring), 210, 345, fill=(37, 176, 255, 255), width=ring)


def _draw_chat_icon(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float) -> None:
    r = 20 * scale
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 255))
    draw.polygon([(cx + 8 * scale, cy + 15 * scale), (cx + 17 * scale, cy + 24 * scale), (cx + 15 * scale, cy + 9 * scale)], fill=(255, 255, 255, 255))
    for offset in (-7, 0, 7):
        draw.ellipse((cx + offset * scale - 2 * scale, cy - 2 * scale, cx + offset * scale + 2 * scale, cy + 2 * scale), fill=(47, 51, 53, 255))


def _draw_plus_button(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, color) -> None:
    sw = max(3, round(3 * scale))
    r = 22 * scale
    draw.rounded_rectangle((cx - r, cy - r, cx + r, cy + r), radius=7 * scale, outline=color, width=sw)
    draw.line((cx - 8 * scale, cy, cx + 8 * scale, cy), fill=color, width=sw)
    draw.line((cx, cy - 8 * scale, cx, cy + 8 * scale), fill=color, width=sw)


def _draw_social_ui(
    layer: Image.Image,
    avatar: Image.Image | None,
    top_label: str,
    footer_username: str,
    footer_tag: str,
    palette: dict,
    scale: float,
) -> None:
    """Draw a generic, non-branded short-video style interface."""
    w, h = layer.size
    draw = ImageDraw.Draw(layer)
    white = (250, 250, 250, 255)
    muted = (190, 191, 194, 255)

    status_font = _font(max(round(20 * scale), 12), True)
    draw.text((w * .122, h * .022), "9:41", font=status_font, fill=white, anchor="la")
    _draw_status_icons(draw, w, h, scale, white)

    top_y = h * .098
    _draw_people_icon(draw, w * .062, top_y, scale, white)
    _draw_camera_icon(draw, w * .785, top_y + 1.5 * scale, scale, white)
    top_font = _font(max(round(20 * scale), 12), False)
    top_bbox = draw.textbbox((0, 0), top_label, font=top_font)
    top_text_y = top_y - (top_bbox[1] + top_bbox[3]) / 2
    draw.text((w * .835, top_text_y), top_label, font=top_font, fill=white)

    side_x = w * .927
    _circle_avatar(layer, avatar, side_x, h * .722, 29 * scale, palette, scale)
    draw = ImageDraw.Draw(layer)
    _draw_chat_icon(draw, side_x, h * .803, scale * 1.08)
    for offset in (-12, 0, 12):
        draw.ellipse((side_x + offset * scale - 3 * scale, h * .87 - 3 * scale, side_x + offset * scale + 3 * scale, h * .87 + 3 * scale), fill=white)

    # Translucent bottom dock keeps controls readable on arbitrary photos.
    dock_top = h * .902
    dock = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dock)
    dd.rectangle((0, dock_top, w, h), fill=(6, 7, 8, 210))
    layer.alpha_composite(dock)
    draw = ImageDraw.Draw(layer)

    meta_font = _font(max(round(19 * scale), 12), False)
    tag_font = _font(max(round(15 * scale), 10), True)
    meta_y = h * .872
    username_x = w * .02
    draw.text((username_x, meta_y), footer_username, font=meta_font, fill=white, anchor="lm")
    username_width = draw.textlength(footer_username, font=meta_font)
    tag_x = username_x + username_width + 10 * scale
    tag_bbox = (tag_x, meta_y - 12 * scale, tag_x + 43 * scale, meta_y + 13 * scale)
    draw.rounded_rectangle(tag_bbox, radius=5 * scale, fill=(0, 154, 55, 235))
    draw.text(((tag_bbox[0] + tag_bbox[2]) / 2, meta_y), footer_tag, font=tag_font, fill=(54, 237, 101, 255), anchor="mm")
    dot_x = tag_bbox[2] + 13 * scale
    draw.ellipse((dot_x - 2 * scale, meta_y - 2 * scale, dot_x + 2 * scale, meta_y + 2 * scale), fill=muted)
    draw.text((dot_x + 10 * scale, meta_y), "刚刚", font=tag_font, fill=muted, anchor="lm")

    nav_font = _font(max(round(18 * scale), 11), True)
    nav_y = h * .932
    for x, label, active in ((.09, "首页", False), (.30, "朋友", True), (.70, "消息", False), (.90, "我", False)):
        draw.text((w * x, nav_y), label, font=nav_font, fill=white if active else muted, anchor="mm")
    _draw_plus_button(draw, w * .5, nav_y, scale, white)

    indicator_w = 160 * scale
    indicator_y = h * .987
    draw.rounded_rectangle((w / 2 - indicator_w / 2, indicator_y, w / 2 + indicator_w / 2, indicator_y + 5 * scale), radius=3 * scale, fill=white)


def render_copy_poster(
    text: str,
    heading: str = "亲爱的",
    author: str = "@amoy TINA",
    background: Image.Image | None = None,
    avatar: Image.Image | None = None,
    top_label: str = "发日常",
    footer_username: str = "@不爱之王",
    footer_tag: str = "日常",
    options: PosterOptions | None = None,
) -> tuple[Image.Image, Image.Image]:
    """Render a poster and return (RGB image, L text mask)."""
    options = options or PosterOptions()
    palette = dict(STYLE.get(options.style, STYLE["清新手绘"]))
    palette["highlight"] = _parse_hex_color(options.highlight_color, palette["highlight"])
    palette["author"] = _parse_hex_color(options.author_color, palette["accent"])
    rng = random.Random(options.seed)

    # Work at 2x for smoother Chinese type and hand-drawn lines.
    aa = 2
    w, h = options.width * aa, options.height * aa
    scale = aa * options.width / 720
    ui_scale = aa * options.width / 520
    canvas = _prepare_background(background, (w, h), options.darkness, palette)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if options.show_doodles and options.style != "极简白字":
        _draw_ambient_glows(layer, palette, ui_scale)
    draw = ImageDraw.Draw(layer)
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)

    max_text_width = round(w * options.content_width)
    base_font_size = round(options.font_size * aa * options.width / 720)
    font_size = max(round(16 * aa), base_font_size)

    # Extract a JSON `text` field first, then normalize supported newline forms.
    copy_text = _extract_copy_text(text)
    normalized_text = copy_text.replace("\r\n", "\n").replace("\r", "\n").replace("/n", "\n")
    raw_paragraphs = normalized_text.split("\n")
    temp_draw = ImageDraw.Draw(Image.new("RGB", (4, 4)))

    def build_lines(size: int):
        font = _font(size, True)
        result = []
        for paragraph in raw_paragraphs:
            if not paragraph.strip():
                result.append([])
            else:
                result.extend(_wrap_runs(temp_draw, _parse_runs(paragraph.strip()), font, max_text_width))
        return font, result

    content_font, lines = build_lines(font_size)
    line_height = font_size * options.line_spacing
    max_content_height = h * 0.57
    while len(lines) * line_height > max_content_height and font_size > round(22 * scale):
        font_size -= max(1, round(2 * scale))
        content_font, lines = build_lines(font_size)
        line_height = font_size * options.line_spacing

    nonempty_count = sum(bool(line) for line in lines)
    empty_count = len(lines) - nonempty_count
    content_height = nonempty_count * line_height + empty_count * line_height * 0.45
    center_y = h * options.vertical_position
    start_y = center_y - content_height / 2

    # Border is sized around the actual content block, with generous editorial whitespace.
    if options.show_border:
        border_pad_x = w * 0.075
        border_pad_top = h * 0.061
        border_pad_bottom = h * 0.036
        border_box = (
            w * (1 - options.content_width) / 2 - border_pad_x,
            start_y - border_pad_top,
            w * (1 + options.content_width) / 2 + border_pad_x,
            start_y + content_height + border_pad_bottom,
        )
        border_box = (
            max(w * .08, border_box[0]),
            max(h * .18, border_box[1]),
            min(w * .92, border_box[2]),
            min(h * .80, border_box[3]),
        )
        _rounded_hand_border(draw, border_box, palette["line"], max(2, round(2.5 * scale)), rng)

    heading_font = _font(max(round(font_size * .67), round(18 * scale)), True)
    author_font = _font(max(round(options.author_font_size * ui_scale), round(10 * ui_scale)), True)
    heading_y = start_y - h * 0.085
    heading_width = draw.textlength(heading, font=heading_font)
    author_width = draw.textlength(author, font=author_font)
    group_width = max(heading_width, author_width)
    group_x = w / 2 - group_width / 2
    text_stroke_width = 0
    draw.text((group_x + (group_width - heading_width) / 2, heading_y), heading, font=heading_font, fill=palette["text"])
    author_x = group_x + (group_width - author_width) / 2 + options.author_offset_x * ui_scale
    author_y = heading_y + font_size * .95 + options.author_offset_y * ui_scale
    author_bbox = draw.textbbox((0, 0), author, font=author_font, stroke_width=text_stroke_width)
    author_center = (
        author_x + author_width / 2,
        author_y + (author_bbox[1] + author_bbox[3]) / 2,
    )
    _draw_rotated_text(
        layer,
        author,
        author_font,
        palette["author"],
        author_center,
        options.author_rotation,
        text_stroke_width,
        (0, 0, 0, 0),
    )

    y = start_y
    all_highlights = []
    stroke_width = text_stroke_width
    for line in lines:
        if line:
            _, highlight_boxes = _draw_centered_runs(
                draw,
                mask_draw,
                line,
                w / 2,
                y,
                content_font,
                palette["text"],
                palette["highlight"],
                stroke_width,
            )
            all_highlights.extend(highlight_boxes)
            y += line_height
        else:
            y += line_height * .45

    if options.style != "极简白字":
        for bbox in all_highlights:
            _draw_underline(draw, bbox, palette["highlight"], max(2, round(2.2 * scale)), rng)

    if options.show_doodles and options.style != "极简白字":
        _draw_doodles(draw, w, h, palette, rng, scale)

    if options.show_app_ui:
        _draw_social_ui(layer, avatar, top_label, footer_username, footer_tag, palette, ui_scale)

    composed = Image.alpha_composite(canvas, layer)
    output = composed.convert("RGB").resize((options.width, options.height), Image.Resampling.LANCZOS)
    output_mask = mask.resize((options.width, options.height), Image.Resampling.LANCZOS)
    return output, output_mask
