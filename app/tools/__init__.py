"""Tool registry. Import build_toolbox() to get every registered tool."""
from app.tools.base import ToolBox, ToolResult, ToolSpec


def build_toolbox() -> ToolBox:
    from app.tools import documents, files, sandbox

    box = ToolBox()
    for module in (files, documents, sandbox):
        for spec in module.SPECS:
            box.register(spec)
    return box


__all__ = ["ToolBox", "ToolResult", "ToolSpec", "build_toolbox"]
