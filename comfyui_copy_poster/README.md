# ComfyUI 文案海报节点

把多行文案和一张背景图排成竖版社交媒体海报。默认视觉参考“夏日记录”类内容：暗化照片、居中粗体中文、彩色重点词、手绘边框、轻量涂鸦和一套模拟 App 界面。

## 安装

将整个 `comfyui_copy_poster` 文件夹复制到：

```text
ComfyUI/custom_nodes/comfyui_copy_poster
```

重启 ComfyUI，在节点菜单的 **图像 / 文案排版** 中找到 **文案海报 · Copy Poster**。

节点只使用 ComfyUI 已有的 `torch`、`numpy` 和 `Pillow`，无需安装额外依赖。

## 使用

1. 可选地把 `Load Image` 接到 `background_image`。不接图片时会生成渐变背景。
2. 在 `text` 中输入文案。每个换行代表一个语义段落，过长内容会自动换行并在必要时自动缩小字号。
   同时兼容接口数据中常见的字面量 `/n`，节点会将其自动识别为换行。
3. 用双中括号标记重点词，例如：

```text
在这个夏天
你记录下了孩子的笑脸
[[海边的风]]
还有[[孩子慢慢长大]]的背影
```

4. `heading` 和 `author` 控制正文上方的小标题与署名。
5. 输出 `image` 可直接接 `Preview Image` 或 `Save Image`；`text_mask` 是文字区域遮罩，可用于后续合成。
6. 可将另一张图片连接到 `avatar_image`，用作右侧圆形头像。

## 参数

| 参数 | 作用 |
| --- | --- |
| `style` | 清新手绘、温暖日记、极简白字三种配色 |
| `width` / `height` | 输出尺寸，默认 520 × 1136，与参考长屏比例一致 |
| `font_size` | 正文字号，内容溢出时会自动缩小 |
| `highlight_color` | 重点文字和下划线颜色，默认柔和奶油黄 `#FFE08A`，支持 `#RRGGBB` |
| `highlight_color_input` | 可连接的字符串输入槽；接入后优先覆盖 `highlight_color`，例如连接 `#7CF3E8` |
| `author` | 正文上方的账号名，例如 `@amoy TINA` |
| `author_color` / `author_font_size` | 账号名颜色和字号 |
| `author_offset_x` / `author_offset_y` | 账号名横向、纵向微调；负数表示向左或向上 |
| `line_spacing` | 行间距倍数 |
| `content_width` | 正文最大宽度占画布比例 |
| `vertical_position` | 正文块垂直中心位置 |
| `darkness` | 背景暗化强度 |
| `show_border` | 是否绘制手绘边框 |
| `show_doodles` | 是否绘制彩色涂鸦 |
| `show_app_ui` | 是否模拟状态栏、入口图标、侧边按钮和底部导航 |
| `top_label` | 右上角入口文案，默认“发日常” |
| `footer_username` / `footer_tag` | 左下角作者名与绿色标签 |
| `seed` | 控制手绘线条的轻微随机变化 |

## 字体

节点会自动查找微软雅黑、黑体、等线、苹方、Noto Sans CJK 等中文字体。也可通过环境变量 `COPY_POSTER_FONT` 指定字体文件的绝对路径，然后重启 ComfyUI。

## 文件结构

```text
comfyui_copy_poster/
├── __init__.py
├── nodes.py
├── renderer.py
├── README.md
└── examples/
    ├── preview.png
    └── workflow_api.json
```
