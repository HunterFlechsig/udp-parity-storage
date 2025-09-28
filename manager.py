import socket;
import json;
import select;

HOST = '127.0.0.1';
PORT = 65432;

user_data = {};
disk_data = {};
message_types = ["register-user", "register-disk", "shutdown"];

def register_user(message):    
    # Check if all required fields exist
    required_fields = ['user-name', 'Ipv4', 'm-port', 'c-port'];
    for field in required_fields:
        if field not in message['data']:
            print(f"✗ Missing field: {field}");
            return False;

    user_data[message['data']['user-name']] = message['data'];

    return True;


def register_disk(message):
    # Check if all required fields exist
    required_fields = ['disk-name', 'Ipv4', 'm-port', 'c-port'];
    for field in required_fields:
        if field not in message['data']:
            print(f"✗ Missing field: {field}");
            return False;

    disk_data[message['data']['disk-name']] = message['data'];
    return True;

#create a socket object
# AF_INET is the address family for IPv4
# SOCK_DGRAM is the socket type for UDP
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind((HOST, PORT));
    print(f"UDP Server listening on {HOST}:{PORT}");
    
    while True:

        try:
            #receive data from the client
            data = None;
            r, _, _ = select.select([s], [], [], 1.0)
            if r:
                data, addr = s.recvfrom(1024)

            if not data:
                continue;

            message = json.loads(data.decode());
            print(f"Received from {addr}: {message['type']}");

            if message['type'] not in message_types:
                print(f"Invalid message type: {message['type']}");
                continue;

            if message['type'] == "register-user":
                register_user(message);
            elif message['type'] == "register-disk":
                register_disk(message);

            print(user_data);

            if not data:
                break;
            #send data to the client
            s.sendto(data, addr);
            
        except KeyboardInterrupt:
            print("\nCtrl+C pressed, shutting down...")
            break;

            