import re
import sqlite3
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


# Function to assign lead to employee in rotation
def assign_lead(conn):
    cursor = conn.cursor()
    
    # Get list of employees
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()

    # Determine next employee in rotation
    cursor.execute("SELECT employee_id FROM lead_assignments ORDER BY id DESC LIMIT 1")
    last_assignment = cursor.fetchone()

    # Rotate through employees
    if last_assignment:
        last_employee_id = last_assignment[0]
        next_employee_id = (last_employee_id % len(employees)) + 1
    else:
        next_employee_id = 1

    # Insert new assignment into database
    cursor.execute("INSERT INTO lead_assignments (employee_id) VALUES (?)", (next_employee_id,))
    conn.commit()

    # Fetch email of assigned employee
    cursor.execute("SELECT email FROM employees WHERE id=?", (next_employee_id,))
    assigned_employee_email = cursor.fetchone()[0]

    return assigned_employee_email


# Setup database to track leads
def setup_database():
    conn = sqlite3.connect('leads.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS employees (name TEXT PRIMARY KEY, email TEXT)''')
    data = [
        ('Rebecca', 'rebecca.crites@thewindsorcompanies.com'),
        ('Gabriele', 'gabrielle.batsche@thewindsorcompanies.com'),
        ('Tim', 'tim.peffley@thewindsorcompanies.com')
    ]

    try:
        cursor.executemany('''INSERT INTO employees (name, email) VALUES (?, ?)''', data)
    except sqlite3.IntegrityError:
        pass

    # cursor.executemany('''INSERT INTO employees (name, email) VALUES ('Rebecca', 'rebecca.crites@thewindsorcompanies.com')''')
    # INSERT INTO employees (email) VALUES ('gabrielle.batsche@thewindsorcompanies.com');
    # INSERT INTO employees (email) VALUES ('tim.peffley@thewindsorcompanies.com');
    # cursor.execute('''CREATE TABLE IF NOT EXISTS lead_assignments (id INTEGER PRIMARY KEY, employee_id INTEGER)''')
    # cursor.execute('''CREATE TABLE IF NOT EXISTS properties (id INTEGER PRIMARY KEY, name TEXT, studio_price REAL, one_bedroom_price REAL, two_bedroom_price REAL)''')
    # cursor.execute('''CREATE TABLE IF NOT EXISTS conversion_tracking (id INTEGER PRIMARY KEY, lead_email TEXT, converted BOOLEAN)''')
    conn.commit()
    return conn


def manage_server():

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = subprocess.run(["nslookup", socket.gethostname()], capture_output=True, text=True)
    server_ip = re.search("(?<=Address:)\s*(\d+\.\d+\.\d+\.\d+)", result.stdout).group().strip()
    server_socket.bind((server_ip, 5000))
    server_socket.listen(1)

    print("Server listening on port 5000.")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr}")
        thread = threading.Thread(target=handle_client, args=(client_socket,))
        thread.start()

# broadcast_ip = ".".join(server_ip.split(".")[:-1]) + ".255"
# 
# broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
# message = hostname + ":" + server_ip
# broadcast_socket.sendto(message.encode(), (broadcast_ip, 12345))

if __name__ == "__main__":

    conn = setup_database()
    check_wifi_connection()
    manage_server()