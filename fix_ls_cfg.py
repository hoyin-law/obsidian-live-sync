import json, io
p = r"C:\Patrick's work place\.obsidian\plugins\obsidian-livesync\data.json"
d = json.load(io.open(p, encoding="utf-8"))

fixes = {
  "notifyThresholdOfRemoteStorageSize": 2000,   # 2GB 才告警，消灭"未配置"弹窗
  "disableCheckingConfigMismatch": True,        # 消灭"配置不一致"乒乓警告
  "suppressNotifyHiddenFilesChange": True,      # 隐藏文件变更不再通知
  "syncOnSave": True,                           # 保存时同步（界面里开了但没落盘）
  "syncOnStart": True,                          # 启动时同步
  "syncAfterMerge": True,                       # 合并后同步
}
for k, v in fixes.items():
    old = d.get(k, "<missing>")
    d[k] = v
    print(f"{k}: {old} -> {v}")

json.dump(d, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("data.json saved")
