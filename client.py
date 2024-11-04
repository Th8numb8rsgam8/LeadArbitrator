# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# import sqlite3
# import datetime

import time
import re, sys
import multiprocessing as mp
import imaplib, email
import socket
import subprocess
import pdb

# Setup database to track leads
def setup_database():
    conn = sqlite3.connect('leads.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY, email TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS lead_assignments (id INTEGER PRIMARY KEY, employee_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS properties (id INTEGER PRIMARY KEY, name TEXT, studio_price REAL, one_bedroom_price REAL, two_bedroom_price REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS conversion_tracking (id INTEGER PRIMARY KEY, lead_email TEXT, converted BOOLEAN)''')
    conn.commit()
    return conn

# Function to send email
def send_email(to_email, subject, body):
    from_email = "your_email@example.com"  # Replace with your email
    password = "your_password"  # Replace with your password

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)  # Change if using another email service
        server.starttls()
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        log_error(e)

# Function to log errors
def log_error(error):
    with open("error_log.txt", "a") as f:
        f.write(f"{datetime.datetime.now()}: {str(error)}\n")

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

# Function to fetch property pricing
def get_property_pricing(conn, property_name):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM properties WHERE name=?", (property_name,))
    return cursor.fetchone()

# Function to get the current greeting
def get_greeting():
    current_hour = datetime.datetime.now().hour
    if current_hour < 12:
        return "Good morning"
    elif current_hour < 18:
        return "Good afternoon"
    else:
        return "Good evening"

# Function to process incoming lead
def process_lead(lead_email, property_name, apartment_type):
    conn = setup_database()
    
    assigned_employee_email = assign_lead(conn)

    # Fetch pricing information based on the property and apartment type
    property_info = get_property_pricing(conn, property_name)
    if property_info:
        if apartment_type.lower() == "studio":
            price = property_info[2]  # studio_price
        elif apartment_type.lower() == "one bedroom":
            price = property_info[3]  # one_bedroom_price
        elif apartment_type.lower() == "two bedroom":
            price = property_info[4]  # two_bedroom_price
        else:
            price = "not available"
    else:
        price = "not available"

    # Construct the email body
    greeting = get_greeting()
    body = (f"{greeting},\n\n"
            f"Thank you for your inquiry about {property_name}!\n\n"
            f"We have a luxurious selection of apartments:\n"
            f"- Studios starting at ${price}.\n"
            f"- One bedrooms starting at ${price}.\n"
            f"- Two bedrooms starting at ${price}.\n\n"
            f"Additionally, we offer a move-in special with a $499 non-refundable deposit and your first month half off!\n\n"
            f"Please let us know what day you would like to schedule a tour, and feel free to ask if you have any further questions.\n\n"
            f"Note: There are other small community fees, but our prices remain competitive!\n"
            f"We look forward to helping you find your new home!\n\n"
            f"Best regards,\n"
            f"Your Leasing Team")

    send_email(assigned_employee_email, f"New Inquiry for {apartment_type} at {property_name}", body)

    # Track the lead conversion (placeholder for analytics)
    track_conversion(lead_email)

    conn.close()

# Function to track conversion rates
def track_conversion(lead_email):
    conn = sqlite3.connect('leads.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conversion_tracking (lead_email, converted) VALUES (?, ?)", (lead_email, False))
    conn.commit()
    conn.close()

# Example usage
# Call process_lead with the lead's email, property name, and apartment type based on the incoming lead
# process_lead("example_lead@example.com", "Home Telephone Lofts", "One Bedroom")


# To populate employee and property data
# INSERT INTO employees (email) VALUES ('rebecca.crites@thewindsorcompanies.com');
# INSERT INTO employees (email) VALUES ('gabrielle.batsche@thewindsorcompanies.com');
# INSERT INTO employees (email) VALUES ('tim.peffley@thewindsorcompanies.com');
# 
# INSERT INTO properties (name, studio_price, one_bedroom_price, two_bedroom_price) VALUES 
# ('Home Telephone Lofts', 1050, 1245, 1650),
# ('Grafton House', NULL, NULL, 1600),
# ('320 Grafton Ave', NULL, 725, NULL),
# ('Arbors North', NULL, 1020, 1020),
# ('Garland Court', NULL, 850, 975),
# ('Graphic Arts Lofts', 1020, 1200, 1400),
# ('The Fireblocks District', 950, 1075, 1550),
# ('The Deneau', 1220, 1500, 1600),
# ('310-316 Superior Ave', NULL, 725, NULL);

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


if __name__ == "__main__":
    # user = "igrkeene@gmail.com"
    # password = "gkwensfxosnwggrc"
    # imap_url = "imap.gmail.com"

    # con = imaplib.IMAP4_SSL(imap_url)
    # con.login(user, password)
    # con.select("Inbox")
    # result, data = con.search(None, "FROM", "amber@kirklandsommers.com")
    # typ, data = con.fetch(b'24180', '(RFC822)')
    # msg = email.message_from_bytes(data[0][1])
    # msg.get_payload()
    # pdb.set_trace()

    # print("LOGGED IN")

    check_wifi_connection()

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    gateway_search = subprocess.run(
        ["powershell", "-Command", 
        "Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Select-Object NextHop"],
        capture_output=True,
        text=True,
        shell=True)
    gateway_ip = re.search("\d+\.\d+\.\d+\.\d+", gateway_search.stdout).group()
    network = ".".join(gateway_ip.split(".")[:-1])
    for host in range(254):
        host_info = subprocess.run(["powershell", "nslookup", f"{network}.{host}"], capture_output=True, text=True)
        try:
            host_name = re.search("(?<=Name:)(.*)", host_info.stdout).group().strip()
            print(host_name)
            try:
                client_socket.connect((f"{network}.{host}", 5000))
                client_socket.send(f"Hello from client: {socket.gethostname()}".encode())
                data = client_socket.recv(1024)
                print(f"Received: {data.decode()}")
                break
            except ConnectionRefusedError:
                pass
            except TimeoutError:
                pass
        except AttributeError:
            pass
    
    while True:
        client_socket.send(socket.gethostname().encode())
        data = client_socket.recv(1024)
        print(f"Received: {data.decode()}")
        time.sleep(1)

    # client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # while True:
    #     server_ip = "192.168.1.159"
    #     port = 5000

    #     client_socket.connect((server_ip, port))
    #     client_socket.send("Hello from the client!".encode())

    #     data = client_socket.recv(1024)

    #     print(f"Received: {data.decode()}")

    # client_socket.close()

################################################################################

    # s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # s.bind(('', 12345))

    # while True:
    #     data = s.recv(1024)
    #     print(f"Received broadcast message: {data.decode()}")