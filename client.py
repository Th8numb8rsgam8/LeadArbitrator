# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# import sqlite3
# import datetime

import time
import re, sys
import imaplib, email
import socket
import subprocess
import pdb

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


def get_network():

    gateway_search = subprocess.run(
        ["powershell", "-Command", 
        "Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Select-Object NextHop"],
        capture_output=True,
        text=True,
        shell=True)
    gateway_ip = re.search("\d+\.\d+\.\d+\.\d+", gateway_search.stdout).group()
    network = ".".join(gateway_ip.split(".")[:-1])

    return network
    

def connect_to_server(network, host, client_socket):
    potential_server = subprocess.run(["powershell", "nslookup", f"{network}.{host}"], capture_output=True, text=True)
    try:
        server_name = re.search("(?<=Name:)(.*)", potential_server.stdout).group().strip()
        try:
            print(f"Attempting to connect to {server_name}...")
            client_socket.connect((f"{network}.{host}", 5000))
            client_socket.send(f"Hello from client: {socket.gethostname()}".encode())
            data = client_socket.recv(1024)
            print(f"{data.decode()}")
            return True
        except ConnectionRefusedError:
            pass
        except TimeoutError:
            pass
    except AttributeError:
        pass
    
    return False


def manage_client(client_socket):

    token = 0
    try:
        while True:
            client_socket.send("Token Request".encode())
            data = client_socket.recv(1024)
            if "Token" in data.decode():
                token = int(re.search("\d", data.decode()).group())
                print(f"Token Received: {token}")
                if token:
                    print("Sending email")
                    client_socket.send("Token Release for bigboii@bigG.com".encode())
            elif "Handled Lead" in data.decode():
                handled_lead = data.decode().split("Handled Lead: ")[1]
                print(f"Deleting handled lead {handled_lead}")
            time.sleep(1)
    except OSError as e:
        print(str(e))
        sys.exit(1)


if __name__ == "__main__":

    check_wifi_connection()

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    network = get_network()

    for host in range(254):
       if connect_to_server(network, host, client_socket):
            break
    
    manage_client(client_socket)