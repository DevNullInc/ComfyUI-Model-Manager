"""
CivitAI Model Manager - ComfyUI Companion Node
Copyright (C) 2025-2026 TheStygianRenegade / /dev/null Inc
Licensed under GNU General Public License v3.0 (GPL-3.0)

Custom Datatypes for ComfyUI-Model-Manager
"""

class MODEL_BUNDLE(tuple):
    """
    Bundled model components: (model, clip, vae, model_type, metadata)
    - model: ComfyUI MODEL object
    - clip: ComfyUI CLIP object
    - vae: ComfyUI VAE object (or None if using separate VAE loader)
    - model_type: str identifier ("SD1.5", "SDXL", "FLUX", "WAN", "LTX", "MiniMaxH3", "Anima", "Qwen", etc.)
    - metadata: dict with CMM info (civitai_id, version_id, file_path, base_model, etc.)
    """
    def __new__(cls, model=None, clip=None, vae=None, model_type="Standard SD", metadata=None):
        if metadata is None:
            metadata = {}
        return super().__new__(cls, (model, clip, vae, model_type, metadata))

    @property
    def model(self):
        return self[0]

    @property
    def clip(self):
        return self[1]

    @property
    def vae(self):
        return self[2]

    @property
    def model_type(self):
        return self[3]

    @property
    def metadata(self):
        return self[4]

    def __repr__(self):
        return f"<MODEL_BUNDLE model_type={self.model_type!r} has_model={self.model is not None} has_clip={self.clip is not None} has_vae={self.vae is not None}>"
