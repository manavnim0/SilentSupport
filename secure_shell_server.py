import socket
import ssl

# Server Configuration
server_ip = '0.0.0.0'
server_port = 4444
certfile = '/home/manav/bmac/server.crt'  # Replace with your actual certificate path
keyfile = '/home/manav/bmac/server.key'   # Replace with your actual key path

# Create SSL Context for secure connections
context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain(certfile=certfile, keyfile=keyfile)

# Whitelisted commands for security
allowed_commands = {"battery_status", "storage_status", "device_info", "wifi_status", "cellular_status"}

# Set up the socket server
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind((server_ip, server_port))
    sock.listen(5)
    print(f"Secure Android Shell Server running on 34.69.184.31:4444")

    with context.wrap_socket(sock, server_side=True) as ssock:
        while True:
            client_socket, addr = ssock.accept()
            print(f"Connected to {addr}")

            try:
                while True:
                    cmd = input("Enter command (type 'exit' to disconnect): ").strip()
                    if cmd == "exit":
                        break
                    if cmd not in allowed_commands:
                        print("Unauthorized command attempted.")
                        continue
                    
                    client_socket.sendall((cmd + "\n").encode('utf-8'))
                    response = client_socket.recv(4096).decode('utf-8').strip()
                    print(f"Client Response: {response}")

            except Exception as e:
                print(f"Connection error: {e}")
            finally:
                client_socket.close()
                print("Client disconnected.")
