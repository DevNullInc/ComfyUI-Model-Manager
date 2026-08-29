# ComfyUI-Model-Manager

Native ComfyUI companion custom node suite for **CivitAI Model Manager (CMM)**. Provides unified model loading via the `MODEL_BUNDLE` pipe architecture, in-canvas missing model/node dependency resolution, CivitAI catalog discovery, and real-time HTTP bridge integration.

---

## 🌟 Key Features

- 🚀 **`MODEL_BUNDLE` Smart Model Pipe**: Bundle model, CLIP, VAE, architecture mode, and CMM metadata into a single connection pipe.
- 🧠 **Automatic Architecture Detection**: Intelligently identifies model architecture (`FLUX`, `SDXL`, `SD1.5`, `WAN`, `LTX`, `MiniMaxH3`, `Anima`, `Qwen`) via CMM database metadata or filename patterns.
- 🔌 **4-Tier Custom Node Resolver**: Detects missing custom nodes in workflows and auto-clones repositories from registry or GitHub with embedded dependency installation.
- 🔍 **In-Canvas Workflow & Graph Inspection**: Scans active LiteGraph canvas graphs and execution prompts to highlight missing checkpoints, LoRAs, and node classes.
- 📥 **CivitAI Search & Queue Downloads**: Search models directly from ComfyUI and enqueue automatic downloads into subfolders by model type.
- 🌐 **Hugging Face Model Inspection**: Query Hugging Face repositories for `.safetensors` files and metadata.
- ⚡ **Real-Time HTTP API Bridge**: Connects seamlessly to CMM's isolated localhost server (`127.0.0.1:5174`) with live status badges, click-to-refresh diagnostics, and ComfyUI Settings integration.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│             CivitAI Model Manager (Electron)           │
│                 (HTTP Bridge @ 127.0.0.1:5174)         │
└───────────────────────────▲────────────────────────────┘
                            │ HTTP JSON API
┌───────────────────────────▼────────────────────────────┐
│                       cmm_client                       │
│      (Session Connection Pooling & Safe Fallbacks)     │
└───────────────────────────▲────────────────────────────┘
                            │
       ┌────────────────────┴─────────────────────┐
       ▼                                          ▼
┌───────────────────────────┐      ┌─────────────────────────────┐
│  Smart Model Pipe Loaders │      │   CMM Management Nodes      │
├───────────────────────────┤      ├─────────────────────────────┤
│ • SmartModelLoader        │      │ • CMMStatus                 │
│ • PipeUnpackModel         │      │ • CMMInspectWorkflow        │
│ • MODEL_BUNDLE datatype   │      │ • CMMWorkflowResolver       │
└───────────────────────────┘      │ • CMMResolveNode            │
                                   │ • CMMDownloadModel          │
                                   │ • CMMSearchCivitAI          │
                                   │ • CMMSearchAndQueue         │
                                   │ • CMMCheckHuggingFace       │
                                   │ • CMMRawRequest             │
                                   └─────────────────────────────┘
```

---

## 🧩 Node Catalog

### 📦 Loaders (`CivitAI/Loaders`)

| Node | Display Name | Inputs | Outputs | Description |
|---|---|---|---|---|
| `SmartModelLoader` | **CMM: Smart Model Loader** | `checkpoint`, `loader_mode`, `clip_source`, `vae_source`, `check_cmm`, `clip_name`, `vae_name`, `cmm_port` | `pipe` (`MODEL_BUNDLE`), `model`, `clip`, `vae`, `model_info` | Unified model loader with architecture detection and `IS_CHANGED` caching. |
| `PipeUnpackModel` | **CMM: Unpack Model Pipe** | `pipe` (`MODEL_BUNDLE`), `override_clip`, `override_vae` | `model`, `clip`, `vae`, `model_type`, `metadata_json` | Deconstructs a `MODEL_BUNDLE` pipe into individual components with optional overrides. |

### 🛠️ Manager & Diagnostics (`CivitAI/Manager`)

| Node | Display Name | Inputs | Outputs | Description |
|---|---|---|---|---|
| `CMMStatus` | **CMM: Status & Heartbeat** | `cmm_port`, `base_url` | `is_online`, `status_text`, `version`, `details_json` | Verifies connection, API port, and database uptime with CMM. |
| `CMMInspectWorkflow` | **CMM: Inspect Workflow** | `cmm_port`, `workflow_json` | `model_count`, `node_type_count`, `missing_models_list`, `missing_nodes_list`, `details_json` | Scans in-memory canvas graph or prompt dictionary for missing dependencies. |
| `CMMWorkflowResolver` | **CMM: Auto-Resolve Workflow** | `resolve_nodes`, `resolve_models`, `auto_clone`, `auto_download`, `cmm_port` | `status_json`, `resolution_report`, `all_resolved` | Auto-resolves missing nodes and models with 1-click clone and download staging. |
| `CMMResolveNode` | **CMM: Resolve Node** | `node_type`, `auto_clone`, `install_deps`, `cmm_port` | `is_installed`, `git_url`, `author`, `title`, `details_json` | Queries 4-tier engine for missing custom node repositories. |
| `CMMDownloadModel` | **CMM: Download Model** | `file_name`, `model_type`, `model_version_id`, `base_model`, `creator`, `cmm_port` | `task_id`, `status`, `computed_path`, `details_json` | Queues model download into auto-sorted folders by version ID. |
| `CMMSearchCivitAI` | **CMM: Search CivitAI** | `query`, `model_type`, `base_model`, `limit`, `cmm_port` | `result_count`, `results_json`, `top_model_name`, `top_version_id` | Queries CivitAI catalog via CMM caching proxy. |
| `CMMSearchAndQueue` | **CMM: Search & Queue Download** | `search_query`, `model_type`, `auto_queue`, `cmm_port` | `download_id`, `queued`, `details_json` | Searches CivitAI and immediately queues top matching `.safetensors` model. |
| `CMMCheckHuggingFace` | **CMM: Check Hugging Face** | `repo_id`, `cmm_port` | `file_count`, `files_json`, `repo_id` | Queries Hugging Face model repository files and metadata. |
| `CMMRawRequest` | **CMM: Raw API Request** | `endpoint`, `method`, `payload`, `timeout`, `cmm_port` | `response_text`, `json_data`, `status_code`, `success` | Low-level generic HTTP executor for custom scripting against CMM bridge. |

---

## ⚙️ Installation

### Option 1: Git Clone (Manual)

Clone this repository directly into your ComfyUI `custom_nodes` directory:

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/DevNullInc/ComfyUI-Model-Manager.git
```

Restart your ComfyUI server. The nodes will appear under the `CivitAI` category.

### Option 2: ComfyUI Manager / Registry

Search for `ComfyUI-Model-Manager` in the ComfyUI Manager Node list and click **Install**.

---

## 🔧 Configuration

### API Port Selection

CivitAI Model Manager runs its HTTP API bridge on `127.0.0.1:5174` by default.

- **ComfyUI Settings Panel**: Open ComfyUI settings (⚙️) and configure **CivitAI Model Manager API Port** (`CMM.Port`).
- **Environment Variable**: Set `CMM_PORT=5175` or `API_PORT=5175` before launching ComfyUI to adjust the default port across all nodes.
- **Per-Node Override**: All nodes provide an optional `cmm_port` integer input.

---

## 📋 Requirements

- **ComfyUI**: v0.2.0+ (for Nodes 2.0 compatibility)
- **CivitAI Model Manager**: v1.3.0+ (for full API support)
- **Python**: 3.9+

## 🧪 Testing

Run the automated unit test suite from the repository root:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📄 License

Copyright (C) 2025-2026 TheStygianRenegade / /dev/null Inc.

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See [LICENSE](LICENSE) for details.
