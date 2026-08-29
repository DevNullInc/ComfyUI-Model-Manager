"""
CivitAI Model Manager - ComfyUI Companion Node
Copyright (C) 2025-2026 TheStygianRenegade / /dev/null Inc
Licensed under GNU General Public License v3.0 (GPL-3.0)

Unit tests for ComfyUI-Model-Manager Custom Nodes and Registration
"""

import json
import unittest
from unittest.mock import MagicMock, patch

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
import __init__ as cmm_init


class TestCMMNodes(unittest.TestCase):
    def test_registration_mappings(self):
        """Verify all custom nodes are properly exported in __init__.py."""
        expected_nodes = [
            "SmartModelLoader",
            "PipeUnpackModel",
            "CMMStatus",
            "CMMInspectWorkflow",
            "CMMWorkflowResolver",
            "CMMResolveNode",
            "CMMDownloadModel",
            "CMMSearchCivitAI",
            "CMMSearchAndQueue",
            "CMMCheckHuggingFace",
            "CMMRawRequest",
        ]
        for node_name in expected_nodes:
            self.assertIn(node_name, cmm_init.NODE_CLASS_MAPPINGS)
            self.assertIn(node_name, cmm_init.NODE_DISPLAY_NAME_MAPPINGS)
        self.assertEqual(cmm_init.WEB_DIRECTORY, "./web/js")

    def test_model_bundle_datatype(self):
        """Verify MODEL_BUNDLE tuple behavior and property access."""
        dummy_model = {"type": "fake_model"}
        dummy_clip = {"type": "fake_clip"}
        dummy_vae = {"type": "fake_vae"}
        metadata = {"civitai_id": 12345, "base_model": "FLUX"}

        bundle = MODEL_BUNDLE(
            model=dummy_model,
            clip=dummy_clip,
            vae=dummy_vae,
            model_type="FLUX",
            metadata=metadata,
        )

        self.assertIsInstance(bundle, tuple)
        self.assertEqual(len(bundle), 5)
        self.assertEqual(bundle.model, dummy_model)
        self.assertEqual(bundle.clip, dummy_clip)
        self.assertEqual(bundle.vae, dummy_vae)
        self.assertEqual(bundle.model_type, "FLUX")
        self.assertEqual(bundle.metadata, metadata)

        # Tuple unpacking test
        m, c, v, m_type, meta = bundle
        self.assertEqual(m, dummy_model)
        self.assertEqual(m_type, "FLUX")
        self.assertEqual(meta["civitai_id"], 12345)

    def test_smart_loader_architecture_detection(self):
        """Verify detect_model_type logic for various models."""
        loader = SmartModelLoader()

        # Metadata baseModel overrides
        self.assertEqual(loader.detect_model_type("random_file.safetensors", {"baseModel": "Flux.1 D"}), "FLUX")
        self.assertEqual(loader.detect_model_type("random_file.safetensors", {"baseModel": "SDXL 1.0"}), "SDXL")
        self.assertEqual(loader.detect_model_type("random_file.safetensors", {"baseModel": "Pony"}), "SDXL")
        self.assertEqual(loader.detect_model_type("random_file.safetensors", {"baseModel": "SD 1.5"}), "SD1.5")
        self.assertEqual(loader.detect_model_type("random_file.safetensors", {"baseModel": "LTXV"}), "LTX")
        self.assertEqual(loader.detect_model_type("random_file.safetensors", {"baseModel": "WAN"}), "WAN")

        # Filename fallbacks
        self.assertEqual(loader.detect_model_type("flux1-dev.safetensors", {}), "FLUX")
        self.assertEqual(loader.detect_model_type("juggernautXL_v9.safetensors", {}), "SDXL")
        self.assertEqual(loader.detect_model_type("wan2.1_i2v.safetensors", {}), "WAN")
        self.assertEqual(loader.detect_model_type("ltx-video-2b.safetensors", {}), "LTX")
        self.assertEqual(loader.detect_model_type("v1-5-pruned.safetensors", {}), "SD1.5")
        self.assertEqual(loader.detect_model_type("unknown_model.safetensors", {}), "Standard SD")

    @patch.object(SmartModelLoader, "detect_model_type", return_value="FLUX")
    def test_smart_loader_execution(self, mock_detect):
        """Test load_model execution and output packing."""
        loader = SmartModelLoader()
        pipe, model, clip, vae, info_str = loader.load_model(
            checkpoint="flux1-dev.safetensors",
            loader_mode="AUTO",
            clip_source="Baked In",
            vae_source="Baked In",
            check_cmm=False,
        )

        self.assertIsInstance(pipe, MODEL_BUNDLE)
        self.assertEqual(pipe.model_type, "FLUX")
        info = json.loads(info_str)
        self.assertEqual(info["model_type"], "FLUX")
        self.assertEqual(info["checkpoint"], "flux1-dev.safetensors")

    def test_pipe_unpacker(self):
        """Test PipeUnpackModel unpacking and overrides."""
        unpacker = PipeUnpackModel()
        bundle = MODEL_BUNDLE(
            model="orig_model",
            clip="orig_clip",
            vae="orig_vae",
            model_type="SDXL",
            metadata={"test": "data"},
        )

        # Standard unpack
        m, c, v, m_type, meta_str = unpacker.unpack(bundle)
        self.assertEqual(m, "orig_model")
        self.assertEqual(c, "orig_clip")
        self.assertEqual(v, "orig_vae")
        self.assertEqual(m_type, "SDXL")
        self.assertIn("test", json.loads(meta_str))

        # Unpack with overrides
        m, c, v, m_type, _ = unpacker.unpack(bundle, override_clip="new_clip", override_vae="new_vae")
        self.assertEqual(m, "orig_model")
        self.assertEqual(c, "new_clip")
        self.assertEqual(v, "new_vae")

    @patch("cmm_client.CMMClient.is_online", return_value=True)
    @patch("cmm_client.CMMClient.get_status", return_value={"version": "1.3.0", "status": "online"})
    @patch("cmm_client.CMMClient.get_health", return_value={"status": "ok", "uptime": 300})
    def test_cmm_status_node(self, mock_health, mock_status, mock_online):
        node = CMMStatus()
        online, text, version, details_str = node.check_status(cmm_port=5174)

        self.assertTrue(online)
        self.assertEqual(text, "Online")
        self.assertEqual(version, "1.3.0")
        self.assertIn("online", json.loads(details_str))

    @patch("cmm_client.CMMClient.parse_workflow")
    @patch("cmm_client.CMMClient.resolve_missing_node")
    def test_cmm_inspect_workflow(self, mock_resolve, mock_parse):
        mock_parse.return_value = {
            "models": [{"modelName": "flux.safetensors", "isInstalled": False}],
            "nodeTypes": ["MissingNodeA"],
        }
        mock_resolve.return_value = {"isInstalled": False}

        node = CMMInspectWorkflow()
        m_count, n_count, missing_m, missing_n, _ = node.inspect_workflow(workflow_json='{"nodes": []}')

        self.assertEqual(m_count, 1)
        self.assertEqual(n_count, 1)
        self.assertIn("flux.safetensors", missing_m)
        self.assertIn("MissingNodeA", missing_n)

    @patch("cmm_client.CMMClient.parse_workflow")
    @patch("cmm_client.CMMClient.resolve_missing_node")
    @patch("cmm_client.CMMClient.clone_custom_node")
    def test_cmm_workflow_resolver(self, mock_clone, mock_resolve, mock_parse):
        mock_parse.return_value = {
            "models": [],
            "nodeTypes": ["ImpactPackNode"],
        }
        mock_resolve.return_value = {
            "isInstalled": False,
            "registryMatch": {"gitUrl": "https://github.com/ltdrdata/ComfyUI-Impact-Pack.git"},
        }
        mock_clone.return_value = {"success": True}

        resolver = CMMWorkflowResolver()
        status_json, report, all_resolved = resolver.resolve(
            resolve_nodes=True,
            resolve_models=True,
            auto_clone=True,
            auto_download=False,
            prompt={},
        )

        self.assertTrue(all_resolved)
        self.assertIn("Auto-Cloned", report)

    @patch("cmm_client.CMMClient.resolve_missing_node")
    def test_cmm_resolve_node(self, mock_resolve):
        mock_resolve.return_value = {
            "isInstalled": True,
            "registryMatch": {
                "author": "ltdrdata",
                "title": "Impact Pack",
                "gitUrl": "https://github.com/ltdrdata/ComfyUI-Impact-Pack.git",
            },
        }
        node = CMMResolveNode()
        is_inst, git_url, author, title, _ = node.resolve_node("ImpactWildcardProcessor")
        self.assertTrue(is_inst)
        self.assertEqual(author, "ltdrdata")
        self.assertEqual(git_url, "https://github.com/ltdrdata/ComfyUI-Impact-Pack.git")

    @patch("cmm_client.CMMClient.download_model")
    def test_cmm_download_model(self, mock_dl):
        mock_dl.return_value = {
            "id": "dl-12345",
            "status": "pending",
            "computedPath": "/models/checkpoints/flux1-dev.safetensors",
        }
        node = CMMDownloadModel()
        task_id, status, path, _ = node.download(
            file_name="flux1-dev.safetensors",
            model_type="Checkpoint",
            model_version_id=691639,
        )
        self.assertEqual(task_id, "dl-12345")
        self.assertEqual(status, "pending")

    @patch("cmm_client.CMMClient.search_models")
    def test_cmm_search_civitai(self, mock_search):
        mock_search.return_value = {
            "items": [
                {"name": "FLUX LoRA", "versions": [{"id": 4567}]}
            ]
        }
        node = CMMSearchCivitAI()
        count, _, top_name, top_version = node.search("FLUX LoRA")
        self.assertEqual(count, 1)
        self.assertEqual(top_name, "FLUX LoRA")
        self.assertEqual(top_version, 4567)

    @patch("cmm_client.CMMClient.search_models")
    @patch("cmm_client.CMMClient.download_model")
    def test_cmm_search_and_queue(self, mock_dl, mock_search):
        mock_search.return_value = {
            "items": [
                {"name": "Realism LORA", "versions": [{"id": 789, "files": [{"name": "realism.safetensors"}]}]}
            ]
        }
        mock_dl.return_value = {"id": "dl-queue-1"}

        node = CMMSearchAndQueue()
        dl_id, queued, _ = node.search_and_queue("Realism LORA", auto_queue=True)
        self.assertEqual(dl_id, "dl-queue-1")
        self.assertTrue(queued)

    @patch("cmm_client.CMMClient.check_hf_repo")
    def test_cmm_check_hf(self, mock_hf):
        mock_hf.return_value = {
            "repoId": "black-forest-labs/FLUX.1-dev",
            "files": ["flux1-dev.safetensors"],
        }
        node = CMMCheckHuggingFace()
        count, files_json, repo = node.check_repo("black-forest-labs/FLUX.1-dev")
        self.assertEqual(count, 1)
        self.assertEqual(repo, "black-forest-labs/FLUX.1-dev")

    @patch("cmm_client.CMMClient.raw_request")
    def test_cmm_raw_request(self, mock_raw):
        mock_raw.return_value = ('{"ok": true}', {"ok": True}, 200)
        node = CMMRawRequest()
        resp_text, json_str, code, ok = node.call_api("/api/status", "GET", "{}")
        self.assertEqual(code, 200)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
