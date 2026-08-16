# V5.0 发布手册 (Release Runbook)

本手册指导业主完成一次 InkStatute v5.0 的完整发布流程。

---

## 1. 发布前检查单

发布前必须确认以下全部通过：

- [ ] **V5 六道门禁全绿**：`node scripts/gates/v5/run-gates.mjs` 输出 `6 passed, 0 failed`
- [ ] **真机冒烟**：在干净的 Windows 机器上安装后能双击启动、完成首启向导、发送一条法律问题并收到流式回复
- [ ] **`engines/engine-lock.json` 已提交**：与 `engines/dsh-pin.txt` 版本一致
- [ ] **`engines/acp.cordis.yml` 已提交**：SHA256 与 lock 中的 `cordis_config_sha256` 一致
- [ ] **便携 Node 已下载**：`apps/desktop/src-tauri/resources/node/node.exe` 存在（gitignored，构建前由 `scripts/fetch-node-runtime.mjs` 下载）
- [ ] **无明文 API 密钥**：`grep -rn 'sk-' apps/ packages/ engines/ scripts/` 除测试 fixture 外无命中
- [ ] **无占位值**：`grep -rn 'dW5zZXQtcmVwbGFjZS13aXRo\|<owner-host>' apps/desktop/src-tauri/tauri.conf.json` 返回空

---

## 2. 签名密钥生成与保管

### 2.1 应用更新签名密钥

Tauri updater 要求安装包有签名。生成密钥对：

```bash
bunx tauri signer generate -w ~/.tauri/inkstatute.key
```

- **私钥** (`~/.tauri/inkstatute.key`)：绝不进仓库。备份位置由业主决定（建议加密 USB + 云备份）。
- **公钥**：输出到终端，复制到 `tauri.conf.json` 的 `plugins.updater.pubkey` 字段。
- **环境变量**：构建时设置 `TAURI_PRIVATE_KEY` 和 `TAURI_KEY_PASSWORD`。

### 2.2 代码签名证书（可选但推荐）

无代码签名证书时，Windows Defender SmartScreen 会拦截首次安装。业主可：

1. 购买 EV 代码签名证书（约 ¥2,000-5,000/年），或
2. 接受首次安装时用户需手动点击"仍要运行"。

---

## 3. 更新服务器需要托管什么

| 文件 | 用途 | 大小估算 |
|---|---|---|
| `engine-lock.json` | 引擎更新清单（版本号、包列表、SHA512） | ~40 KB |
| `latest.json` + 安装包 + `.sig` | Tauri app 更新（updater 格式） | ~100-200 MB |
| `content-manifest.json` + 内容包 zip | 法律技能内容包更新 | ~5-20 MB |

**注意：引擎的 196 个 npm tarball 不需要业主托管——走 npm registry（`registry.npmmirror.com` 或 `registry.npmjs.org`）。**

### 3.1 `latest.json` 格式（Tauri updater）

```json
{
  "version": "0.1.1",
  "notes": "修复合同审查中的引用缺失问题",
  "pub_date": "2026-02-15T10:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "signature": "...",
      "url": "https://updates.inkstatute.com/releases/inkstatute-0.1.1-windows-x86_64.msi.zip"
    }
  }
}
```

### 3.2 `tauri.conf.json` 更新端点

发布前必须将 `plugins.updater.endpoints` 中的占位地址
`https://updates.inkstatute.com/api/app/latest/{{target}}/{{arch}}/{{current_version}}`
替换为业主实际托管的地址。

---

## 4. 引擎升级流程

1. 改 `engines/dsh-pin.txt` 为新版本号
2. 运行 `node scripts/gen-engine-lock.mjs` 生成新的 `engine-lock.json`
3. 本机冒烟：`cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --test engine_smoke_test -- --ignored`
4. 真机回归：跑一轮真实法律任务（合同审查 / 法律咨询 / 文书起草）
5. 提交 `engine-lock.json` 和 `dsh-pin.txt`
6. 将新的 `engine-lock.json` 上传到更新服务器
7. 用户侧：app 启动后自动检测 → 提示更新 → 用户确认 → 下载装配冒烟 → 下次启动生效

---

## 5. 回滚流程

### 5.1 服务器侧回滚

将更新服务器上的 `engine-lock.json` 换回旧版本。用户侧 app 下次检查更新时会检测到"已是最新"（因为版本号回退了），不会自动降级。

### 5.2 用户侧手动回退

设置 → 关于 → 已安装引擎版本 → 点击「回退」按钮。回退目标也必须通过冒烟测试。

### 5.3 紧急回退（app 无法启动）

删除 `%LOCALAPPDATA%\InkStatute\engine\current` 文件，app 会回退到上一可用版本（如果有多个版本目录）。如果只有一个版本，需要重新安装 app。

---

## 6. 首次运行 Defender 提示处理

无 EV 代码签名证书时，Windows Defender SmartScreen 会显示"Windows 已保护你的电脑"。

**用户操作**：点击「更多信息」→「仍要运行」。

**业主建议**：在下载页面或安装指南中注明此为正常现象，并附截图说明。

---

## 7. 构建命令

```bash
# 1. 下载便携 Node（首次或 Node 版本更新后）
node scripts/fetch-node-runtime.mjs

# 2. 一键构建安装包
node scripts/build-windows-installer.mjs

# 产物路径：
# apps/desktop/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/
```

---

## 8. 七个验收场景（PRD §2）

在干净的 Windows 机器上逐条演练：

| # | 场景 | 通过标准 |
|---|---|---|
| 1 | 双击安装 → 向导 → 打开即用 | 全程无命令行、无配置文件 |
| 2 | 「审查这份合同」+ 拖入文件 | 流式正文 + 思考过程 + 工具时间线 + 引用徽记 + 必要时澄清卡 |
| 3 | 审批 | 弹批准卡，允许/拒绝均生效，界面上找不到批量批准入口 |
| 4 | 中止 | 点停止后当前轮立即结算 |
| 5 | 引擎更新 | 提示 → 确认 → 下载校验冒烟 → 下次启动生效 |
| 6 | 技能更新 | 启动自动拉取，用户无感 |
| 7 | 断网 | 可打开、可看历史、提示"联网后才能进行新任务"、字体不降级 |

**这是 v5.0 的交付闸。任一项不过则回到对应 phase 修复。**

---

## 9. 人工闸门（不在本阶段关闭）

| 闸门 | 内容 | 状态 |
|---|---|---|
| HG-1 法律质量 | 律师抽样确认不低于 lawyer-desktop/Hermes 基线 | DEFERRED |
| HG-3 律师试运行 | 五工作日 / 15 真实任务 | DEFERRED |

这两个闸门需要律师人工评估，不得由自动化声称通过。
