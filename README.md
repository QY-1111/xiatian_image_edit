# xiatian_image_edit

一个用于将多行中文文案渲染成竖版社交媒体海报的 ComfyUI 自定义节点。

## 功能

- 自动裁切背景并添加暗色蒙版
- 中文自动换行与字号自适应
- `[[重点文字]]` 高光标记及可连接颜色输入槽
- 手绘边框、装饰线和背景光圈
- 模拟状态栏、侧边按钮、作者信息与底部导航
- 标题、账号名、颜色、字号及位置均可调
- 输出成品图与文字遮罩

## 安装

将 `comfyui_copy_poster` 文件夹复制到：

```text
ComfyUI/custom_nodes/comfyui_copy_poster
```

重启 ComfyUI，搜索节点 **文案海报 · Copy Poster**。

详细参数请查看 [插件说明](comfyui_copy_poster/README.md)。

