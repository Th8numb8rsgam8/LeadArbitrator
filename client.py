from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import datetime
import time
import re, sys, os
import pickle
import socket
import subprocess
import random

import pdb

from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from base64 import urlsafe_b64decode, urlsafe_b64encode

# Google API dashboard https://console.cloud.google.com/apis/dashboard
# Google API Python setup: https://developers.google.com/gmail/api/quickstart/python

class EmailHandler:

    def __init__(self, user, source):
        self._user = user
        self._source = source
        self._scopes = ['https://mail.google.com/']
        self._lead_info_pattern = "Renter's Information\\r\\nName:\s*(.*)\\r\\nPhone:\s*(.*)\\r\\nEmail:\s*(.*)\\r\\nLead Submitted"

        self._gmail_api()
        self._get_responses()


    def _gmail_api(self):

        creds = None
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self._scopes)
                creds = flow.run_local_server(port=0)

            with open("token.pickle", "wb") as token:
                pickle.dump(creds, token)
    
        self._service = build("gmail", 'v1', credentials=creds)
        print("Gmail API authenticated.")


    def _get_responses(self):

        signature_file = Path("signature.txt")
        signature = signature_file.read_text()
        responses_dir = Path("responses")
        self._response_dict = {self._format_location_name(f.name): f.read_text() + signature for f in responses_dir.iterdir()}


    def _format_location_name(self, file_name):

        name = file_name.split(".")[0]
        capitalized = list(map(lambda x: x.capitalize(), name.split("_")))
        return " ".join(capitalized)


    def send_email(self, to_email, lead_info, handler=None):

        msg = MIMEMultipart()
        msg['From'] = self._user

        if handler:
            body = f'''
                {handler} Initiated lead for {lead_info["name"]}, who is interested in {lead_info["location"]}.
                Contact Info: email: {to_email}, phone: {lead_info["phone"]}.
                '''
            msg['To'] = self._user
            msg['Subject'] = "Lead Handled"
            msg.attach(MIMEText(body, 'plain'))

        else:
            if not self._response_dict.get(lead_info["location"]):
                print(f'{lead_info["location"]} is not one of the recorded locations.')
                return

            body = self._response_dict.get(lead_info["location"])
            msg['To'] = to_email
            msg['Subject'] = lead_info["location"]
            msg.attach(MIMEText(body, 'html'))

        try:
            self._service.users().messages().send(
                userId="me",
                body={"raw": urlsafe_b64encode(msg.as_bytes()).decode()}
            ).execute()
            if notify:
                print(f"Handled notification sent to {self._user}")
            else:
                print(f"Email sent to {to_email}")
        except Exception as e:
            self._log_error(e)


    def delete_email(self, msg_id):

        self._service.users().messages().delete(userId="me", id=msg_id).execute()


    def retrieve_leads(self):

        leads_info = {}
        result = self._service.users().messages().list(userId="me", q=f"in:inbox from:{self._source}").execute()

        if not result.get("messages"):
            return leads_info
        else:
            for message in result["messages"]:
                msg = self._service.users().messages().get(userId="me", id=message["id"], format="full").execute()
                payload = msg["payload"]
                headers = payload.get("headers")
                subject = [hdr["value"] for hdr in headers if hdr["name"].lower() == "subject"][0]

                try:
                    data = payload.get("body").get("data")
                    text = urlsafe_b64decode(data).decode()
                    soup = BeautifulSoup(text, 'html.parser')
                    lead_name = re.search("Name:\s*(.*)\r", text).groups()[0]
                    lead_phone = soup.select('a[href*=tel]')[0].decode_contents()
                    lead_email = soup.select('a[href*=mailto]')[0].decode_contents()
                    # lead_name, lead_phone, lead_email = lead_info = re.findall(self._lead_info_pattern, text)[0]
                    location = re.search("Apartments.com Network lead for (.*)", subject).groups()[0]
                    leads_info[lead_email] = {
                        "name": lead_name, 
                        "phone": lead_phone,
                        "msg_id": message["id"],
                        "location": location}
                except IndexError as e:
                    self._log_error(e)
        
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
            'Get-NetAdapter -Physical | Where-Object {$_.Status -eq "Up" -and ($_.Name -like "*Wi-Fi*" -or "*Wireless*")}'],
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
                    lead_handler = data.decode().split(" by ")
                    handler = lead_handler[-1]
                    handled_lead = lead_handler[0].split("Handled Lead: ")[1]
                    try:
                        tgt_info = leads.pop(handled_lead)
                        print(f"Deleting handled lead from {handled_lead}...")
                        self._email_handler.delete_email(tgt_info["msg_id"])
                        self._email_handler.send_email(handled_lead, tgt_info, handler=handler)
                    except KeyError:
                        print(f"{handled_lead} not in client's inbox")

                previous_broadcast = info
            
            time.sleep(2)


if __name__ == "__main__":

    user = "rebecca.crites@thewindsorcompanies.com"
    source = "daytonleasing@thewindsorcompanies.com"

    email_handler = EmailHandler(user, source)
    client_handler = ClientHandler(email_handler)
    client_handler.manage_client()
