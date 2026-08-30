/**
 * CivitAI Model Manager - ComfyUI Companion Node Frontend Extension
 * Copyright (C) 2025-2026 TheStygianRenegade / /dev/null Inc
 * Licensed under GNU General Public License v3.0 (GPL-3.0)
 */

import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "CivitAI.ModelManager.Bridge";
const DEFAULT_CMM_PORT = 5174;

app.registerExtension({
    name: EXTENSION_NAME,

    async setup() {
        console.log("[CivitAI Model Manager] Initializing frontend bridge extension...");

        // Initialize port from settings or default
        this.cmmPort = DEFAULT_CMM_PORT;

        if (app.ui?.settings) {
            try {
                app.ui.settings.addSetting({
                    id: "CMM.Port",
                    name: "CivitAI Model Manager API Port",
                    type: "number",
                    defaultValue: DEFAULT_CMM_PORT,
                    min: 1024,
                    max: 65535,
                    tooltip: "Localhost HTTP API Bridge port configured in CivitAI Model Manager settings",
                    onChange: (newVal) => {
                        this.cmmPort = parseInt(newVal, 10) || DEFAULT_CMM_PORT;
                        this.checkCMMStatus();
                    },
                });
                const savedPort = app.ui.settings.getSettingValue("CMM.Port");
                if (savedPort) {
                    this.cmmPort = parseInt(savedPort, 10) || DEFAULT_CMM_PORT;
                }
            } catch (err) {
                console.debug("[CMM] Settings hook:", err);
            }
        }

        // Periodic heartbeat check for CMM Electron API bridge
        this.checkCMMStatus();
        this.statusInterval = setInterval(() => this.checkCMMStatus(), 30000);

        // Listen for custom server events dispatched by PromptServer
        if (app.api && typeof app.api.addEventListener === "function") {
            this.downloadProgressListener = (event) => {
                const detail = event.detail || {};
                console.log("[CMM Download Progress]", detail);
                if (detail.status === "completed" && app.ui?.notifications?.show) {
                    app.ui.notifications.show({
                        title: "CMM Download Complete",
                        message: detail.fileName || detail.file_name || "Model download completed",
                        type: "success",
                        duration: 5000,
                    });
                }
            };

            this.statusListener = (event) => {
                const detail = event.detail || {};
                console.log("[CMM Status Update]", detail);
                if (typeof detail.is_online === "boolean") {
                    this.isOnline = detail.is_online;
                    this.updateStatusBadge(this.isOnline);
                }
            };

            app.api.addEventListener("cmm.download_progress", this.downloadProgressListener);
            app.api.addEventListener("cmm.status", this.statusListener);
        }
    },

    beforeUnregister() {
        // Prevent memory leaks on reload or unregistration
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }

        if (app.api && typeof app.api.removeEventListener === "function") {
            if (this.downloadProgressListener) {
                app.api.removeEventListener("cmm.download_progress", this.downloadProgressListener);
            }
            if (this.statusListener) {
                app.api.removeEventListener("cmm.status", this.statusListener);
            }
        }

        const badge = document.getElementById("cmm-status-badge");
        if (badge) {
            badge.remove();
        }
    },

    async checkCMMStatus() {
        const port = this.cmmPort || DEFAULT_CMM_PORT;
        const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
        const timeoutId = controller ? setTimeout(() => controller.abort(), 2000) : null;

        try {
            const res = await fetch(`http://127.0.0.1:${port}/api/health`, {
                method: "GET",
                signal: controller ? controller.signal : undefined,
            });
            if (res.ok) {
                const data = await res.json();
                if (data.status === "ok") {
                    this.isOnline = true;
                    this.updateStatusBadge(true);
                    return;
                }
            }
            this.isOnline = false;
            this.updateStatusBadge(false);
        } catch {
            this.isOnline = false;
            this.updateStatusBadge(false);
        } finally {
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
        }
    },

    updateStatusBadge(isOnline) {
        let badge = document.getElementById("cmm-status-badge");
        if (!badge) {
            badge = document.createElement("div");
            badge.id = "cmm-status-badge";
            badge.style.position = "fixed";
            badge.style.right = "12px";
            badge.style.padding = "4px 10px";
            badge.style.borderRadius = "12px";
            badge.style.fontSize = "11px";
            badge.style.fontFamily = "system-ui, -apple-system, sans-serif";
            badge.style.fontWeight = "600";
            badge.style.zIndex = "9999";
            badge.style.display = "flex";
            badge.style.alignItems = "center";
            badge.style.gap = "6px";
            badge.style.boxShadow = "0 2px 8px rgba(0,0,0,0.3)";
            badge.style.transition = "all 0.3s ease";
            badge.style.cursor = "pointer";
            badge.title = "CivitAI Model Manager HTTP Bridge. Click to refresh status.";
            badge.addEventListener("click", () => {
                badge.style.opacity = "0.5";
                badge.style.transform = "scale(0.96)";
                this.checkCMMStatus().finally(() => {
                    badge.style.opacity = "1";
                    badge.style.transform = "scale(1)";
                });
            });
            document.body.appendChild(badge);
        }

        // Avoid collision with other bottom-fixed elements
        let bottomOffset = 12;
        const fixedElements = document.querySelectorAll('[style*="fixed"][style*="bottom"]');
        fixedElements.forEach((el) => {
            if (el !== badge) {
                const rect = el.getBoundingClientRect();
                if (rect.right > window.innerWidth - 120 && rect.bottom > window.innerHeight - 80) {
                    bottomOffset = Math.max(bottomOffset, window.innerHeight - rect.top + 8);
                }
            }
        });
        badge.style.bottom = `${bottomOffset}px`;

        const isDark = document.body.classList.contains("dark") || !document.body.classList.contains("light");

        if (isOnline) {
            badge.style.background = isDark ? "#1b3320" : "#dcfce7";
            badge.style.color = isDark ? "#4ade80" : "#166534";
            badge.style.border = `1px solid ${isDark ? "#22c55e" : "#86efac"}`;
            badge.innerHTML = `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 6px #22c55e;"></span> CMM: Online`;
        } else {
            badge.style.background = isDark ? "#2a1b1b" : "#fee2e2";
            badge.style.color = isDark ? "#f87171" : "#991b1b";
            badge.style.border = `1px solid ${isDark ? "#ef4444" : "#fca5a5"}`;
            badge.innerHTML = `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#ef4444;"></span> CMM: Offline`;
        }
    },

    async nodeCreated(node) {
        const category = node.constructor?.category || "";
        const comfyClass = node.comfyClass || "";

        // Apply styling for Renegade / CivitAI / CMM nodes
        if (
            category.includes("Renegade Nodes") ||
            category.startsWith("CivitAI") ||
            comfyClass.startsWith("CMM") ||
            comfyClass === "SmartModelLoader" ||
            comfyClass === "PipeUnpackModel"
        ) {
            node.color = "#1e293b";
            node.bgcolor = "#0f172a";
        }

        // SmartModelLoader: conditionally show clip name / vae name widgets
        if (comfyClass === "SmartModelLoader") {
            const toggleWidgetVisibility = (widget, visible) => {
                if (!widget) return;
                widget.type = visible ? widget._origType || widget.type : "hidden";
                if (visible && widget._origType) {
                    widget.type = widget._origType;
                }
                if (!visible) {
                    if (widget.type !== "hidden") {
                        widget._origType = widget.type;
                    }
                    widget.type = "hidden";
                }
            };

            const findWidget = (name) => node.widgets?.find((w) => w.name === name);

            const updateVisibility = () => {
                const clipSource = findWidget("clip source");
                const vaeSource = findWidget("vae source");
                const clipName = findWidget("clip name");
                const vaeName = findWidget("vae name");

                toggleWidgetVisibility(clipName, clipSource?.value === "Separate File");
                toggleWidgetVisibility(vaeName, vaeSource?.value === "Separate File");

                // Trigger layout recalculation
                node.setSize?.(node.computeSize?.() || node.size);
            };

            // Store original callbacks and chain ours
            const clipSource = findWidget("clip source");
            const vaeSource = findWidget("vae source");

            if (clipSource) {
                const origClip = clipSource.callback;
                clipSource.callback = (...args) => {
                    origClip?.(...args);
                    updateVisibility();
                };
            }
            if (vaeSource) {
                const origVae = vaeSource.callback;
                vaeSource.callback = (...args) => {
                    origVae?.(...args);
                    updateVisibility();
                };
            }

            // Set initial state after a tick so widgets are fully initialized
            setTimeout(updateVisibility, 100);
        }
    },
});
