# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## Reporting a Vulnerability

**Please do not open public issues for security vulnerabilities.**

Instead, report security concerns privately:

- **Email**: `bug-report@renegadeinc.net` with subject line: `[ComfyUI-Model-Manager] Security Issue`
- **GitHub**: Use GitHub's [Private Vulnerability Reporting](https://github.com/DevNullInc/ComfyUI-Model-Manager/security/advisories/new) feature on this repository

### What to Include in Your Report
- Description and classification of the vulnerability
- Detailed step-by-step reproduction steps or minimal proof-of-concept workflow
- Potential impact assessment (e.g., unauthorized local file access, command injection, remote code execution)
- Environment details (OS, Python version, ComfyUI release / commit hash, CMM version)

### Response Timeline
- **Acknowledgment**: Within 48 hours
- **Initial Assessment & Triage**: Within 7 business days
- **Fix & Patch Release**: Typically within 14–30 days depending on severity
- **Coordinated Public Disclosure**: Once a security patch is released and users have had reasonable time to update

---

## Security Scope

### In Scope
- Local HTTP communication between custom nodes and the CivitAI Model Manager bridge (`127.0.0.1:<port>`).
- Custom node cloning and Python dependency installation triggers (`CMMResolveNode`, `CMMWorkflowResolver`).
- In-memory workflow inspection, prompt parsing, and deserialization routines.
- `MODEL_BUNDLE` pipe metadata handling.

### Out of Scope
- Vulnerabilities in upstream ComfyUI core (please report directly to [ComfyUI](https://github.com/comfyanonymous/ComfyUI/security)).
- CivitAI API platform or infrastructure vulnerabilities (please report directly to [CivitAI](https://civitai.com)).
- Vulnerabilities within the CivitAI Model Manager desktop application itself (please report to [Civitai-manager-ComfyUI](https://github.com/DevNullInc/Civitai-manager-ComfyUI/security)).
- Malicious third-party custom nodes cloned from arbitrary untrusted external URLs without verification.
