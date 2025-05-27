import socket
import ssl
import threading
import os
import struct
from concurrent.futures import ThreadPoolExecutor

# ----------------------------------------------------------------------------
# Server Configuration
# ----------------------------------------------------------------------------

# Server Configuration
SERVER_IP = '0.0.0.0'
SERVER_PORT = 4444
certfile = '/home/bmac60714/server.crt'  # Replace with your actual certificate path
keyfile = '/home/bmac60714/server.key'   # Replace with your actual key path

# ----------------------------------------------------------------------------
# SSL Context Setup
# ----------------------------------------------------------------------------
def create_ssl_context():
    """
    Create SSL Context for secure connections.
    For mutual TLS, you would also add CA verification here.
    """
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    # If you want the server to verify the client, add:
    # context.verify_mode = ssl.CERT_REQUIRED
    # context.load_verify_locations(cafile='/path/to/ca.crt')
    return context

# ----------------------------------------------------------------------------
# Whitelisted Commands & Handling
# ----------------------------------------------------------------------------
# A broader set of possible commands. Adjust as needed.
# The dictionary maps command -> short description (optional).
# In real usage, you’d have server-side handler logic for each.


# Whitelisted commands for security
ALLOWED_COMMANDS = {
    # System / Device Info
    "battery_status":         "Query battery level/state",
    "storage_status":         "Query disk usage/state",
    "device_info":            "Query general device info",
    "system_info":            "Query system info like OS, architecture",
    "os_version":             "Query OS version",
    "cpu_info":               "Get CPU info",
    "ram_info":               "Get RAM usage info",

    # Network Info
    "wifi_status":            "Get WiFi info/status",
    "cellular_status":        "Get cellular info/status",
    "bluetooth_status":       "Check Bluetooth status",

    # Logs & Diagnostics
    "fetch_logs":             "Retrieve logs (system/app)",
    "process_list":           "List running processes",
    "crash_report":           "Retrieve last crash report(s)",

    # Hardware States
    "camera_status":          "Check camera hardware state",
    "sensor_status":          "Check sensor states (accelerometer, etc.)",
    "mic_status":             "Check microphone state",

    # Phone & App
    "call_logs":              "Retrieve call logs",
    "sms_logs":               "Retrieve SMS logs",
    "installed_apps":         "List installed applications",

    # Location
    "gps_status":             "Get GPS status",
    "location_info":          "Retrieve last known location",

    # File & Directory Operations
    "list_directory":         "List contents of a directory path",
    "read_file":              "Read the contents of a file path",
    "delete_file":            "Delete a specified file",
    "rename_file":            "Rename or move a file",
    "copy_file":              "Copy a file to a new path",
    "mkdir":                  "Create a new directory",
    "rmdir":                  "Remove a directory (with caution)",

    # File Transfer & Execution
    "push_file":              "Transfer (push) a file to the client device",
    "exec_file":              "Execute a file/binary on the client device",

    # System Management (Potentially Dangerous)
    "reboot_device":          "Reboot the device",
    "shutdown_device":        "Shut down the device",
    "factory_reset":          "Perform a factory reset (very dangerous)",
    "kill_process":           "Force kill a process by PID or name",
    "start_service":          "Start a background service (requires service name/ID)",
    "stop_service":           "Stop a background service",
    "install_app":            "Install an application package",
    "uninstall_app":          "Uninstall an application package",

    # Permissions & Access Control
    "list_system_permissions": "List system-level permissions",
    "get_permission_status":   "Check current permission states for an app or system",
    "grant_permission":        "Grant a system permission (often restricted to root/system)",
    "revoke_permission":       "Revoke a previously granted system permission",

    # Screen / Media
    "capture_screenshot":     "Capture a screenshot of the current screen",
    "record_screen":          "Start/stop screen recording (if supported)",
    "record_audio":           "Start/stop audio recording",
    "record_video":           "Start/stop video recording",
}

def handle_command(command: str, client_socket: socket.socket):
    """
    Basic server-side dispatcher:
    - Validate the command is allowed
    - Perform any server-side pre-processing if needed
    - Relay command to the client for execution
    """
    # Example server-side checks before sending to the client
    if command not in ALLOWED_COMMANDS:
        # We’ll return a special message indicating it's unauthorized
        message = f"UNAUTHORIZED: {command}"
        client_socket.sendall((message + "\n").encode('utf-8'))
        return False
    else:
        # If authorized, send the command to the client
        client_socket.sendall((command + "\n").encode('utf-8'))
        return True

# ----------------------------------------------------------------------------
# Threaded Client Handler
# ----------------------------------------------------------------------------
def client_handler(client_socket, address):
    """
    Handle commands for a single client in a dedicated thread.
    """
    print(f"[+] Connected to {address}")

    try:
        while True:
            # Prompt the server operator for a command
            cmd = input("Enter command (type 'exit' to disconnect client): ").strip()
            if cmd.lower() == "exit":
                print(f"[-] Disconnecting {address}")
                break

            # Attempt to dispatch command
            authorized = handle_command(cmd, client_socket)
            if not authorized:
                print("[!] Unauthorized command attempted.")
                continue

            # --------------------------
            # Now read the response from the client using a length prefix
            # --------------------------
            # First, read the 4-byte length prefix
            prefix_data = client_socket.recv(4)
            if len(prefix_data) < 4:
                print("[!] Client disconnected or invalid response prefix.")
                break

            message_length = struct.unpack('!I', prefix_data)[0]

            # Now read message_length bytes
            chunks = []
            bytes_received = 0
            while bytes_received < message_length:
                data = client_socket.recv(min(4096, message_length - bytes_received))
                if not data:
                    print("[!] Connection closed while receiving data.")
                    break
                chunks.append(data)
                bytes_received += len(data)

            full_message = b''.join(chunks).decode('utf-8')
            print(f"[{address} Response] {full_message}")

    except Exception as e:
        print(f"[!] Error in client handler for {address}: {e}")
    finally:
        client_socket.close()
        print(f"[+] Connection closed for {address}")

# Set up the socket server
# ----------------------------------------------------------------------------
# Main Server Loop (with ThreadPool)
# ----------------------------------------------------------------------------
def main():
    # Create SSL context
    context = create_ssl_context()

    # Create the server socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((SERVER_IP, SERVER_PORT))
        server_socket.listen(5)
        print(f"Secure Android Shell Server running on {SERVER_IP}:{SERVER_PORT}")

        # Wrap the socket to use SSL
        with context.wrap_socket(server_socket, server_side=True) as ssock:
            print("[*] Waiting for incoming TLS connections...")

            # Thread pool to handle multiple clients
            with ThreadPoolExecutor(max_workers=5) as executor:
                while True:
                    try:
                        client_socket, addr = ssock.accept()
                    except ssl.SSLError as ssl_err:
                        print(f"[!] SSL error during accept: {ssl_err}")
                        continue

                    # Once a client connects, handle in a new thread
                    executor.submit(client_handler, client_socket, addr)

# ----------------------------------------------------------------------------
# Entry Point
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    main()
