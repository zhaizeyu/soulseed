# 部署到 Debian 云服务器

当前代码**无需为 Debian 做适配修改**，路径与网络绑定已跨平台。按下面清单配置即可在云服务器上运行。

## 一、无需改代码的原因

| 项目 | 说明 |
|------|------|
| **路径** | 使用 `pathlib.Path` 与相对路径（如 `data/`、`logs/`），在 Linux 下正常。 |
| **Web 监听** | `config.yaml` 默认 `web_host: "0.0.0.0"`，外网可访问。 |
| **平台判断** | 未使用 `darwin`/`windows`/`sys.platform` 等平台分支。 |
| **截屏 (mss)** | 仅当 `vision_enabled: true` 时调用；无图形界面时保持 **`vision_enabled: false`** 即可，不会报错。 |

## 二、部署前配置清单

1. **Python 3.11+**  
   Debian 12：`sudo apt install python3.11 python3.11-venv python3-pip`  
   或使用 [deadsnakes PPA](https://github.com/deadsnakes/python3.11) / 自编译。

2. **`.env`**（项目根目录）  
   - 必填：`GEMINI_API_KEY=你的密钥`  
   - 若跑 Telegram Bot：`TELEGRAM_BOT_TOKEN=你的Bot Token`

3. **`config.yaml` 与无图形环境**  
   - 保持 **`vision_enabled: false`**（当前默认即为 false），避免在无 DISPLAY 的服务器上调用截屏。  
   - 若只跑 Web/Telegram，不跑 CLI 主循环，无需改其他项。

4. **依赖安装**  
   ```bash
   cd /path/to/SoulSeed_Project
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 三、运行方式（任选）

- **仅 Web 对话**：`python -m src.web`（默认 0.0.0.0:8765）
- **仅 Telegram Bot**：在 `config.yaml` 中设 `telegram_enabled: true`，然后 `python -m src.telegram`
- **CLI 主循环**：`python main.py`（需有终端交互，适合调试）

## 四、可选：进程保活（systemd）

以 Web 为例，可建 `/etc/systemd/system/soulseed-web.service`：

```ini
[Unit]
Description=SoulSeed Web
After=network.target

[Service]
Type=simple
User=你的用户
WorkingDirectory=/path/to/SoulSeed_Project
Environment=PATH=/path/to/SoulSeed_Project/.venv/bin
ExecStart=/path/to/SoulSeed_Project/.venv/bin/python -m src.web
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

然后：`sudo systemctl daemon-reload && sudo systemctl enable --now soulseed-web`。

## 五、防火墙与安全

- 若从外网访问 Web：放行 `web_port`（默认 8765），例如 `ufw allow 8765/tcp`。
- `.env` 不要提交到仓库；生产环境建议用独立用户、限制目录权限。

## 六、若将来在服务器上启用「眼睛」（截屏）

无图形界面时 mss 会失败。若确需在服务器上截屏（例如用虚拟显示），可：

- 使用 **Xvfb**：安装 `xvfb`，启动时 `DISPLAY=:99`，并先启动 `Xvfb :99`；或  
- 保持 `vision_enabled: false`，仅通过 Web 上传图片 / Telegram 发图 等方式提供图像输入。

当前默认配置已适合无图形界面的 Debian 云服务器，无需改代码即可部署。
