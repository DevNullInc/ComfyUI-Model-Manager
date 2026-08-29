"""
CivitAI Model Manager - ComfyUI Companion Node
Copyright (C) 2025-2026 TheStygianRenegade / /dev/null Inc
Licensed under GNU General Public License v3.0 (GPL-3.0)

ComfyUI-Model-Manager: Native companion node package for CivitAI Model Manager.
"""

try:
    from .datatypes import MODEL_BUNDLE
    from .nodes import (
        SmartModelLoader,
        PipeUnpackModel,
        CMMStatus,
        CMMInspectWorkflow,
        CMMWorkflowResolver,
        CMMResolveNode,
        CMMDownloadModel,
        CMMSearchCivitAI,
        CMMSearchAndQueue,
        CMMCheckHuggingFace,
        CMMRawRequest,
    )
except ImportError:
    from datatypes import MODEL_BUNDLE
    from nodes import (
        SmartModelLoader,
        PipeUnpackModel,
        CMMStatus,
        CMMInspectWorkflow,
        CMMWorkflowResolver,
        CMMResolveNode,
        CMMDownloadModel,
        CMMSearchCivitAI,
        CMMSearchAndQueue,
        CMMCheckHuggingFace,
        CMMRawRequest,
    )

NODE_CLASS_MAPPINGS = {
    "SmartModelLoader": SmartModelLoader,
    "PipeUnpackModel": PipeUnpackModel,
    "CMMStatus": CMMStatus,
    "CMMInspectWorkflow": CMMInspectWorkflow,
    "CMMWorkflowResolver": CMMWorkflowResolver,
    "CMMResolveNode": CMMResolveNode,
    "CMMDownloadModel": CMMDownloadModel,
    "CMMSearchCivitAI": CMMSearchCivitAI,
    "CMMSearchAndQueue": CMMSearchAndQueue,
    "CMMCheckHuggingFace": CMMCheckHuggingFace,
    "CMMRawRequest": CMMRawRequest,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SmartModelLoader": "CMM: Smart Model Loader",
    "PipeUnpackModel": "CMM: Unpack Model Pipe",
    "CMMStatus": "CMM: Status & Heartbeat",
    "CMMInspectWorkflow": "CMM: Inspect Workflow",
    "CMMWorkflowResolver": "CMM: Auto-Resolve Workflow",
    "CMMResolveNode": "CMM: Resolve Node",
    "CMMDownloadModel": "CMM: Download Model",
    "CMMSearchCivitAI": "CMM: Search CivitAI",
    "CMMSearchAndQueue": "CMM: Search & Queue Download",
    "CMMCheckHuggingFace": "CMM: Check Hugging Face",
    "CMMRawRequest": "CMM: Raw API Request",
}

WEB_DIRECTORY = "./web/js"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "MODEL_BUNDLE",
]
