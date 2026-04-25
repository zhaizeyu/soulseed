# 部署到 Debian 云服务器

当前代码无需为 Debian 做适配，按下面步骤配置即可在云服务器运行。**推荐使用 `scripts/` 下的起停脚本**做后端运行（nohup + 日志 + PID），断 SSH 后进程保持。

---

## 一、部署前准备

1. **Python 3.11+**  
   Debian 12：`sudo apt install python3.11 python3.11-venv python3-pip`  
   Debian 默认无 `python` 命令，只有 `python3` / `python3.11`。可用：  
   - 创建 venv 后始终在 venv 内操作（推荐）；或  
   - `sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1` 让系统提供 `python`。

2. **`.env`**（项目根目录）  
   - 必填：`LITELLM_API_KEY=你的密钥`、`OPENAI_BASE_URL=你的网关地址`、`CHAT_MODEL=模型名`  
   - 跑 Telegram Bot 时：`TELEGRAM_BOT_TOKEN=你的 Bot Token`

3. **config.yaml**  
   - 无图形界面时保持 **`vision_enabled: false`**（默认即可），避免截屏报错。  
   - 仅跑 Web/Telegram 时无需改其他项。

4. **依赖安装**（在项目根目录执行）  
   ```bash
   cd /path/to/SoulSeed_Project
   python3.11 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```  
   前端（仅 Web 模式需要）：`cd webapp && npm install`

---

## 二、启停方式（推荐）

在**项目根目录**执行下列脚本；脚本会自动激活 `.venv`（若存在）、创建 `logs/`、nohup 写日志并写 PID 文件，断终端后进程继续运行。

| 模式 | 启动 | 停止 | 日志 |
|------|------|------|------|
| **Web（后端 + 前端）** | `./scripts/start_web.sh` | `./scripts/stop_web.sh` | `logs/web_backend.log`、`logs/web_frontend.log` |
| **Telegram Bot** | `./scripts/start_telegram.sh` | `./scripts/stop_telegram.sh` | `logs/telegram.log` |

- 使用 `sh` 时：`sh scripts/start_web.sh`、`sh scripts/start_telegram.sh` 等同样有效。  
- 若提示「已在运行」：先执行对应 `stop_*.sh` 再启动。  
- Web 启动后：后端 http://127.0.0.1:8765，前端 http://localhost:5173。

---

## 三、前台运行（调试用）

需要直接看终端输出时，可在激活 venv 后：

- **Web**：`python -m src.web`（仅后端，默认 0.0.0.0:8765）
- **Telegram**：确保 `config.yaml` 中 `telegram_enabled: true`，然后 `python -m src.telegram`
- **CLI 主循环**：`python main.py`（需终端交互）

---

## 四、可选：systemd 开机自启

需要开机自启或崩溃自动重启时，可使用 systemd。

**Web** — `/etc/systemd/system/soulseed-web.service`：

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

**Telegram** — `/etc/systemd/system/soulseed-telegram.service`：

```ini
[Unit]
Description=SoulSeed Telegram Bot
After=network.target

[Service]
Type=simple
User=你的用户
WorkingDirectory=/path/to/SoulSeed_Project
Environment=PATH=/path/to/SoulSeed_Project/.venv/bin
ExecStart=/path/to/SoulSeed_Project/.venv/bin/python -m src.telegram
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

将上述路径与用户改为实际值后：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now soulseed-web
# 或
sudo systemctl enable --now soulseed-telegram
```

---

## 五、防火墙与安全

- 外网访问 Web 时放行 `web_port`（默认 8765），例如：`ufw allow 8765/tcp`。  
- `.env` 勿提交仓库；生产建议用独立用户并限制目录权限。

---

## 六、无图形界面说明

服务器无 DISPLAY 时，保持 **`vision_enabled: false`** 即可。若将来需要在服务器上截屏，可考虑 Xvfb 或保持关闭，仅通过 Web 上传图片 / Telegram 发图提供图像输入。
