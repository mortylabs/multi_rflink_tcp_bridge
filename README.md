# MultiRFLink TCP Bridge

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**MultiRFLinkTCPBridge** is a Python app that consolidates multiple RFLink streams (433MHz, 868MHz, etc.) from distributed devices, with their own IP addresses or ports, into a single TCP output - ready for Home Assistant or any automation hub.

---

## 📌 Key Benefit

🔧 **Multi-RFLink support out of the box** - Home Assistant supports only one RFLink connection natively. This bridge removes that limitation by allowing multiple RFLink units - each potentially sniffing different RF frequencies like **433MHz** and **868MHz** - to be connected simultaneously.

🛰️ **Extend signal range and coverage** by deploying RFLink devices (e.g., Raspberry Pi Zero W + RF modules) in different rooms or floors. This bridge links all devices into one TCP stream, letting Home Assistant consume everything from a **single, unified endpoint**.

---

## 📖 Table of Contents

- [Features](#features)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [Usage](#usage)
- [Integration Examples](#integration-examples)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## 🧩 Features

- Supports 433MHz and 868MHz RFLinks in parallel
- Centralizes multiple RFLink TCP feeds into one
- Compatible with Home Assistant, Node-RED, MQTT, etc.
- Optional Telegram alerts on disconnect/reconnect
- Graceful handling of stale messages on client connection
- Lightweight and efficient (runs on Pi Zero W)

---

## 🚀 Quickstart

```bash
git clone https://github.com/mortylabs/MultiRFLinkTCPBridge.git
cd MultiRFLinkTCPBridge
cp .env.example .env
nano .env  # configure IPs, ports, and logging
pip install -r requirements.txt
python MultiRFLinkTCPBridge.py
```


## ⚙️ Configuration

Create and customize a `.env` file in the project root. You can copy from a template:

```bash
cp .env.example .env
```

| Variable                 | Description                                           | Example             |
|--------------------------|-------------------------------------------------------|---------------------|
| `RFLINK1_IP`, `PORT`     | RFLink device #1 IP and port                          | `192.168.1.10:5000` |
| `RFLINK2_IP`, `PORT`     | Optional second RFLink device                         | `192.168.1.11:5001` |
| `RFLINK3_IP`, `PORT`     | Optional third RFLink device                          | `192.168.1.12:5002` |
| `RFLINK_BRIDGE_IP`       | IP for this bridge to listen on                       | `0.0.0.0`           |
| `RFLINK_BRIDGE_PORT`     | Port for unified stream                               | `1234`              |
| `WRITE_LOG_TO_DISK`      | Write logs to file (`true` or `false`)                | `true`              |
| `LOGGING_LEVEL`          | Logging level (`DEBUG`, `INFO`, `WARN`, `ERROR`)_     | `INFO`              |
| `TELEGRAM_ENABLED`       | Enable Telegram alerts                                | `true`              |
| `TELEGRAM_BOT_KEY`       | Telegram bot token                                    | `-`                 |
| `TELEGRAM_BOT_CHAT_ID`   | Target chat ID for alerts                             | `-`                 |


## 🧠 Usage

Once configured, simply run the script:

```bash
python MultiRFLinkTCPBridge.py
```
- Starts listener threads for each RFLink
- Forwards their messages into one bridge stream
- Supports reconnects and alerting via Telegram
- Messages drained on new client connect to avoid stale payloads

This bridge gives your automation system a unified, real-time view of your RF environment, regardless of how many RFLinks you deploy or where you place them.

## 🚁 Remote Device Setup

For each Raspberry Pi Zero W / 2 W with an RFLink USB device:

1. **Install Python 3 and `rflinkproxy`**

```bash
sudo apt update
pip3 install rflink
```

2. **Create a proxy systemctl service: **
```bash
sudo nano /etc/systemd/system/rflinkproxy.service
[Unit]
Description=RFLink Proxy Service
After=network.target

[Service]
ExecStart=/home/pi/start-rflinkproxy.sh
WorkingDirectory=/home/pi
User=pi
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```
sudo systemctl daemon-reload
sudo systemctl enable rflinkproxy
sudo systemctl start rflinkproxy
```

## 🏠 Integration Examples

### 🔌 Home Assistant

```yaml
sensor:
  - platform: tcp
    host: 192.168.1.50  # IP of your bridge device
    port: 1234          # Port defined in your .env
    name: RFLink Stream

```
### 🔁 Node-RED Integration

To integrate the unified RFLink stream into Node-RED:

1. **Add a TCP In node**
   - Type: `stream`
   - Host: IP of your MultiRFLinkTCPBridge (e.g., `192.168.1.50`)
   - Port: TCP port from your `.env` (e.g., `1234`)

2. **Connect it to a debug or processing node**
   - This will show raw RFLink messages from all linked devices

💡 Tip: You can split or parse the RFLink strings using `function`


## 📈 Roadmap

- [x] Multi-RFLink support across IPs and ports
- [x] Support for multiple frequencies (433MHz and 868MHz)
- [x] Telegram alert integration for error/reconnects
- [x] Graceful queue draining on new client connect
- [ ] Dockerfile and container support
- [ ] AsyncIO-based socket backend for better scalability

---

## 📜 License

This project is licensed under the MIT License.  
See the [LICENSE](LICENSE) file for details.

---

## 💬 Questions?

Have feedback or need support?

- Open an [issue](https://github.com/mortylabs/MultiRFLinkTCPBridge/issues)
- Start a discussion on the repo
- Suggest features or improvements via pull requests



