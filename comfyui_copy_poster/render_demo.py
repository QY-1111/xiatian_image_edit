"""Standalone preview generator; not required by ComfyUI."""

from pathlib import Path
import sys

from PIL import Image

from renderer import PosterOptions, render_copy_poster


COPY = """在这个夏天
你在抖音记录下了
孩子的笑脸
[[海边的风]]
还有[[孩子慢慢长大]]的背影
原来夏天最动人的部分
就是这些被认真爱着的瞬间"""


def main() -> None:
    background = Image.open(sys.argv[1]) if len(sys.argv) > 1 else None
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "examples" / "preview.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    image, _ = render_copy_poster(
        COPY,
        heading="亲爱的",
        author="@amoy TINA",
        background=background,
        options=PosterOptions(),
    )
    image.save(target)
    print(target.resolve())


if __name__ == "__main__":
    main()
