import re, sys
import queue
import argparse
import sqlite3
import threading
import socket
import time
import subprocess
from pathlib import Path
import pdb


def num_clients_to_serve():

    cli_parser = argparse.ArgumentParser(
        prog="LeadArbitrator"
    )
    cli_parser.add_argument(
        "num_clients",
        type=int,
        help="Number of clients to connect before starting token rotation."
    )
    num_clients = vars(cli_parser.parse_args())["num_clients"]

    if num_clients < 1:
        print("ERROR: Must serve at least one client.")
        sys.exit(1)

    return num_clients


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


def handle_client(client_socket, broadcast_socket):

    conn = sqlite3.connect('leads.db')
    cursor = conn.cursor()
    client_name = None
    broadcast_addr = None

    while True:

        data = client_socket.recv(1024)
        if "Hello from client" in data.decode():
            client_name, broadcast_addr = re.search("Client:\s*(.*),\s*Broadcast:\s*(.*)", data.decode()).groups()
            print(f"Client name: {client_name}.")
            client_socket.send(f"Client name received by server.".encode())

            cursor.execute(f"SELECT name, token FROM employees WHERE name = '{threading.current_thread().name}'")
            name, token = cursor.fetchone()
            if token:
                broadcast_socket.sendto(f"Token: {name}".encode(), (broadcast_addr, 12345))

        elif "Token Release" in data.decode():
            handled_lead = data.decode().split("Token Release for ")[1]
            broadcast_socket.sendto(f"Handled Lead: {handled_lead}".encode(), (broadcast_addr, 12345))

            clients = ["\'"+thread.name+"\'" for thread in threading.enumerate() if thread.name != "MainThread"]
            client_query = "(" + ", ".join(clients) + ")"
            cursor.execute("SELECT name, token FROM employees WHERE name IN " + client_query)
            info = cursor.fetchall()
            print(f"{threading.current_thread().name} releasing token {info}")
            tokens = [val[1] for val in info]
            rotated_tokens = tokens[1:] + tokens[:1]
            for idx, token in enumerate(rotated_tokens):
                cursor.execute(f"UPDATE employees SET token = {str(token)} WHERE name = '{info[idx][0]}'")
            conn.commit()

            cursor.execute("SELECT name FROM employees WHERE token = 1")
            name = cursor.fetchone()[0]
            broadcast_socket.sendto(f"Token: {name}".encode(), (broadcast_addr, 12345))

        time.sleep(5)


# Setup database to track leads
def setup_database():

    if not Path("leads.db").exists():
        conn = sqlite3.connect('leads.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS employees (name TEXT, email TEXT, token INTEGER)''')
        data = [
            ('Rebecca', 'rebecca.crites@thewindsorcompanies.com', '0'),
            # ('Gabriele', 'gabrielle.batsche@thewindsorcompanies.com', '0'),
            # ('Tim', 'tim.peffley@thewindsorcompanies.com', '0'),
            ('DESKTOP-18R4AM7', 'alien@ware.com', '0'),
            ('DESKTOP-F8DKQV0', 'igrkeene@gmail.com', '1')
        ]

        try:
            cursor.executemany('''INSERT INTO employees (name, email, token) VALUES (?, ?, ?)''', data)
        except sqlite3.IntegrityError:
            pass

        # cursor.executemany('''INSERT INTO employees (name, email) VALUES ('Rebecca', 'rebecca.crites@thewindsorcompanies.com')''')
        # INSERT INTO employees (email) VALUES ('gabrielle.batsche@thewindsorcompanies.com');
        # INSERT INTO employees (email) VALUES ('tim.peffley@thewindsorcompanies.com');
        # cursor.execute('''CREATE TABLE IF NOT EXISTS lead_assignments (id INTEGER PRIMARY KEY, employee_id INTEGER)''')
        # cursor.execute('''CREATE TABLE IF NOT EXISTS properties (id INTEGER PRIMARY KEY, name TEXT, studio_price REAL, one_bedroom_price REAL, two_bedroom_price REAL)''')
        # cursor.execute('''CREATE TABLE IF NOT EXISTS conversion_tracking (id INTEGER PRIMARY KEY, lead_email TEXT, converted BOOLEAN)''')
        conn.commit()
        conn.close()


def manage_server(num_clients):

    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = subprocess.run(["nslookup", socket.gethostname()], capture_output=True, text=True)
    server_ip = re.search("(?<=Address:)\s*(\d+\.\d+\.\d+\.\d+)", result.stdout).group().strip()
    server_socket.bind((server_ip, 5000))
    server_socket.listen(1)

    print("Server listening on port 5000.")

    client_threads = []
    while True:
        client_socket, addr = server_socket.accept()
        client_info = subprocess.run(["powershell", "nslookup", f"{addr}"], capture_output=True, text=True)
        client_name = re.search("(?<=Name:)\s*(.*)\.", client_info.stdout).groups()[0]
        print(f"Connection from {client_name}:{addr}")
        thread = threading.Thread(
            name=client_name,
            target=handle_client, 
            args=(client_socket, broadcast_socket))
        client_threads.append(thread)
        if len(client_threads) == num_clients:
            break

    for t in client_threads:
        t.start()
        time.sleep(5)


if __name__ == "__main__":

    num_clients = num_clients_to_serve()
    check_wifi_connection()
    setup_database()
    manage_server(num_clients)