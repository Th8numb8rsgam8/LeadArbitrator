from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import imaplib, email, smtplib
from pathlib import Path
import datetime
import time
import re, sys
import socket
import subprocess
import random

import pdb

# To set up app password, go to https://myaccount.google.com/apppasswords
class EmailHandler:

    def __init__(self, user, password, source):
        self._user = user
        self._password = password
        self._source = source
        self._imap_url = "imap.gmail.com"
        self._smtp_url = "smtp.gmail.com"

        self._imap = imaplib.IMAP4_SSL(self._imap_url)
        self._imap.login(user, password)
        self._get_responses()


    def _get_responses(self):

        signature_file = Path("signature.txt")
        signature = signature_file.read_text()
        responses_dir = Path("responses")
        self._response_dict = {f.name.split(".")[0]: f.read_text() + signature for f in responses_dir.iterdir()}


    def send_email(self, to_email, lead_info, notify=False):

        msg = MIMEMultipart()
        msg['From'] = self._user

        if notify:
            body = f"Handled lead for {to_email}"
            msg['To'] = self._user
            msg['Subject'] = "Lead Handled"
            msg.attach(MIMEText(body, 'plain'))
        else:
            body = self._response_dict[lead_info["Location Name"]]
            msg['To'] = to_email
            msg['Subject'] = "Location Name"
            msg.attach(MIMEText(body, 'html'))

        try:
            smtp = smtplib.SMTP(self._smtp_url, 587)  # Change if using another email service
            smtp.starttls()
            smtp.login(self._user, self._password)
            smtp.send_message(msg)
            smtp.quit()
            if notify:
                print(f"Handled notification sent to {self._user}")
            else:
                print(f"Email sent to {to_email}")
        except Exception as e:
            self._log_error(e)


    def delete_email(self, msg_id):

        self._imap.store(msg_id, "+FLAGS", "\\Deleted")
        self._imap.expunge()


    def retrieve_leads(self):

        leads_info = {}
        self._imap.select("Inbox")
        result, messages = self._imap.search(None, "FROM", self._source)
        message_list = messages[0].split(b' ')
        if len(message_list) == 1 and message_list[0] == b'':
            return leads_info
        else:
            for message in message_list:
                _, msg = self._imap.fetch(message, '(RFC822)')
                msg_data = email.message_from_bytes(msg[0][1])
                payload = msg_data.get_payload()[1].get_payload()
                print("Parse Payload for relevant info.")
                leads_info[msg_data["Subject"]] = payload
        
            return leads_info


    # Function to log errors
    def _log_error(self, error):
        with open("error_log.txt", "a") as f:
            f.write(f"{datetime.datetime.now()}: {str(error)}\n")


# Function to get the current greeting
def get_greeting():

    current_hour = datetime.datetime.now().hour
    if current_hour < 12:
        return "Good morning"
    elif current_hour < 18:
        return "Good afternoon"
    else:
        return "Good evening"


class ClientHandler:

    def __init__(self, email_handler):

        self._check_wifi_connection()
        self._client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._email_handler = email_handler
        self._setup_broadcast_socket()
        self._get_network()

        for host in range(254):
           if self._connect_to_server(host):
                break


    def _check_wifi_connection(self):

        wifi_connection = subprocess.run(
            ["powershell", "-Command", 
            'Get-NetAdapter -Physical | Where-Object {$_.Status -eq "Up" -and $_.Name -like "*Wi-Fi*"}'],
            capture_output=True,
            text=True,
            shell=True)

        if wifi_connection.stdout == "":
            print("Not connected to WiFi!")
            sys.exit(1)


    def _setup_broadcast_socket(self):

        self._broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._broadcast_socket.bind(('', 12345))


    def _get_network(self):

        gateway_search = subprocess.run(
            ["powershell", "-Command", 
            "Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Select-Object NextHop"],
            capture_output=True,
            text=True,
            shell=True)
        gateway_ip = re.search("\d+\.\d+\.\d+\.\d+", gateway_search.stdout).group()
        self._network = ".".join(gateway_ip.split(".")[:-1])
        

    def _connect_to_server(self, host):

        potential_server = subprocess.run(["powershell", "nslookup", f"{self._network}.{host}"], capture_output=True, text=True)
        try:
            server_name = re.search("(?<=Name:)(.*)", potential_server.stdout).group().strip()
            try:
                print(f"Attempting to connect to {server_name}...")
                self._client_socket.connect((f"{self._network}.{host}", 5000))
                self._client_socket.send(f"Hello from client. Client: {socket.gethostname()}, Broadcast: {self._network}.255".encode())
                data = self._client_socket.recv(1024)
                print(f"{data.decode()}")
                return True
            except ConnectionRefusedError as e:
                pass
            except TimeoutError as e:
                pass
        except AttributeError:
            pass
        
        return False


    def manage_client(self):

        previous_broadcast = None
        inbox_empty = False
        while True:
            leads = self._email_handler.retrieve_leads()
            data, addr = self._broadcast_socket.recvfrom(8192)
            info = data.decode()
            if info != previous_broadcast or inbox_empty:
                if "Token" in info and socket.gethostname() in info:
                    try:
                        tgt_email, tgt_info = leads.popitem()
                        print(f"SENDING EMAIL {tgt_email}...")
                        self._email_handler.send_email(tgt_email, tgt_info)
                        self._client_socket.send(f"Token Release for {tgt_email}".encode())
                        inbox_empty = False
                    except KeyError:
                        print("No leads found in inbox.")
                        self._client_socket.send("No Leads.".encode())
                        inbox_empty = True
                elif "Handled Lead" in info:
                    handled_lead = data.decode().split("Handled Lead: ")[1]
                    try:
                        tgt_info = leads.pop(handled_lead)
                        print(f"Deleting handled lead from {handled_lead}...")
                        self._email_handler.delete_email(handled_lead, tgt_info["Email Id"])
                        self._email_handler.send_email(handled_lead, tgt_info, notify=True)
                    except KeyError:
                        print(f"{handled_lead} not in client's inbox")

                previous_broadcast = info
            
            time.sleep(2)


if __name__ == "__main__":

    user = "igrkeene@gmail.com"
    password = "gkwensfxosnwggrc"
    source = "b1gbo1j@yahoo.com"

    email_handler = EmailHandler(user, password, source)
    client_handler = ClientHandler(email_handler)
    client_handler.manage_client()