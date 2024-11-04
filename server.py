import re
import threading
import socket
import subprocess
import pdb


def check_wifi_connection():
    wifi_connection = subprocess.run(
        ["powershell", "-Command", 
        'Get-NetAdapter -Physical | Where-Object {$_.Status -eq "Up" -and $_.Name -like "*Wi-Fi*"}'],
        capture_output=True,
        text=True,
        shell=True)

    if wifi_connection.stdout == "":
        print("Not connected to WiFi!")
        sys.exit(1)


def handle_client(client_socket):
    while True:
        data = client_socket.recv(1024)
        if not data:
            continue
        print(f"Received: {data.decode()}")
        client_socket.send("Message Received!".encode())



# broadcast_ip = ".".join(server_ip.split(".")[:-1]) + ".255"
# 
# broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
# message = hostname + ":" + server_ip
# broadcast_socket.sendto(message.encode(), (broadcast_ip, 12345))

if __name__ == "__main__":
    check_wifi_connection()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    hostname = socket.gethostname()
    result = subprocess.run(["nslookup", hostname], capture_output=True, text=True)
    server_ip = re.search("(?<=Address:)\s*(\d+\.\d+\.\d+\.\d+)", result.stdout).group().strip()
    server_socket.bind((server_ip, 5000))
    server_socket.listen(1)

    print("Server listening on port 5000.")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr}")
        thread = threading.Thread(target=handle_client, args=(client_socket,))
        thread.start()