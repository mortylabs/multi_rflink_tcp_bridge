#!/usr/bin/env python3
'''
"""
MultiRFLink TCP Bridge

This script enables Home Assistant and other systems to interface with multiple RFLink devices
simultaneously by aggregating their data into a single TCP stream. This overcomes the
single-RFLink limitation found in many home automation platforms like Home Assistant.

You can deploy multiple RFLink receivers (e.g., Raspberry Pi Zero W devices with RF modules) throughout your home.
Each RFLink can sniff different frequencies like 433MHz or 868MHz, dramatically improving your RF coverage.
This bridge links all of them together and presents them as one unified stream for Home Assistant or other consumers.


This app reads in the following env vairables,
    which can be set already externaally via an export --OR__
    supplied in a ".env" file in the same directory as this python script:
LOG_DIR                     directory to write logs to
WRITE_LOG_TO_DISK          write log to disk if true, or to screen if false
LOGGING_LEVEL              DEBUG, INFO, WARN, ERROR, EXCEPTION etc
TELEGRAM_ENABLED           True/False
TELEGRAM_BOT_KEY           Telegram key supplied by BotFather
TELEGRAM_BOT_CHAT_ID       Telegram chat id
RFLINK1_IP                 TCP IP address of first RfLink device
RFLINK1_PORT               TCP PORT of first RfLink device
RFLINK2_IP                 2nd RFLink device etc
RFLINK2_PORT               etc
RFLINK_BRIDGE_IP           etc
RFLINK_BRIDGE_PORT         etc
'''

import socket
import threading
import queue
import logging
from os import path, getcwd, getenv
from sys import exc_info
from dotenv import load_dotenv
import telepot
from time import sleep

# Load environment variables
load_dotenv(path.join(path.abspath(path.dirname(__file__)), '.env'))

APP_NAME = path.basename(__file__).replace(".py", "")

# Logging setup
log_dir = getenv('LOG_DIR', getcwd())
if not path.isdir(log_dir):
    logging.warning("Invalid $LOG_DIR (%s), defaulting to cwd (%s)", log_dir, getcwd())
    log_dir = getcwd()
log_dir = path.join(log_dir, '')

log_file = path.join(log_dir, f"{APP_NAME}.log")

write_log_to_disk = getenv('WRITE_LOG_TO_DISK', 'false').lower() == 'true'
log_level = logging.getLevelName(getenv('LOGGING_LEVEL', 'INFO').upper())
log_level = log_level if isinstance(log_level, int) else logging.INFO

log_format = '%(asctime)s %(funcName)-20s [%(lineno)s]: %(message)s'
log_datefmt = '%Y-%m-%d %H:%M:%S'

logging.basicConfig(
    format=log_format,
    datefmt=log_datefmt,
    filename=log_file if write_log_to_disk else None,
    level=log_level
)

logger = logging.getLogger(__name__)

# Telegram setup
telegram_enabled = getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'
telegram_bot_key = getenv('TELEGRAM_BOT_KEY')
telegram_chat_id = getenv('TELEGRAM_BOT_CHAT_ID')
telegram_bot = telepot.Bot(telegram_bot_key) if telegram_enabled else None

# RFLink device config
bridge_ip = getenv('RFLINK_BRIDGE_IP', 'localhost')
bridge_port = int(getenv('RFLINK_BRIDGE_PORT', '1234'))

devices = [
    (getenv('RFLINK1_IP'), getenv('RFLINK1_PORT')),
    (getenv('RFLINK2_IP'), getenv('RFLINK2_PORT')),
    (getenv('RFLINK3_IP'), getenv('RFLINK3_PORT'))
]

message_queue = queue.Queue()

def format_exception():
    return f"line: {exc_info()[2].tb_lineno}, {exc_info()[1]}" if exc_info()[0] else "exc_info not available!"

def log_error_and_notify(message):
    if exc_info()[0]:
        logger.exception(message)
    else:
        logger.error(message)

    send_telegram_message(message)

def send_telegram_message(message):
    if not telegram_enabled:
        return
    for attempt in range(3):
        try:
            telegram_bot.sendMessage(telegram_chat_id, f"<b>{APP_NAME}</b>\n<i>{message}</i>", parse_mode="Html")
            return
        except telepot.exception.TooManyRequestsError as e:
            retry_after = e.json.get('parameters', {}).get('retry_after', 10) if hasattr(e, 'json') else 10
            logger.warning(f"Telegram rate limited, retrying after {retry_after}s")
            sleep(retry_after)
        except Exception:
            logger.exception("Failed to send Telegram message")
            return


class BridgeThread(threading.Thread):
    def __init__(self, ip, port):
        super().__init__()
        self.ip = ip
        self.port = port
        self._reconnect_pending = False

    def run(self):
        while True:
            try:
                logger.info(f"{self.__class__.__name__}: Starting on {self.ip}:{self.port}")
                with socket.socket() as server_socket:
                    # Fix 1: SO_REUSEADDR prevents "port already in use" on restart
                    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    server_socket.bind((self.ip, self.port))
                    server_socket.listen(2)
                    logger.info(f"{self.__class__.__name__}: Listening for client...")
                    conn, addr = server_socket.accept()
                    if self._reconnect_pending:
                        log_error_and_notify(f"BridgeThread: HA reconnected successfully from {addr} ✅")
                    self._reconnect_pending = False
                    with conn:
                        logger.info(f"{self.__class__.__name__}: Incoming connection from {addr}")
                        while not message_queue.empty():
                            logger.info(f"{self.__class__.__name__}: Draining old messages ({message_queue.qsize()} remaining)...")
                            message_queue.get()
                        while True:
                            item = message_queue.get()
                            logger.info(f"{self.__class__.__name__}: Sending {item}")
                            conn.sendall(item)
                            message_queue.task_done()
            except Exception:
                err = format_exception()
                logger.warning(f"{self.__class__.__name__}: Connection lost ({err}), starting 120s reconnect window...")
                self._reconnect_pending = True
                def alert_if_no_reconnect(bridge, error):
                    sleep(120)
                    if bridge._reconnect_pending:
                        log_error_and_notify(f"BridgeThread: HA did not reconnect within 120s — {error}")
                        bridge._reconnect_pending = False
                threading.Thread(target=alert_if_no_reconnect, args=(self, err), daemon=True).start()
                sleep(10)

class RFLinkThread(threading.Thread):
    def __init__(self, ip, port):
        super().__init__()
        self.ip = ip
        self.port = int(port)
        self._down = False
        self._last_alert = 0
        self._alert_interval = 7200  # 2 hours

    def _handle_disconnect(self, reason):
        if not self._down:
            # First disconnection — start timer, only alert if still down after 120s
            self._down = True
            logger.info(f"{self.__class__.__name__}: {self.ip} disconnected — {reason}, starting 120s reconnect window...")
            def alert_if_no_reconnect(thread, r):
                sleep(120)
                if thread._down:
                    thread._last_alert = __import__('time').time()
                    log_error_and_notify(f"{thread.__class__.__name__}: {thread.ip} disconnected — {r}")
            threading.Thread(target=alert_if_no_reconnect, args=(self, reason), daemon=True).start()
        else:
            now = __import__('time').time()
            if now - self._last_alert >= self._alert_interval:
                # Still down — reminder every 2 hours
                self._last_alert = now
                log_error_and_notify(f"{self.__class__.__name__}: {self.ip} still down — {reason}")

    def _handle_reconnect(self):
        if self._down:
            self._down = False
            if self._last_alert > 0:
                # Only notify if disconnect alert was actually sent (i.e. down > 120s)
                log_error_and_notify(f"{self.__class__.__name__}: {self.ip} reconnected successfully ✅")

    def run(self):
        while True:
            try:
                logger.debug(f"{self.__class__.__name__}: Connecting to {self.ip}:{self.port}")
                with socket.socket() as client_socket:
                    # Fix 2: SO_KEEPALIVE detects dead connections at the TCP level
                    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    client_socket.connect((self.ip, self.port))
                    self._handle_reconnect()
                    while True:
                        data = client_socket.recv(1024)
                        if data:
                            if message_queue.qsize() > 50:
                                logger.warning(f"{self.__class__.__name__}: Queue full, discarding message: {data}")
                            else:
                                logger.debug(f"{self.__class__.__name__}: Received: {data}")
                                message_queue.put(data)
                        else:
                            self._handle_disconnect("connection closed by host")
                            sleep(10)
                            break
            except Exception:
                self._handle_disconnect(format_exception())
                sleep(30)

if __name__ == "__main__":
    logger.info("Starting application...")

    for idx, (ip, port) in enumerate(devices, start=1):
        if ip and port:
            thread = RFLinkThread(ip, port)
            thread.start()
        else:
            logger.info(f"RFLINK{idx} disabled")

    bridge_thread = BridgeThread(bridge_ip, bridge_port)
    bridge_thread.start()
    bridge_thread.join()
