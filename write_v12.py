# -*- coding: utf-8 -*-
src = r"""// src/main.ts — Live Sync Collab v1.2（桌面 / Android / iOS 通用）
// 傻瓜版：内置服务器默认配置，装好即用；断线/对方离线各只弹一次中文提醒；自动重连。
import { App, Notice, Plugin, PluginSettingTab, Setting, MarkdownView, TFile } from "obsidian";
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";
import { yCollab } from "y-codemirror.next";
import { StateEffect } from "@codemirror/state";
import type { Extension } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";

interface LiveSyncSettings {
  serverUrl: string;
  token: string;
  vaultName: string;
  showNotices: boolean;   // 连接成功时是否弹通知（默认关，状态栏有显示）
}

// 内置默认配置：新设备装上插件即可用，无需手填
const DEFAULT_SETTINGS: LiveSyncSettings = {
  serverUrl: "wss://sync.hoyinlaw.online:8443",
  token: "b97638cfdd94abbbbd7c70c12415cf694353395e13e38d00cbd42b338c626e40",
  vaultName: "my-vault",
  showNotices: false,
};

const DISCONNECT_WARN_DELAY = 8000;  // 断线超过 8 秒才提醒一次

interface SyncSession {
  doc: Y.Doc;
  provider: WebsocketProvider;
  ytext: Y.Text;
  path: string;
  cm: EditorView | null;
  bound: boolean;
}

export default class LiveSyncPlugin extends Plugin {
  settings: LiveSyncSettings;
  session: SyncSession | null = null;
  statusEl: HTMLElement;
  private disconnectWarned = false;   // 本次断线是否已提醒过（只弹一次）
  private disconnectTimer: number | null = null;
  private peerWarned = false;         // 本次"对方不在线"是否已提醒过（只弹一次）

  async onload() {
    await this.loadSettings();
    this.addSettingTab(new LiveSyncSettingTab(this.app, this));
    this.statusEl = this.addStatusBarItem();
    this.setStatus("未连接");

    this.registerEvent(this.app.workspace.on("active-leaf-change", () => this.onActiveFile()));
    this.registerEvent(this.app.workspace.on("file-open", () => this.onActiveFile()));
    this.registerEvent(this.app.workspace.on("layout-change", () => this.ensureBinding()));

    this.addCommand({
      id: "reconnect-live-sync",
      name: "重新连接实时同步",
      callback: () => this.onActiveFile(true),
    });

    this.registerInterval(window.setInterval(() => this.ensureBinding(), 2000));

    this.app.workspace.onLayoutReady(() => this.onActiveFile());
  }

  onunload() { this.detach(); }

  setStatus(s: string) { if (this.statusEl) this.statusEl.setText("Live: " + s); }

  private getCmView(): EditorView | null {
    const view = this.app.workspace.getActiveViewOfType(MarkdownView);
    if (!view) return null;
    return (view.editor as any).cm as EditorView;
  }

  private clearDisconnectTimer() {
    if (this.disconnectTimer !== null) {
      window.clearTimeout(this.disconnectTimer);
      this.disconnectTimer = null;
    }
  }

  private detach() {
    this.clearDisconnectTimer();
    if (this.session) {
      this.session.provider.destroy();
      this.session.doc.destroy();
      this.session = null;
    }
  }

  async onActiveFile(force = false) {
    const file = this.app.workspace.getActiveFile();
    if (!file || file.extension !== "md") {
      if (this.session) { this.detach(); this.setStatus("非 Markdown"); }
      return;
    }
    if (!this.settings.serverUrl || !this.settings.token) {
      this.setStatus("未配置");
      return;
    }
    if (!force && this.session && this.session.path === file.path) return;
    this.detach();
    this.attach(file);
  }

  private ensureBinding() {
    const s = this.session;
    if (!s || !s.provider.synced) return;
    const cm = this.getCmView();
    if (!cm) return;
    if (!s.bound || s.cm !== cm) {
      console.log("[live-sync] rebinding editor view");
      this.bind(s, cm);
    }
  }

  private attach(file: TFile) {
    const room = encodeURIComponent(this.settings.vaultName + "/" + file.path);
    const doc = new Y.Doc();
    const ytext = doc.getText("content");
    const provider = new WebsocketProvider(this.settings.serverUrl, room, doc, {
      params: { token: this.settings.token },
    });
    const session: SyncSession = { doc, provider, ytext, path: file.path, cm: null, bound: false };
    this.session = session;
    this.setStatus("连接中…");

    let syncedOnce = false;
    provider.on("sync", (isSynced: boolean) => {
      if (!isSynced || syncedOnce) return;
      syncedOnce = true;
      this.setStatus("已连接");

      const peers = provider.awareness.getStates().size;
      const cm0 = this.getCmView();
      const local0 = cm0 ? cm0.state.doc.toString() : "";
      const trySeed = () => {
        const cm = this.getCmView();
        const local = cm ? cm.state.doc.toString() : "";
        if (ytext.length === 0 && local.length > 0) {
          ytext.insert(0, local);
          console.log("[live-sync] seeded room,", local.length, "chars");
        }
      };
      if (ytext.length === 0) {
        if (peers <= 1) {
          trySeed();
        } else {
          setTimeout(() => { if (ytext.length === 0) trySeed(); }, 1500);
        }
      } else if (peers <= 1 && local0 !== ytext.toString()) {
        // 只有本端在线但内容不一致 → 本地覆盖远端，防止静默丢字
        doc.transact(() => {
          ytext.delete(0, ytext.length);
          ytext.insert(0, local0);
        });
        new Notice("实时同步：已用本机内容覆盖服务器的旧版本");
        console.log("[live-sync] local overrides remote");
      }
      this.ensureBinding();
      if (this.settings.showNotices) new Notice("实时同步已连接：" + file.basename);
    });

    // 连接状态监控：断线超过 8 秒只提醒一次；恢复后静默并复位
    provider.on("status", (e: any) => {
      if (this.session !== session) return;
      if (e.status === "connected") {
        this.setStatus("已连接");
        this.clearDisconnectTimer();
        this.disconnectWarned = false;
      } else {
        this.setStatus("重连中…");
        this.clearDisconnectTimer();
        this.disconnectTimer = window.setTimeout(() => {
          if (this.session === session && !this.disconnectWarned) {
            this.disconnectWarned = true;
            new Notice("实时同步：与服务器断开，正在自动重连，修改不会丢失");
          }
        }, DISCONNECT_WARN_DELAY);
      }
    });

    // 本地修改检测：另一台设备不在线时只提醒一次（上线后自动补齐，复位以便下次再提醒）
    doc.on("update", (_update: Uint8Array, origin: any) => {
      if (origin === provider) return;              // 远端应用的更新，不算本地修改
      if (this.session !== session) return;
      if (provider.awareness.getStates().size <= 1 && !this.peerWarned) {
        this.peerWarned = true;
        new Notice("实时同步：另一台设备当前不在线，修改将在对方上线后自动同步");
      }
    });
    provider.awareness.on("change", () => {
      if (provider.awareness.getStates().size > 1) this.peerWarned = false;
    });
  }

  private bind(s: SyncSession, cm: EditorView) {
    const bindingExt: Extension = yCollab(s.ytext, s.provider.awareness);
    cm.dispatch({ effects: StateEffect.appendConfig.of([bindingExt]) });
    s.cm = cm;
    s.bound = true;
    console.log("[live-sync] bound to editor, ytext len:", s.ytext.length);
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    // 旧版本配置里没有 showNotices 字段时默认关闭
    if (typeof this.settings.showNotices !== "boolean") this.settings.showNotices = false;
  }
  async saveSettings() {
    await this.saveData(this.settings);
  }
}

class LiveSyncSettingTab extends PluginSettingTab {
  plugin: LiveSyncPlugin;
  constructor(app: App, plugin: LiveSyncPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }
  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "实时同步设置（一般无需修改）" });

    new Setting(containerEl)
      .setName("服务器地址")
      .setDesc("已内置默认值，只有换服务器时才需要改")
      .addText((t) =>
        t.setPlaceholder("wss://...").setValue(this.plugin.settings.serverUrl)
          .onChange(async (v) => {
            this.plugin.settings.serverUrl = v.trim().replace(/\/$/, "");
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("连接密钥")
      .setDesc("已内置默认值，与服务器 SYNC_TOKEN 一致")
      .addText((t) =>
        t.setPlaceholder("token").setValue(this.plugin.settings.token)
          .onChange(async (v) => {
            this.plugin.settings.token = v.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("仓库名（房间前缀）")
      .setDesc("已内置默认值，多台设备必须相同")
      .addText((t) =>
        t.setPlaceholder("default").setValue(this.plugin.settings.vaultName)
          .onChange(async (v) => {
            this.plugin.settings.vaultName = v.trim() || "default";
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("连接成功时弹通知")
      .setDesc("默认关闭，连接状态见右下角状态栏")
      .addToggle((t) =>
        t.setValue(this.plugin.settings.showNotices)
          .onChange(async (v) => {
            this.plugin.settings.showNotices = v;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("立即重连")
      .addButton((b) =>
        b.setButtonText("重连").onClick(() => {
          this.plugin.onActiveFile(true);
          new Notice("已重新连接");
        })
      );
  }
}
"""
import io
io.open(r"C:\Users\Patrick\obsidian-live-sync\plugin\src\main.ts", "w", encoding="utf-8").write(src)

import json
mp = r"C:\Users\Patrick\obsidian-live-sync\plugin\manifest.json"
m = json.load(io.open(mp, encoding="utf-8"))
m["version"] = "1.2.0"
json.dump(m, io.open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("main.ts rewritten, version 1.2.0")
