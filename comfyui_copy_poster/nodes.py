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
                "文案内容": (
                    "STRING",
                    {
                        "default": DEFAULT_COPY,
                        "multiline": True,
                        "dynamicPrompts": False,
                        "tooltip": "每个换行是一个文案段落；用 [[文字]] 标出高亮内容。",
                    },
                ),
                "顶部称呼": (
                    "STRING",
                    {
                        "default": "亲爱的",
                        "multiline": False,
                        "dynamicPrompts": False,
                    },
                ),
                "账号名称": (
                    "STRING",
                    {
                        "default": "@amoy TINA",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "tooltip": "正文上方的账号名，例如 @amoy TINA。",
                    },
                ),
                "账号颜色": (
                    "STRING",
                    {
                        "default": "#FFF06A",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "tooltip": "账号名颜色，支持 #RRGGBB。",
                    },
                ),
                "账号字号": (
                    "INT",
                    {"default": 27, "min": 10, "max": 120, "step": 1, "tooltip": "账号名字号。"},
                ),
                "账号水平偏移": (
                    "INT",
                    {"default": 0, "min": -240, "max": 240, "step": 1, "tooltip": "账号名横向偏移，负数向左。"},
                ),
                "账号垂直偏移": (
                    "INT",
                    {"default": 0, "min": -240, "max": 240, "step": 1, "tooltip": "账号名纵向偏移，负数向上。"},
                ),
                "视觉风格": (["清新手绘", "温暖日记", "极简白字"], {"default": "清新手绘"}),
                "图片宽度": ("INT", {"default": 520, "min": 256, "max": 4096, "step": 8}),
                "图片高度": ("INT", {"default": 1136, "min": 256, "max": 4096, "step": 8}),
                "正文字号": ("INT", {"default": 43, "min": 16, "max": 180, "step": 1}),
                "高光颜色": (
                    "STRING",
                    {
                        "default": "#FFE08A",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "tooltip": "重点文字与下划线颜色，支持 #RRGGBB，例如 #FFE08A。",
                    },
                ),
                "行间距": ("FLOAT", {"default": 1.92, "min": 1.0, "max": 3.0, "step": 0.05}),
                "文案宽度比例": ("FLOAT", {"default": 0.78, "min": 0.45, "max": 0.94, "step": 0.01}),
                "文案垂直位置": ("FLOAT", {"default": 0.51, "min": 0.25, "max": 0.75, "step": 0.01}),
                "背景压暗强度": ("FLOAT", {"default": 0.48, "min": 0.0, "max": 0.9, "step": 0.01}),
                "显示手绘边框": ("BOOLEAN", {"default": True}),
                "显示装饰图案": ("BOOLEAN", {"default": True}),
                "显示界面图标": (
                    "BOOLEAN",
                    {"default": True, "tooltip": "模拟状态栏、侧边按钮、作者信息和底部导航。"},
                ),
                "右上角文字": (
                    "STRING",
                    {"default": "发日常", "multiline": False, "dynamicPrompts": False},
                ),
                "底部用户名": (
                    "STRING",
                    {"default": "@不爱之王", "multiline": False, "dynamicPrompts": False},
                ),
                "底部标签": (
                    "STRING",
                    {"default": "日常", "multiline": False, "dynamicPrompts": False},
                ),
                "随机种子": ("INT", {"default": 1257, "min": 0, "max": 0xFFFFFFFF}),
            },
            "optional": {
                "高光颜色输入": (
                    "STRING",
                    {
                        "forceInput": True,
                        "tooltip": "文案高光颜色输入槽。连接 #RRGGBB 字符串后，会覆盖节点中的高光颜色。",
                    },
                ),
                "背景图片": (
                    "IMAGE",
                    {"tooltip": "可选。未连接时使用节点自带的渐变背景。"},
                ),
                "头像图片": (
                    "IMAGE",
                    {"tooltip": "可选。用于右侧圆形头像；未连接时绘制通用头像。"},
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("成品图片", "文字遮罩")
    FUNCTION = "render"
    CATEGORY = "图像/文案排版"
    DESCRIPTION = "将多行文案渲染为竖版社交媒体风格海报。[[双中括号]] 内的文字会高亮。"

    def render(self, **参数):
        """Use Chinese widget names while accepting legacy English API keys."""
        def 取值(中文名, 英文名, 默认值=None):
            return 参数[中文名] if 中文名 in 参数 else 参数.get(英文名, 默认值)

        text = 取值("文案内容", "text", DEFAULT_COPY)
        heading = 取值("顶部称呼", "heading", "亲爱的")
        author = 取值("账号名称", "author", "@amoy TINA")
        author_color = 取值("账号颜色", "author_color", "#FFF06A")
        author_font_size = 取值("账号字号", "author_font_size", 27)
        author_offset_x = 取值("账号水平偏移", "author_offset_x", 0)
        author_offset_y = 取值("账号垂直偏移", "author_offset_y", 0)
        style = 取值("视觉风格", "style", "清新手绘")
        width = 取值("图片宽度", "width", 520)
        height = 取值("图片高度", "height", 1136)
        font_size = 取值("正文字号", "font_size", 43)
        highlight_color = 取值("高光颜色", "highlight_color", "#FFE08A")
        line_spacing = 取值("行间距", "line_spacing", 1.92)
        content_width = 取值("文案宽度比例", "content_width", 0.78)
        vertical_position = 取值("文案垂直位置", "vertical_position", 0.51)
        darkness = 取值("背景压暗强度", "darkness", 0.48)
        show_border = 取值("显示手绘边框", "show_border", True)
        show_doodles = 取值("显示装饰图案", "show_doodles", True)
        show_app_ui = 取值("显示界面图标", "show_app_ui", True)
        top_label = 取值("右上角文字", "top_label", "发日常")
        footer_username = 取值("底部用户名", "footer_username", "@不爱之王")
        footer_tag = 取值("底部标签", "footer_tag", "日常")
        seed = 取值("随机种子", "seed", 1257)
        highlight_color_input = 取值("高光颜色输入", "highlight_color_input")
        background_image = 取值("背景图片", "background_image")
        avatar_image = 取值("头像图片", "avatar_image")

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
