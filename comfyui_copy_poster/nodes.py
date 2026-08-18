from __future__ import annotations

import numpy as np
import torch
from PIL import Image

from .renderer import PosterOptions, render_copy_poster


DEFAULT_COPY = """在这个夏天
你在抖音记录下了
孩子的笑脸
[[海边的风]]
还有[[孩子慢慢长大]]的背影
原来夏天最动人的部分
就是这些被认真爱着的瞬间"""


def _tensor_to_pil(image: torch.Tensor) -> Image.Image:
    array = image.detach().cpu().numpy()
    array = np.clip(array * 255.0, 0, 255).astype(np.uint8)
    if array.shape[-1] == 4:
        return Image.fromarray(array, "RGBA")
    return Image.fromarray(array[..., :3], "RGB")


def _pil_to_tensor(image: Image.Image) -> torch.Tensor:
    array = np.asarray(image.convert("RGB"), dtype=np.float32).copy() / 255.0
    return torch.from_numpy(array)[None, ...]


class CopyPoster:
    """Render social-media style copy over a portrait background."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "default": DEFAULT_COPY,
                        "multiline": True,
                        "dynamicPrompts": False,
                        "tooltip": "每个换行是一个文案段落；用 [[文字]] 标出高亮内容。",
                    },
                ),
                "heading": (
                    "STRING",
                    {
                        "default": "亲爱的",
                        "multiline": False,
                        "dynamicPrompts": False,
                    },
                ),
                "author": (
                    "STRING",
                    {
                        "default": "@amoy TINA",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "tooltip": "正文上方的账号名，例如 @amoy TINA。",
                    },
                ),
                "author_color": (
                    "STRING",
                    {
                        "default": "#FFF06A",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "tooltip": "账号名颜色，支持 #RRGGBB。",
                    },
                ),
                "author_font_size": (
                    "INT",
                    {"default": 27, "min": 10, "max": 120, "step": 1, "tooltip": "账号名字号。"},
                ),
                "author_offset_x": (
                    "INT",
                    {"default": 0, "min": -240, "max": 240, "step": 1, "tooltip": "账号名横向偏移，负数向左。"},
                ),
                "author_offset_y": (
                    "INT",
                    {"default": 0, "min": -240, "max": 240, "step": 1, "tooltip": "账号名纵向偏移，负数向上。"},
                ),
                "style": (["清新手绘", "温暖日记", "极简白字"], {"default": "清新手绘"}),
                "width": ("INT", {"default": 520, "min": 256, "max": 4096, "step": 8}),
                "height": ("INT", {"default": 1136, "min": 256, "max": 4096, "step": 8}),
                "font_size": ("INT", {"default": 43, "min": 16, "max": 180, "step": 1}),
                "highlight_color": (
                    "STRING",
                    {
                        "default": "#FFE08A",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "tooltip": "重点文字与下划线颜色，支持 #RRGGBB，例如 #FFE08A。",
                    },
                ),
                "line_spacing": ("FLOAT", {"default": 1.92, "min": 1.0, "max": 3.0, "step": 0.05}),
                "content_width": ("FLOAT", {"default": 0.78, "min": 0.45, "max": 0.94, "step": 0.01}),
                "vertical_position": ("FLOAT", {"default": 0.51, "min": 0.25, "max": 0.75, "step": 0.01}),
                "darkness": ("FLOAT", {"default": 0.48, "min": 0.0, "max": 0.9, "step": 0.01}),
                "show_border": ("BOOLEAN", {"default": True}),
                "show_doodles": ("BOOLEAN", {"default": True}),
                "show_app_ui": (
                    "BOOLEAN",
                    {"default": True, "tooltip": "模拟状态栏、侧边按钮、作者信息和底部导航。"},
                ),
                "top_label": (
                    "STRING",
                    {"default": "发日常", "multiline": False, "dynamicPrompts": False},
                ),
                "footer_username": (
                    "STRING",
                    {"default": "@不爱之王", "multiline": False, "dynamicPrompts": False},
                ),
                "footer_tag": (
                    "STRING",
                    {"default": "日常", "multiline": False, "dynamicPrompts": False},
                ),
                "seed": ("INT", {"default": 1257, "min": 0, "max": 0xFFFFFFFF}),
            },
            "optional": {
                "highlight_color_input": (
                    "STRING",
                    {
                        "forceInput": True,
                        "tooltip": "文案高光颜色输入槽。连接 #RRGGBB 字符串后，会覆盖节点中的 highlight_color。",
                    },
                ),
                "background_image": (
                    "IMAGE",
                    {"tooltip": "可选。未连接时使用节点自带的渐变背景。"},
                ),
                "avatar_image": (
                    "IMAGE",
                    {"tooltip": "可选。用于右侧圆形头像；未连接时绘制通用头像。"},
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "text_mask")
    FUNCTION = "render"
    CATEGORY = "图像/文案排版"
    DESCRIPTION = "将多行文案渲染为竖版社交媒体风格海报。[[双中括号]] 内的文字会高亮。"

    def render(
        self,
        text: str,
        heading: str,
        author: str,
        author_color: str,
        author_font_size: int,
        author_offset_x: int,
        author_offset_y: int,
        style: str,
        width: int,
        height: int,
        font_size: int,
        highlight_color: str,
        line_spacing: float,
        content_width: float,
        vertical_position: float,
        darkness: float,
        show_border: bool,
        show_doodles: bool,
        show_app_ui: bool,
        top_label: str,
        footer_username: str,
        footer_tag: str,
        seed: int,
        highlight_color_input: str | None = None,
        background_image: torch.Tensor | None = None,
        avatar_image: torch.Tensor | None = None,
    ):
        resolved_highlight_color = (
            highlight_color_input.strip()
            if isinstance(highlight_color_input, str) and highlight_color_input.strip()
            else highlight_color
        )
        options = PosterOptions(
            width=width,
            height=height,
            font_size=font_size,
            highlight_color=resolved_highlight_color,
            author_color=author_color,
            author_font_size=author_font_size,
            author_offset_x=author_offset_x,
            author_offset_y=author_offset_y,
            line_spacing=line_spacing,
            content_width=content_width,
            vertical_position=vertical_position,
            darkness=darkness,
            show_border=show_border,
            show_doodles=show_doodles,
            show_app_ui=show_app_ui,
            style=style,
            seed=seed,
        )

        sources = [None]
        if background_image is not None:
            sources = [_tensor_to_pil(item) for item in background_image]

        avatars = []
        if avatar_image is not None:
            avatars = [_tensor_to_pil(item) for item in avatar_image]

        images = []
        masks = []
        for index, source in enumerate(sources):
            avatar = avatars[min(index, len(avatars) - 1)] if avatars else None
            rendered, text_mask = render_copy_poster(
                text=text,
                heading=heading,
                author=author,
                background=source,
                avatar=avatar,
                top_label=top_label,
                footer_username=footer_username,
                footer_tag=footer_tag,
                options=options.with_seed(seed + index),
            )
            images.append(_pil_to_tensor(rendered))
            mask_array = np.asarray(text_mask, dtype=np.float32).copy() / 255.0
            masks.append(torch.from_numpy(mask_array)[None, ...])

        return (torch.cat(images, dim=0), torch.cat(masks, dim=0))


NODE_CLASS_MAPPINGS = {"CopyPoster": CopyPoster}
NODE_DISPLAY_NAME_MAPPINGS = {"CopyPoster": "文案海报 · Copy Poster"}
