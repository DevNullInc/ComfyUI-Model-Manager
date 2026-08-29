"""
CivitAI Model Manager - ComfyUI Companion Node
Copyright (C) 2025-2026 TheStygianRenegade / /dev/null Inc
Licensed under GNU General Public License v3.0 (GPL-3.0)

Unit tests for CMMClient HTTP Client Layer
"""

import json
import unittest
from unittest.mock import MagicMock, patch
import requests

from cmm_client import CMMClient


class TestCMMClient(unittest.TestCase):
    def setUp(self):
        self.client = CMMClient(port=5174)

    def test_default_url(self):
        self.assertEqual(self.client.base_url, "http://127.0.0.1:5174")

    def test_custom_port(self):
        custom_client = CMMClient(port=5175)
        self.assertEqual(custom_client.base_url, "http://127.0.0.1:5175")

    def test_custom_base_url(self):
        custom_client = CMMClient(base_url="http://localhost:8080/")
        self.assertEqual(custom_client.base_url, "http://localhost:8080")

    @patch("requests.Session.request")
    def test_is_online_true(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"status": "ok", "uptime": 120}
        mock_request.return_value = mock_resp

        self.assertTrue(self.client.is_online())

    @patch("requests.Session.request")
    def test_is_online_offline_on_connection_error(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")
        self.assertFalse(self.client.is_online())

    @patch("requests.Session.request")
    def test_get_status(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "status": "online",
            "enabled": True,
            "version": "1.3.0",
            "port": 5174,
        }
        mock_request.return_value = mock_resp

        status = self.client.get_status()
        self.assertEqual(status.get("status"), "online")
        self.assertEqual(status.get("version"), "1.3.0")

    @patch("requests.Session.request")
    def test_parse_workflow(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "fileName": "test.json",
            "models": [{"nodeId": "4", "modelName": "flux1-dev.safetensors", "isInstalled": True}],
            "nodeTypes": ["CheckpointLoaderSimple"],
        }
        mock_request.return_value = mock_resp

        analysis = self.client.parse_workflow(workflow_data={"nodes": []})
        self.assertEqual(len(analysis["models"]), 1)
        self.assertEqual(analysis["models"][0]["modelName"], "flux1-dev.safetensors")

    @patch("requests.Session.request")
    def test_resolve_missing_node(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "nodeType": "ImpactWildcardProcessor",
            "isInstalled": True,
            "registryMatch": {
                "author": "ltdrdata",
                "gitUrl": "https://github.com/ltdrdata/ComfyUI-Impact-Pack.git",
            },
        }
        mock_request.return_value = mock_resp

        res = self.client.resolve_missing_node("ImpactWildcardProcessor")
        self.assertTrue(res["isInstalled"])
        self.assertEqual(res["registryMatch"]["author"], "ltdrdata")

    @patch("requests.Session.request")
    def test_clone_custom_node(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "success": True,
            "installedPath": "/path/to/custom_nodes/ComfyUI-Impact-Pack",
            "hasRequirements": True,
        }
        mock_request.return_value = mock_resp

        res = self.client.clone_custom_node("https://github.com/ltdrdata/ComfyUI-Impact-Pack.git")
        self.assertTrue(res["success"])
        self.assertTrue(res["hasRequirements"])

    @patch("requests.Session.request")
    def test_download_model(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "id": "dl-uuid-999",
            "fileName": "flux1-dev.safetensors",
            "status": "pending",
            "computedPath": "/models/checkpoints/flux1-dev.safetensors",
        }
        mock_request.return_value = mock_resp

        dl = self.client.download_model(
            file_name="flux1-dev",
            model_type="Checkpoint",
            model_version_id=691639,
            base_model="Flux.1 D",
        )
        self.assertEqual(dl["id"], "dl-uuid-999")
        self.assertEqual(dl["status"], "pending")

    @patch("requests.Session.request")
    def test_search_models(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "items": [
                {"id": 1, "name": "Realism Model", "versions": [{"id": 101, "files": [{"name": "realism.safetensors"}]}]}
            ]
        }
        mock_request.return_value = mock_resp

        res = self.client.search_models("realism", types=["LORA"])
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["name"], "Realism Model")

    @patch("requests.Session.request")
    def test_check_hf_repo(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "repoId": "black-forest-labs/FLUX.1-dev",
            "files": ["flux1-dev.safetensors", "ae.safetensors"],
        }
        mock_request.return_value = mock_resp

        res = self.client.check_hf_repo("black-forest-labs/FLUX.1-dev")
        self.assertEqual(len(res["files"]), 2)

    @patch("requests.Session.request")
    def test_raw_request(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"custom": "data"}
        mock_resp.text = '{"custom": "data"}'
        mock_request.return_value = mock_resp

        text, data, code = self.client.raw_request("/api/custom", method="POST", payload='{"test": 1}')
        self.assertEqual(code, 200)
        self.assertEqual(data.get("custom"), "data")


if __name__ == "__main__":
    unittest.main()
