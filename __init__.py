"""ComfyUI entry point for GitHub/Manager installations.

ComfyUI loads each direct child of ``custom_nodes`` as one Python package.  The
implementation lives in ``comfyui_copy_poster`` so that the downloadable ZIP
can still be installed as a standalone folder; this bridge exports the same
node mappings when the whole repository is cloned into ``custom_nodes``.
"""

from .comfyui_copy_poster import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

