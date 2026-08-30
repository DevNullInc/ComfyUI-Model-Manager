"""
CivitAI Model Manager - ComfyUI Companion Node
Copyright (C) 2025-2026 TheStygianRenegade / /dev/null Inc
Licensed under GNU General Public License v3.0 (GPL-3.0)

ComfyUI Custom Nodes for CivitAI Model Manager (CMM)
"""

import gc
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from .cmm_client import CMMClient
    from .datatypes import MODEL_BUNDLE
except ImportError:
    from cmm_client import CMMClient
    from datatypes import MODEL_BUNDLE

logger = logging.getLogger("ComfyUI-Model-Manager")

# -----------------------------------------------------------------------------
# Optional ComfyUI runtime imports with safe fallbacks
# -----------------------------------------------------------------------------
try:
    import folder_paths  # type: ignore
except ImportError:
    folder_paths = None

try:
    import comfy.sd  # type: ignore
    import comfy.utils  # type: ignore
except ImportError:
    try:
        import importlib
        comfy_sd = importlib.import_module("comfy.sd")
        comfy_utils = importlib.import_module("comfy.utils")
        class _ComfyModuleStub:
            sd = comfy_sd
            utils = comfy_utils
        comfy = _ComfyModuleStub()
    except Exception:
        comfy = None

try:
    from server import PromptServer  # type: ignore
except ImportError:
    PromptServer = None

try:
    import torch  # type: ignore
except ImportError:
    torch = None

try:
    import comfy.model_management  # type: ignore
except ImportError:
    pass


def _send_cmm_event(event_name: str, data: Dict[str, Any]):
    """Safely dispatch real-time events to frontend via PromptServer."""
    if PromptServer and hasattr(PromptServer, "instance") and PromptServer.instance:
        try:
            PromptServer.instance.send_sync(event_name, data)
        except Exception:
            pass


def _get_default_cmm_port() -> int:
    """Helper to detect configured CMM API port from environment or settings."""
    env_port = os.environ.get("CMM_PORT") or os.environ.get("API_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    return 5174


def _get_folder_filenames(folder_name: str) -> List[str]:
    """Helper to safely fetch filenames from ComfyUI folder_paths."""
    if folder_paths and hasattr(folder_paths, "get_filename_list"):
        try:
            files = folder_paths.get_filename_list(folder_name)
            if files:
                return sorted(list(files))
        except Exception:
            pass
    return ["none"]


# =============================================================================
# 1. Smart Model Loader (Pipe & Metadata-Aware)
# =============================================================================
class SmartModelLoader:
    """
    Unified smart model loader with CMM integration.
    Auto-detects architecture from CMM metadata or filename and outputs MODEL_BUNDLE pipe.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Loaders"
    FUNCTION = "load_model"
    RETURN_TYPES = ("MODEL_BUNDLE",)
    RETURN_NAMES = ("pipe",)

    @classmethod
    def INPUT_TYPES(cls):
        checkpoints = _get_folder_filenames("checkpoints")
        clips = ["none"] + [f for f in _get_folder_filenames("clip") if f != "none"]
        vaes = ["none"] + [f for f in _get_folder_filenames("vae") if f != "none"]

        return {
            "required": {
                "checkpoint": (checkpoints, {"default": checkpoints[0] if checkpoints else "none"}),
                "loader mode": (
                    ["AUTO", "Standard SD", "SDXL", "FLUX", "WAN", "LTX", "MiniMaxH3", "Anima", "Qwen"],
                    {"default": "AUTO"},
                ),
                "clip source": (["Baked In", "Separate File", "None"], {"default": "Baked In"}),
                "vae source": (["Baked In", "Separate File", "None"], {"default": "Baked In"}),
                "check cmm": ("BOOLEAN", {"default": True, "tooltip": "Query CMM for model metadata"}),
                "auto download": ("BOOLEAN", {"default": False, "tooltip": "Queue download if missing from CMM"}),
            },
            "optional": {
                "clip name": (clips, {"default": clips[0] if clips else "none"}),
                "vae name": (vaes, {"default": vaes[0] if vaes else "none"}),
                "cmm port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535, "tooltip": "CMM API port (default: 5174)"}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs) -> str:
        return "{}:{}:{}:{}:{}:{}:{}".format(
            kwargs.get("checkpoint", ""),
            kwargs.get("loader mode", ""),
            kwargs.get("clip source", ""),
            kwargs.get("vae source", ""),
            kwargs.get("clip name", ""),
            kwargs.get("vae name", ""),
            kwargs.get("cmm port", ""),
        )

    def detect_model_type(self, checkpoint_name: str, metadata: Dict[str, Any]) -> str:
        """Auto-detect model architecture from filename or CMM metadata."""
        name_lower = (checkpoint_name or "").lower()

        # Check CMM metadata baseModel first
        if metadata and metadata.get("baseModel"):
            base = str(metadata["baseModel"]).upper()
            mapping = {
                "SD 1.5": "SD1.5",
                "SD1.5": "SD1.5",
                "SDXL 1.0": "SDXL",
                "SDXL": "SDXL",
                "PONY": "SDXL",
                "ILLUSTRIOUS": "SDXL",
                "FLUX.1 D": "FLUX",
                "FLUX.1 S": "FLUX",
                "FLUX": "FLUX",
                "LTXV": "LTX",
                "LTX": "LTX",
                "WAN": "WAN",
                "MINIMAX": "MiniMaxH3",
                "ANIMA": "Anima",
                "QWEN": "Qwen",
            }
            for key, val in mapping.items():
                if key in base:
                    return val

        # Fallback to filename patterns
        if "flux" in name_lower:
            return "FLUX"
        elif "xl" in name_lower or "sdxl" in name_lower or "pony" in name_lower or "illustrious" in name_lower:
            return "SDXL"
        elif "wan" in name_lower:
            return "WAN"
        elif "ltx" in name_lower:
            return "LTX"
        elif "minimax" in name_lower or "h3" in name_lower:
            return "MiniMaxH3"
        elif "anima" in name_lower:
            return "Anima"
        elif "qwen" in name_lower:
            return "Qwen"
        elif "v1-5" in name_lower or "sd15" in name_lower or "1.5" in name_lower:
            return "SD1.5"

        return "Standard SD"

    def load_model(self, **kwargs) -> Tuple[MODEL_BUNDLE]:
        checkpoint = kwargs.get("checkpoint", "none")
        loader_mode = kwargs.get("loader mode", "AUTO")
        clip_source = kwargs.get("clip source", "Baked In")
        vae_source = kwargs.get("vae source", "Baked In")
        check_cmm = kwargs.get("check cmm", True)
        clip_name = kwargs.get("clip name")
        vae_name = kwargs.get("vae name")
        cmm_port = kwargs.get("cmm port", _get_default_cmm_port())

        # 1. Query CMM for model metadata if enabled
        model_metadata: Dict[str, Any] = {}
        cmm = CMMClient(port=cmm_port)

        if check_cmm and cmm.is_online():
            try:
                local_models = cmm.get_local_models()
                for m in local_models:
                    if m.get("fileName") == checkpoint or os.path.basename(m.get("filePath", "")) == checkpoint:
                        model_metadata = m
                        break
            except Exception as e:
                logger.debug(f"Error checking CMM metadata: {e}")

        # 2. Determine architecture mode
        detected_mode = self.detect_model_type(checkpoint, model_metadata)
        final_mode = detected_mode if loader_mode == "AUTO" else loader_mode

        model = None
        clip = None
        vae_out = None

        # 3. Load via ComfyUI if available
        if folder_paths and comfy:
            ckpt_path = folder_paths.get_full_path("checkpoints", checkpoint)
            if ckpt_path and os.path.exists(ckpt_path):
                load_clip = (clip_source == "Baked In")
                load_vae = (vae_source == "Baked In")
                try:
                    embed_dir = folder_paths.get_folder_paths("embeddings") if hasattr(folder_paths, "get_folder_paths") else None
                    out = comfy.sd.load_checkpoint_guess_config(
                        ckpt_path,
                        output_vae=load_vae,
                        output_clip=load_clip,
                        embedding_directory=embed_dir,
                    )
                    model = out[0]
                    if load_clip and len(out) > 1:
                        clip = out[1]
                    if load_vae and len(out) > 2:
                        vae_out = out[2]
                except Exception as e:
                    logger.error(f"Failed to load checkpoint '{checkpoint}': {e}")

            # Handle separate CLIP
            if clip_source == "Separate File" and clip_name and clip_name != "none":
                clip_path = folder_paths.get_full_path("clip", clip_name)
                if clip_path and os.path.exists(clip_path):
                    try:
                        clip = comfy.sd.load_clip(ckpt_paths=[clip_path])
                    except Exception as e:
                        logger.error(f"Failed to load separate clip '{clip_name}': {e}")
            elif clip_source == "None":
                clip = None

            # Handle separate VAE
            if vae_source == "Separate File" and vae_name and vae_name != "none":
                vae_path = folder_paths.get_full_path("vae", vae_name)
                if vae_path and os.path.exists(vae_path):
                    try:
                        vae_out = comfy.sd.VAE(sd=comfy.utils.load_torch_file(vae_path))
                    except Exception as e:
                        logger.error(f"Failed to load separate vae '{vae_name}': {e}")
            elif vae_source == "None":
                vae_out = None

        # 4. Construct metadata dictionary
        metadata = {
            "checkpoint": checkpoint,
            "model_type": final_mode,
            "detected_mode": detected_mode,
            "clip_source": clip_source,
            "vae_source": vae_source,
            "clip_name": clip_name if clip_source == "Separate File" else None,
            "vae_name": vae_name if vae_source == "Separate File" else None,
            "civitai_id": model_metadata.get("civitaiModelId"),
            "version_id": model_metadata.get("civitaiVersionId"),
            "file_path": model_metadata.get("filePath"),
            "base_model": model_metadata.get("baseModel", "Unknown"),
            "cmm_matched": bool(model_metadata),
        }

        # 5. Pack into MODEL_BUNDLE pipe
        pipe = MODEL_BUNDLE(
            model=model,
            clip=clip,
            vae=vae_out,
            model_type=final_mode,
            metadata=metadata,
        )

        return (pipe,)


# =============================================================================
# 2. Pipe Unpacker
# =============================================================================
class PipeUnpackModel:
    """
    Deconstructs a MODEL_BUNDLE pipe into individual model, clip, vae components
    with optional type, info, and debug outputs.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Loaders"
    FUNCTION = "unpack"
    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "type", "info", "debug")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pipe": ("MODEL_BUNDLE",),
            },
        }

    def unpack(self, pipe: Any) -> Tuple[Any, Any, Any, str, str, str]:
        if isinstance(pipe, (tuple, list)) and len(pipe) >= 5:
            model, clip, vae, model_type, metadata = pipe[0], pipe[1], pipe[2], pipe[3], pipe[4]
        else:
            model, clip, vae, model_type, metadata = None, None, None, "Unknown", {}

        meta = metadata if isinstance(metadata, dict) else {}

        # type: architecture identifier
        type_str = str(model_type)

        # info: human-readable summary
        info_lines = [
            f"Checkpoint: {meta.get('checkpoint', 'N/A')}",
            f"Architecture: {type_str}",
            f"Base Model: {meta.get('base_model', 'Unknown')}",
            f"CMM Matched: {'Yes' if meta.get('cmm_matched') else 'No'}",
        ]
        if meta.get("civitai_id"):
            info_lines.append(f"CivitAI ID: {meta['civitai_id']}")
        if meta.get("version_id"):
            info_lines.append(f"Version ID: {meta['version_id']}")
        info_str = "\n".join(info_lines)

        # debug: full metadata JSON dump
        debug_str = json.dumps(meta, indent=2)

        return (model, clip, vae, type_str, info_str, debug_str)


# =============================================================================
# 3. CMM Status & Heartbeat
# =============================================================================
class CMMStatus:
    """
    Verifies connection, API port, and database uptime with CivitAI Model Manager.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Manager"
    FUNCTION = "check_status"
    RETURN_TYPES = ("BOOLEAN", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("is_online", "status_text", "version", "details_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "cmm_port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535, "tooltip": "CMM API port"}),
                "base_url": ("STRING", {"default": "", "tooltip": "Optional custom base URL (e.g. http://127.0.0.1:5174)"}),
            }
        }

    def check_status(self, cmm_port: int = 5174, base_url: str = "") -> Tuple[bool, str, str, str]:
        client = CMMClient(port=cmm_port, base_url=base_url if base_url else None)
        status_data = client.get_status()
        health_data = client.get_health()

        online = client.is_online()
        version = str(status_data.get("version", "Unknown"))
        status_text = "Online" if online else "Offline / Unreachable"

        details = {
            "online": online,
            "status": status_data,
            "health": health_data,
            "base_url": client.base_url,
        }

        _send_cmm_event("cmm.status", {"is_online": online, "version": version, "port": cmm_port})

        return (online, status_text, version, json.dumps(details, indent=2))


# =============================================================================
# 4. CMM Inspect Workflow
# =============================================================================
class CMMInspectWorkflow:
    """
    Scans in-memory workflow graph or prompt dictionary for referenced/missing models and custom nodes.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Manager"
    FUNCTION = "inspect_workflow"
    RETURN_TYPES = ("INT", "INT", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("model_count", "node_type_count", "missing_models_list", "missing_nodes_list", "details_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "cmm_port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535}),
                "workflow_json": ("STRING", {"multiline": True, "default": "", "tooltip": "Optional raw workflow JSON. If empty, uses active execution prompt."}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    def inspect_workflow(
        self,
        cmm_port: int = 5174,
        workflow_json: str = "",
        prompt: Optional[Dict[str, Any]] = None,
        extra_pnginfo: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, int, str, str, str]:
        client = CMMClient(port=cmm_port)

        payload_workflow = None
        if workflow_json and workflow_json.strip():
            try:
                payload_workflow = json.loads(workflow_json)
            except Exception:
                pass

        if payload_workflow is not None:
            analysis = client.parse_workflow(workflow_data=payload_workflow)
        elif extra_pnginfo and isinstance(extra_pnginfo, dict) and "workflow" in extra_pnginfo:
            analysis = client.parse_workflow(workflow_data=extra_pnginfo["workflow"], name="active_canvas.json")
        elif prompt is not None:
            analysis = client.parse_workflow(prompt=prompt)
        else:
            analysis = client.parse_workflow(workflow_data={})

        models = analysis.get("models", [])
        node_types = analysis.get("nodeTypes", [])

        missing_models = [m.get("modelName", "unknown") for m in models if not m.get("isInstalled", True)]
        missing_nodes = []

        # Check missing nodes with CMM resolve
        for nt in node_types:
            res = client.resolve_missing_node(nt)
            if not res.get("isInstalled", True):
                missing_nodes.append(nt)

        return (
            len(models),
            len(node_types),
            ", ".join(missing_models) if missing_models else "None",
            ", ".join(missing_nodes) if missing_nodes else "None",
            json.dumps(analysis, indent=2),
        )


# =============================================================================
# 5. CMM Auto-Resolve Workflow
# =============================================================================
class CMMWorkflowResolver:
    """
    Inspects current workflow via CMM and auto-resolves missing nodes and models.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Manager"
    FUNCTION = "resolve"
    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("status_json", "resolution_report", "all_resolved")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "resolve_nodes": ("BOOLEAN", {"default": True}),
                "resolve_models": ("BOOLEAN", {"default": True}),
                "auto_clone": ("BOOLEAN", {"default": False, "tooltip": "Automatically git clone missing custom nodes"}),
                "auto_download": ("BOOLEAN", {"default": False, "tooltip": "Automatically queue missing models for download"}),
            },
            "optional": {
                "cmm_port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535}),
            },
            "hidden": {
                "prompt": "PROMPT",
            },
        }

    def resolve(
        self,
        resolve_nodes: bool,
        resolve_models: bool,
        auto_clone: bool,
        auto_download: bool,
        cmm_port: int = 5174,
        prompt: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, bool]:
        cmm = CMMClient(port=cmm_port)
        analysis = cmm.parse_workflow(prompt=prompt or {}, name="active_execution_prompt.json")

        results: Dict[str, Any] = {
            "missing_nodes": [],
            "missing_models": [],
            "resolved_nodes": [],
            "queued_downloads": [],
        }

        # 1. Resolve missing custom nodes
        if resolve_nodes:
            for node_type in analysis.get("nodeTypes", []):
                resolution = cmm.resolve_missing_node(node_type)
                if not resolution.get("isInstalled", False):
                    results["missing_nodes"].append(node_type)
                    if auto_clone and resolution.get("registryMatch"):
                        git_url = resolution["registryMatch"].get("gitUrl")
                        if git_url:
                            clone_res = cmm.clone_custom_node(git_url)
                            if clone_res.get("success"):
                                results["resolved_nodes"].append(node_type)

        # 2. Resolve missing models
        if resolve_models:
            for model in analysis.get("models", []):
                if not model.get("isInstalled", False):
                    model_name = model.get("modelName", "")
                    results["missing_models"].append(model_name)
                    if auto_download and model.get("civitaiVersionId"):
                        dl_res = cmm.download_model(
                            file_name=model_name,
                            model_type=model.get("modelType", "Checkpoint"),
                            model_version_id=model["civitaiVersionId"],
                            base_model=model.get("baseModel", "SDXL 1.0"),
                        )
                        if dl_res.get("id"):
                            results["queued_downloads"].append(model_name)

        all_resolved = (
            len(set(results["missing_nodes"]) - set(results["resolved_nodes"])) == 0
            and len(results["missing_models"]) == 0
        )

        # Build human readable report
        report_lines = ["=== CivitAI Model Manager Workflow Resolution Report ==="]
        if results["resolved_nodes"]:
            report_lines.append(f"✅ Auto-Cloned Nodes: {', '.join(results['resolved_nodes'])}")
        remaining_nodes = list(set(results["missing_nodes"]) - set(results["resolved_nodes"]))
        if remaining_nodes:
            report_lines.append(f"❌ Missing Custom Nodes: {', '.join(remaining_nodes)}")
        if results["queued_downloads"]:
            report_lines.append(f"📥 Queued Model Downloads: {', '.join(results['queued_downloads'])}")
        if results["missing_models"]:
            report_lines.append(f"⚠️ Unresolved Models: {', '.join(results['missing_models'])}")
        if not results["missing_nodes"] and not results["missing_models"]:
            report_lines.append("🎉 All workflow nodes and models are installed locally!")

        report_text = "\n".join(report_lines)
        return (json.dumps(results, indent=2), report_text, all_resolved)


# =============================================================================
# 6. CMM Resolve Node
# =============================================================================
class CMMResolveNode:
    """
    4-tier query to find install repos for missing node types with optional auto-clone & dep installation.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Manager"
    FUNCTION = "resolve_node"
    RETURN_TYPES = ("BOOLEAN", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("is_installed", "git_url", "author", "title", "details_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "node_type": ("STRING", {"default": "", "tooltip": "Class name of missing node (e.g. ImpactWildcardProcessor)"}),
            },
            "optional": {
                "auto_clone": ("BOOLEAN", {"default": False, "tooltip": "Clone repository into custom_nodes/ if found"}),
                "install_deps": ("BOOLEAN", {"default": False, "tooltip": "Run pip install requirements.txt if cloned"}),
                "cmm_port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535}),
            },
        }

    def resolve_node(
        self,
        node_type: str,
        auto_clone: bool = False,
        install_deps: bool = False,
        cmm_port: int = 5174,
    ) -> Tuple[bool, str, str, str, str]:
        client = CMMClient(port=cmm_port)
        res = client.resolve_missing_node(node_type.strip())

        is_installed = res.get("isInstalled", False)
        reg = res.get("registryMatch") or {}
        git_url = reg.get("gitUrl", "")
        author = reg.get("author", "")
        title = reg.get("title", "")

        if not git_url and res.get("githubCandidates"):
            top = res["githubCandidates"][0]
            git_url = top.get("gitUrl", "")
            author = top.get("author", "")
            title = top.get("repoName", "")

        # Auto clone if requested
        if auto_clone and git_url and not is_installed:
            clone_res = client.clone_custom_node(git_url)
            if clone_res.get("success"):
                is_installed = True
                installed_path = clone_res.get("installedPath", "")
                if install_deps and installed_path and clone_res.get("hasRequirements"):
                    client.install_node_dependencies(installed_path)

        return (is_installed, git_url, author, title, json.dumps(res, indent=2))


# =============================================================================
# 7. CMM Download Model
# =============================================================================
class CMMDownloadModel:
    """
    Enqueues model download into auto-sorted folders by CivitAI model/version ID.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Manager"
    FUNCTION = "download"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("task_id", "status", "computed_path", "details_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "file_name": ("STRING", {"default": "model.safetensors"}),
                "model_type": (
                    ["Checkpoint", "LORA", "LoCon", "TextualInversion", "VAE", "ControlNet", "Upscaler", "UNET", "CLIP"],
                    {"default": "Checkpoint"},
                ),
                "model_version_id": ("INT", {"default": 0, "min": 0, "max": 100000000}),
            },
            "optional": {
                "base_model": (
                    ["Flux.1 D", "Flux.1 S", "SDXL 1.0", "SD 1.5", "SD 2.1", "Pony", "Illustrious", "LTXV", "WAN", "Other"],
                    {"default": "Flux.1 D"},
                ),
                "creator": ("STRING", {"default": ""}),
                "cmm_port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535}),
            },
        }

    def download(
        self,
        file_name: str,
        model_type: str,
        model_version_id: int,
        base_model: str = "Flux.1 D",
        creator: str = "",
        cmm_port: int = 5174,
    ) -> Tuple[str, str, str, str]:
        client = CMMClient(port=cmm_port)
        res = client.download_model(
            file_name=file_name,
            model_type=model_type,
            model_version_id=model_version_id,
            base_model=base_model,
            creator=creator if creator else None,
        )

        task_id = str(res.get("id", ""))
        status = str(res.get("status", "error" if not task_id else "pending"))
        computed_path = str(res.get("computedPath", ""))

        _send_cmm_event("cmm.download_progress", {
            "task_id": task_id,
            "status": status,
            "fileName": file_name,
            "computedPath": computed_path,
        })

        return (task_id, status, computed_path, json.dumps(res, indent=2))


# =============================================================================
# 8. CMM Search CivitAI
# =============================================================================
class CMMSearchCivitAI:
    """
    Queries CivitAI catalog by query, type, and base model via CMM proxy.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Manager"
    FUNCTION = "search"
    RETURN_TYPES = ("INT", "STRING", "STRING", "INT")
    RETURN_NAMES = ("result_count", "results_json", "top_model_name", "top_version_id")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "query": ("STRING", {"default": ""}),
                "model_type": (["All", "Checkpoint", "LORA", "LoCon", "TextualInversion", "VAE", "ControlNet", "Upscaler", "UNET"], {"default": "All"}),
            },
            "optional": {
                "base_model": (["All", "Flux.1 D", "Flux.1 S", "SDXL 1.0", "SD 1.5", "Pony", "Illustrious", "LTXV", "WAN"], {"default": "All"}),
                "limit": ("INT", {"default": 10, "min": 1, "max": 50}),
                "cmm_port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535}),
            },
        }

    def search(
        self,
        query: str,
        model_type: str = "All",
        base_model: str = "All",
        limit: int = 10,
        cmm_port: int = 5174,
    ) -> Tuple[int, str, str, int]:
        client = CMMClient(port=cmm_port)
        types = None if model_type == "All" else [model_type]
        base_models = None if base_model == "All" else [base_model]

        res = client.search_models(query=query.strip(), types=types, base_models=base_models, limit=limit)
        items = res.get("items", []) if isinstance(res, dict) else []

        top_name = ""
        top_version_id = 0
        if items:
            top = items[0]
            top_name = top.get("name", "")
            versions = top.get("modelVersions") or top.get("versions") or []
            if versions:
                top_version_id = int(versions[0].get("id", 0))

        return (len(items), json.dumps(res, indent=2), top_name, top_version_id)


# =============================================================================
# 9. CMM Search & Queue Download
# =============================================================================
class CMMSearchAndQueue:
    """
    Searches CivitAI and queues top match for download in a single step.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Manager"
    FUNCTION = "search_and_queue"
    RETURN_TYPES = ("STRING", "BOOLEAN", "STRING")
    RETURN_NAMES = ("download_id", "queued", "details_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "search_query": ("STRING", {"default": ""}),
                "model_type": (["Checkpoint", "LORA", "VAE", "CLIP", "UNET"], {"default": "Checkpoint"}),
            },
            "optional": {
                "auto_queue": ("BOOLEAN", {"default": True}),
                "cmm_port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535}),
            },
        }

    def search_and_queue(
        self,
        search_query: str,
        model_type: str = "Checkpoint",
        auto_queue: bool = True,
        cmm_port: int = 5174,
    ) -> Tuple[str, bool, str]:
        cmm = CMMClient(port=cmm_port)
        results = cmm.search_models(query=search_query.strip(), types=[model_type], limit=5)
        items = results.get("items", [])

        if not items:
            return ("", False, json.dumps({"error": "No matching models found", "query": search_query}, indent=2))

        model = items[0]
        versions = model.get("modelVersions") or model.get("versions") or []
        version = versions[0] if versions else None

        if auto_queue and version:
            files = version.get("files", [])
            selected_file = None
            for f in files:
                fname = f.get("name", "")
                if fname.endswith(".safetensors") and f.get("primary", False):
                    selected_file = f
                    break
            if not selected_file:
                for f in files:
                    if f.get("name", "").endswith(".safetensors"):
                        selected_file = f
                        break
            if not selected_file and files:
                selected_file = files[0]

            file_name = selected_file.get("name") if selected_file else f"{model.get('name', 'model')}.safetensors"
            download = cmm.download_model(
                file_name=file_name,
                model_type=model_type,
                model_version_id=version["id"],
                base_model=model.get("baseModel", "Flux.1 D"),
            )
            dl_id = str(download.get("id", ""))
            _send_cmm_event("cmm.download_progress", {
                "task_id": dl_id,
                "status": str(download.get("status", "pending")),
                "fileName": file_name,
                "modelType": model_type,
            })
            return (dl_id, bool(dl_id), json.dumps(download, indent=2))

        return ("", False, json.dumps({"model": model, "queued": False}, indent=2))


# =============================================================================
# 10. CMM Check Hugging Face
# =============================================================================
class CMMCheckHuggingFace:
    """
    Queries Hugging Face model repository files & metadata via CMM bridge.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Manager"
    FUNCTION = "check_repo"
    RETURN_TYPES = ("INT", "STRING", "STRING")
    RETURN_NAMES = ("file_count", "files_json", "repo_id")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "repo_id": ("STRING", {"default": "black-forest-labs/FLUX.1-dev"}),
            },
            "optional": {
                "cmm_port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535}),
            },
        }

    def check_repo(self, repo_id: str, cmm_port: int = 5174) -> Tuple[int, str, str]:
        client = CMMClient(port=cmm_port)
        res = client.check_hf_repo(repo_id.strip())
        files = res.get("files", []) if isinstance(res, dict) else []
        return (len(files), json.dumps(res, indent=2), repo_id)


# =============================================================================
# 11. CMM Raw API Request
# =============================================================================
class CMMRawRequest:
    """
    Low-level generic HTTP caller for advanced CMM API scripting.
    """

    CATEGORY = "☣Renegade Nodes☣/CivitAI/Manager"
    FUNCTION = "call_api"
    RETURN_TYPES = ("STRING", "STRING", "INT", "BOOLEAN")
    RETURN_NAMES = ("response_text", "json_data", "status_code", "success")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "endpoint": ("STRING", {"default": "/api/status"}),
                "method": (["GET", "POST", "PUT", "DELETE"], {"default": "GET"}),
                "payload": ("STRING", {"multiline": True, "default": "{}"}),
            },
            "optional": {
                "timeout": ("INT", {"default": 30, "min": 1, "max": 300}),
                "cmm_port": ("INT", {"default": _get_default_cmm_port(), "min": 1024, "max": 65535}),
            },
        }

    def call_api(
        self,
        endpoint: str,
        method: str,
        payload: str,
        timeout: int = 30,
        cmm_port: int = 5174,
    ) -> Tuple[str, str, int, bool]:
        client = CMMClient(port=cmm_port, timeout=float(timeout))
        resp_text, json_data, status_code = client.raw_request(
            endpoint=endpoint,
            method=method,
            payload=payload,
            timeout=float(timeout),
        )
        success = 200 <= status_code < 300
        return (resp_text, json.dumps(json_data, indent=2), status_code, success)


# =============================================================================
# 12. VRAM Unloader
# =============================================================================
class CMMVRAMUnloader:
    """
    Passthrough node that offloads MODEL, CLIP, and/or VAE from VRAM.
    Three modes: Offload to RAM (CPU), Full Unload, or Aggressive Clear.
    Designed as an inline assist for low-VRAM workflows.
    """

    CATEGORY = "\u2623Renegade Nodes\u2623/CivitAI/Memory"
    FUNCTION = "unload"
    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "status")
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (
                    ["Offload to RAM", "Full Unload", "Aggressive Clear"],
                    {"default": "Offload to RAM"},
                ),
            },
            "optional": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs) -> str:
        """Always re-execute — this node is a side-effect operation."""
        return str(time.time())

    def _offload_to_cpu(self, obj: Any, label: str) -> str:
        """Move a model patcher or raw module to CPU."""
        if obj is None:
            return ""
        try:
            # ModelPatcher style (model.model is the nn.Module)
            inner = getattr(obj, "model", None)
            if inner is not None and hasattr(inner, "to"):
                inner.to("cpu")
                return f"\u2705 {label}: offloaded to RAM\n"
            # Raw nn.Module
            if hasattr(obj, "to"):
                obj.to("cpu")
                return f"\u2705 {label}: offloaded to RAM\n"
        except Exception as e:
            return f"\u26a0\ufe0f {label}: offload failed ({e})\n"
        return ""

    def _full_unload(self, obj: Any, label: str) -> str:
        """Evict model from ComfyUI's loaded model cache."""
        if obj is None:
            return ""
        status = self._offload_to_cpu(obj, label)
        try:
            if hasattr(comfy, "model_management"):
                if hasattr(comfy.model_management, "unload_model_clones"):
                    inner = getattr(obj, "model", obj)
                    comfy.model_management.unload_model_clones(inner)
                    status = f"\u2705 {label}: fully unloaded\n"
        except Exception as e:
            status += f"\u26a0\ufe0f {label}: cache eviction failed ({e})\n"
        return status

    def unload(
        self,
        mode: str = "Offload to RAM",
        model: Any = None,
        clip: Any = None,
        vae: Any = None,
    ) -> Tuple[Any, Any, Any, str]:
        report = [f"=== VRAM Unloader ({mode}) ==="]

        targets = [(model, "MODEL"), (clip, "CLIP"), (vae, "VAE")]

        if mode == "Offload to RAM":
            for obj, label in targets:
                line = self._offload_to_cpu(obj, label)
                if line:
                    report.append(line.strip())

        elif mode == "Full Unload":
            for obj, label in targets:
                line = self._full_unload(obj, label)
                if line:
                    report.append(line.strip())
            try:
                if hasattr(comfy, "model_management") and hasattr(comfy.model_management, "soft_empty_cache"):
                    comfy.model_management.soft_empty_cache()
                    report.append("\U0001f9f9 CUDA cache cleared")
            except Exception:
                pass

        elif mode == "Aggressive Clear":
            for obj, label in targets:
                line = self._full_unload(obj, label)
                if line:
                    report.append(line.strip())
            try:
                if hasattr(comfy, "model_management"):
                    if hasattr(comfy.model_management, "unload_all_models"):
                        comfy.model_management.unload_all_models()
                    if hasattr(comfy.model_management, "soft_empty_cache"):
                        comfy.model_management.soft_empty_cache()
            except Exception:
                pass
            gc.collect()
            if torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
            report.append("\U0001f4a5 Aggressive clear complete (gc + CUDA cache purged)")

        if len(report) == 1:
            report.append("No models were connected.")

        status = "\n".join(report)
        logger.info(status)
        _send_cmm_event("cmm.vram_unload", {"mode": mode, "status": status})

        return (model, clip, vae, status)


# =============================================================================
# 13. VRAM Reloader
# =============================================================================
class CMMVRAMReloader:
    """
    Passthrough node that reloads MODEL, CLIP, and/or VAE back onto the GPU.
    Respects ComfyUI's memory management and partial-loading budget.
    """

    CATEGORY = "\u2623Renegade Nodes\u2623/CivitAI/Memory"
    FUNCTION = "reload"
    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "status")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs) -> str:
        """Always re-execute — this node is a side-effect operation."""
        return str(time.time())

    def _get_device(self) -> str:
        """Determine the target GPU device."""
        try:
            if hasattr(comfy, "model_management") and hasattr(comfy.model_management, "get_torch_device"):
                return comfy.model_management.get_torch_device()
        except Exception:
            pass
        if torch is not None and torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _reload_to_gpu(self, obj: Any, label: str) -> str:
        """Load a model back onto GPU via ComfyUI's managed loader or manual .to()."""
        if obj is None:
            return ""
        try:
            # Prefer ComfyUI's managed loading (respects VRAM budget)
            if hasattr(comfy, "model_management") and hasattr(comfy.model_management, "load_model_gpu"):
                comfy.model_management.load_model_gpu(obj)
                return f"\u2705 {label}: reloaded to GPU (managed)\n"
        except Exception:
            pass

        # Fallback: manual device transfer
        device = self._get_device()
        try:
            inner = getattr(obj, "model", None)
            if inner is not None and hasattr(inner, "to"):
                inner.to(device)
                return f"\u2705 {label}: reloaded to {device} (manual)\n"
            if hasattr(obj, "to"):
                obj.to(device)
                return f"\u2705 {label}: reloaded to {device} (manual)\n"
        except Exception as e:
            return f"\u26a0\ufe0f {label}: reload failed ({e})\n"
        return ""

    def reload(
        self,
        model: Any = None,
        clip: Any = None,
        vae: Any = None,
    ) -> Tuple[Any, Any, Any, str]:
        report = ["=== VRAM Reloader ==="]

        for obj, label in [(model, "MODEL"), (clip, "CLIP"), (vae, "VAE")]:
            line = self._reload_to_gpu(obj, label)
            if line:
                report.append(line.strip())

        if len(report) == 1:
            report.append("No models were connected.")

        status = "\n".join(report)
        logger.info(status)
        _send_cmm_event("cmm.vram_reload", {"status": status})

        return (model, clip, vae, status)
