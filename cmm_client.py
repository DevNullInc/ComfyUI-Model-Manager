"""
CivitAI Model Manager - ComfyUI Companion Node
Copyright (C) 2025-2026 TheStygianRenegade / /dev/null Inc
Licensed under GNU General Public License v3.0 (GPL-3.0)

CivitAI Model Manager (CMM) API Client
Provides HTTP communication with the local Electron bridge.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import json
import logging
import requests

logger = logging.getLogger("ComfyUI-Model-Manager")


class CMMClient:
    """
    Client helper for ComfyUI custom nodes connecting to CivitAI Model Manager.
    Automatically defaults to port 5174 (127.0.0.1:5174).
    """

    def __init__(self, port: int = 5174, base_url: Optional[str] = None, timeout: float = 10.0):
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = f"http://127.0.0.1:{port or 5174}"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # -------------------------------------------------------------------------
    # Internal Request Helpers
    # -------------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[bool, Any, int, str]:
        """
        Executes an HTTP request against the CMM bridge.
        Returns (success: bool, data: Any, status_code: int, error_message: str).
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        req_timeout = timeout or self.timeout
        try:
            res = self.session.request(
                method=method.upper(),
                url=url,
                json=json_data if json_data is not None else None,
                params=params,
                timeout=req_timeout,
            )
            content_type = res.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    data = res.json()
                except Exception:
                    data = res.text
            else:
                data = res.text

            is_ok = 200 <= res.status_code < 300
            err_msg = "" if is_ok else f"HTTP {res.status_code}: {res.text}"
            return is_ok, data, res.status_code, err_msg
        except requests.exceptions.ConnectionError:
            err = f"Could not connect to CivitAI Model Manager at {self.base_url}. Ensure CMM is running and API Bridge is enabled in Settings."
            logger.debug(err)
            return False, {"error": err}, 0, err
        except requests.exceptions.Timeout:
            err = f"Request to {url} timed out after {req_timeout}s."
            logger.debug(err)
            return False, {"error": err}, 0, err
        except Exception as e:
            err = f"CMM request error: {str(e)}"
            logger.debug(err)
            return False, {"error": err}, 0, err

    # -------------------------------------------------------------------------
    # 1. Health & Server Status
    # -------------------------------------------------------------------------
    def is_online(self) -> bool:
        """Verify if CivitAI Model Manager is running and the API Bridge is reachable."""
        ok, data, code, _ = self._request("GET", "/api/health", timeout=2.0)
        if ok and isinstance(data, dict) and data.get("status") == "ok":
            return True
        # Fallback check status endpoint
        ok, data, code, _ = self._request("GET", "/api/status", timeout=2.0)
        return ok and isinstance(data, dict) and data.get("status") in ("online", "ok")

    def get_health(self) -> Dict[str, Any]:
        """Fetch heartbeat status and process uptime."""
        ok, data, _, err = self._request("GET", "/api/health")
        return data if (ok and isinstance(data, dict)) else {"status": "offline", "error": err}

    def get_status(self) -> Dict[str, Any]:
        """Fetch bridge status, enabled flag, app version, and port."""
        ok, data, _, err = self._request("GET", "/api/status")
        return data if (ok and isinstance(data, dict)) else {"status": "offline", "enabled": False, "error": err}

    # -------------------------------------------------------------------------
    # 2. Workflow Inspection & In-Memory Parsing
    # -------------------------------------------------------------------------
    def parse_workflow(
        self,
        workflow_data: Optional[Dict[str, Any]] = None,
        name: str = "workflow.json",
        prompt: Optional[Dict[str, Any]] = None,
        folder_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Inspect a raw workflow, prompt dictionary, or disk folders to detect missing models & nodes.
        """
        payload: Dict[str, Any] = {}
        if workflow_data is not None:
            payload["workflow"] = workflow_data
            payload["name"] = name
        elif prompt is not None:
            payload["prompt"] = prompt
            payload["name"] = name
        elif folder_paths is not None:
            payload["folderPaths"] = folder_paths
        else:
            payload["workflow"] = {}
            payload["name"] = name

        ok, data, _, err = self._request("POST", "/api/workflows", json_data=payload)
        return data if (ok and isinstance(data, dict)) else {"error": err, "models": [], "nodeTypes": []}

    # -------------------------------------------------------------------------
    # 3. Custom Node Dependency Resolution (4-Tier Engine)
    # -------------------------------------------------------------------------
    def resolve_missing_node(self, node_type: str) -> Dict[str, Any]:
        """Query 4-tier resolution engine (Local -> SQLite Cache -> GitHub) for missing custom node."""
        ok, data, _, err = self._request("POST", "/api/nodes/resolve", json_data={"nodeType": node_type})
        return data if (ok and isinstance(data, dict)) else {"nodeType": node_type, "isInstalled": False, "error": err}

    def search_github(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Performs scoped search on GitHub for ComfyUI custom node repositories."""
        ok, data, _, err = self._request("POST", "/api/nodes/search-github", json_data={"query": query, "limit": limit})
        return data if (ok and isinstance(data, dict)) else {"query": query, "candidates": [], "error": err}

    def clone_custom_node(self, git_url: str, folder_name: Optional[str] = None) -> Dict[str, Any]:
        """Clone a custom node Git repository into ComfyUI's custom_nodes/ directory."""
        payload = {"gitUrl": git_url}
        if folder_name:
            payload["folderName"] = folder_name
        ok, data, _, err = self._request("POST", "/api/nodes/clone", json_data=payload, timeout=60.0)
        return data if (ok and isinstance(data, dict)) else {"success": False, "error": err}

    def install_node_dependencies(self, folder_path: str) -> Dict[str, Any]:
        """Execute pip install on requirements.txt using ComfyUI's specific Python runtime."""
        ok, data, _, err = self._request("POST", "/api/nodes/install-deps", json_data={"folderPath": folder_path}, timeout=120.0)
        return data if (ok and isinstance(data, dict)) else {"success": False, "error": err}

    def get_installed_nodes(self) -> List[Dict[str, Any]]:
        """Fetch all installed custom node packages and git remotes."""
        ok, data, _, _ = self._request("GET", "/api/nodes/installed")
        return data if (ok and isinstance(data, list)) else []

    # -------------------------------------------------------------------------
    # 4. Local Library & Model Queries
    # -------------------------------------------------------------------------
    def get_local_models(self) -> List[Dict[str, Any]]:
        """Returns all indexed models from local SQLite with metadata, type, and file paths."""
        ok, data, _, _ = self._request("GET", "/api/local-models")
        return data if (ok and isinstance(data, list)) else []

    def scan_library(self, root_path: Optional[str] = None) -> Dict[str, Any]:
        """Initiates an asynchronous background scan of a specified models directory."""
        payload = {"rootPath": root_path} if root_path else {}
        ok, data, _, err = self._request("POST", "/api/scan-library", json_data=payload)
        return data if (ok and isinstance(data, dict)) else {"error": err}

    def get_scan_status(self) -> Dict[str, Any]:
        """Returns active library scanning state and progress."""
        ok, data, _, err = self._request("GET", "/api/get-scan-status")
        return data if (ok and isinstance(data, dict)) else {"isScanning": False, "progress": 0, "error": err}

    def cancel_scan(self) -> Dict[str, Any]:
        """Cancels any active library scan."""
        ok, data, _, err = self._request("POST", "/api/cancel-scan")
        return data if (ok and isinstance(data, dict)) else {"error": err}

    def clear_library(self) -> Dict[str, Any]:
        """Clears local SQLite model table and thumbnail cache."""
        ok, data, _, err = self._request("POST", "/api/clear-library")
        return data if (ok and isinstance(data, dict)) else {"error": err}

    def match_unidentified_models(self) -> Dict[str, Any]:
        """Attempts hash-based automatic CivitAI metadata lookup for unmatched local files."""
        ok, data, _, err = self._request("POST", "/api/match-unidentified-models")
        return data if (ok and isinstance(data, dict)) else {"error": err}

    # -------------------------------------------------------------------------
    # 5. CivitAI Queries & Downloads
    # -------------------------------------------------------------------------
    def search_models(
        self,
        query: str = "",
        types: Optional[List[str]] = None,
        base_models: Optional[List[str]] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Search CivitAI models via CMM's caching proxy."""
        payload: Dict[str, Any] = {"query": query, "limit": limit}
        if types:
            payload["types"] = types
        if base_models:
            payload["baseModels"] = base_models
        ok, data, _, err = self._request("POST", "/api/search-models", json_data=payload)
        if ok and isinstance(data, dict):
            return data
        if ok and isinstance(data, list):
            return {"items": data}
        return {"items": [], "error": err}

    def get_model(self, model_id: int) -> Dict[str, Any]:
        """Fetches CivitAI model details by model ID."""
        ok, data, _, err = self._request("GET", f"/api/model/{model_id}")
        return data if (ok and isinstance(data, dict)) else {"error": err}

    def get_version(self, version_id: int) -> Dict[str, Any]:
        """Fetches CivitAI version details and download URLs."""
        ok, data, _, err = self._request("GET", f"/api/version/{version_id}")
        return data if (ok and isinstance(data, dict)) else {"error": err}

    def get_enums(self) -> Dict[str, Any]:
        """Fetches valid model types and base model categories."""
        ok, data, _, err = self._request("GET", "/api/enums")
        return data if (ok and isinstance(data, dict)) else {"types": [], "baseModels": [], "error": err}

    def download_model(
        self,
        file_name: str,
        model_type: str,
        model_version_id: int,
        base_model: str = "SDXL 1.0",
        creator: Optional[str] = None,
        target_root: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Queue a model for automatic download and subfolder routing."""
        clean_file_name = file_name if "." in file_name else f"{file_name}.safetensors"
        payload = {
            "fileName": clean_file_name,
            "modelType": model_type,
            "baseModel": base_model,
            "creator": creator,
            "modelVersionId": model_version_id,
        }
        if target_root:
            payload["targetRoot"] = target_root

        ok, data, _, err = self._request("POST", "/api/add-download", json_data=payload)
        return data if (ok and isinstance(data, dict)) else {"success": False, "error": err}

    def get_downloads(self) -> List[Dict[str, Any]]:
        """Returns the list of all download tasks with progress, speed, and status."""
        ok, data, _, _ = self._request("GET", "/api/downloads")
        return data if (ok and isinstance(data, list)) else []

    def pause_download(self, task_id: str) -> Dict[str, Any]:
        """Pauses a download task."""
        ok, data, _, err = self._request("POST", "/api/pause-download", json_data={"id": task_id})
        return data if (ok and isinstance(data, dict)) else {"error": err}

    def resume_download(self, task_id: str) -> Dict[str, Any]:
        """Resumes a paused download task."""
        ok, data, _, err = self._request("POST", "/api/resume-download", json_data={"id": task_id})
        return data if (ok and isinstance(data, dict)) else {"error": err}

    def cancel_download(self, task_id: str) -> Dict[str, Any]:
        """Cancels a download task."""
        ok, data, _, err = self._request("POST", "/api/cancel-download", json_data={"id": task_id})
        return data if (ok and isinstance(data, dict)) else {"error": err}

    def force_complete_download(self, task_id: str) -> Dict[str, Any]:
        """Marks a download task as complete."""
        ok, data, _, err = self._request("POST", "/api/force-complete-download", json_data={"id": task_id})
        return data if (ok and isinstance(data, dict)) else {"error": err}

    # -------------------------------------------------------------------------
    # 6. Hugging Face Integration
    # -------------------------------------------------------------------------
    def check_hf_repo(self, repo_id: str) -> Dict[str, Any]:
        """Inspects a Hugging Face repository and returns file lists, sizes, and safetensors metadata."""
        ok, data, _, err = self._request("POST", "/api/hf/check", json_data={"repoId": repo_id})
        return data if (ok and isinstance(data, dict)) else {"repoId": repo_id, "files": [], "error": err}

    def whoami_hf(self) -> Dict[str, Any]:
        """Returns Hugging Face login authorization state."""
        ok, data, _, err = self._request("GET", "/api/hf/whoami")
        return data if (ok and isinstance(data, dict)) else {"loggedIn": False, "error": err}

    def validate_hf_token(self, token: str) -> Dict[str, Any]:
        """Validates a Hugging Face User Access Token."""
        ok, data, _, err = self._request("POST", "/api/hf/validate-token", json_data={"token": token})
        return data if (ok and isinstance(data, dict)) else {"valid": False, "error": err}

    # -------------------------------------------------------------------------
    # 7. Configuration & Backups
    # -------------------------------------------------------------------------
    def get_config(self) -> Dict[str, Any]:
        """Retrieves app configuration, folder paths, and sorting preferences."""
        ok, data, _, err = self._request("GET", "/api/config")
        return data if (ok and isinstance(data, dict)) else {"error": err}

    def save_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Updates application configuration parameters."""
        ok, data, _, err = self._request("POST", "/api/save-config", json_data=config)
        return data if (ok and isinstance(data, dict)) else {"error": err}

    # -------------------------------------------------------------------------
    # 8. Webhooks & Integrations
    # -------------------------------------------------------------------------
    def test_webhook(self, url: str, event: str = "ping") -> Dict[str, Any]:
        """Dispatches a test event to verify custom webhook URLs."""
        ok, data, _, err = self._request("POST", "/api/webhooks/test", json_data={"url": url, "event": event})
        return data if (ok and isinstance(data, dict)) else {"error": err}

    # -------------------------------------------------------------------------
    # Generic Raw Request
    # -------------------------------------------------------------------------
    def raw_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: Optional[Union[Dict[str, Any], str]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[str, Dict[str, Any], int]:
        """
        Executes a raw request for generic / dynamic node calls.
        Returns (response_text, json_data, status_code).
        """
        json_data = None
        if payload:
            if isinstance(payload, str):
                try:
                    json_data = json.loads(payload)
                except Exception:
                    json_data = None
            elif isinstance(payload, dict):
                json_data = payload

        ok, data, status_code, err = self._request(
            method=method,
            path=endpoint,
            json_data=json_data if method.upper() not in ("GET", "HEAD") else None,
            timeout=timeout,
        )

        if isinstance(data, dict):
            return json.dumps(data, indent=2), data, status_code
        elif isinstance(data, list):
            return json.dumps(data, indent=2), {"items": data}, status_code
        else:
            text = str(data)
            return text, {"raw": text, "error": err} if err else {"raw": text}, status_code
