# manager.py
# Hunter Flechsig, 1225292005
# Create a manager process
# Manager process is responsible for orchestrating the user and disk processes and the dss

import socket;
import json;
import select;
import getopt;
import sys;

# Default configuration
HOST = '127.0.0.1';
PORT = 31500;

# Command line argument parsing
args = sys.argv[1:]
options = "hi:p:h"
long_options = ["ip", "port", "help"]

try:
    arguments, values = getopt.getopt(args, options, long_options)
    for currentArg, currentVal in arguments:
        if currentArg in ("-h", "--help"):
            print("Manager Process Help \n" 
                " -i, --ip: IP address to bind the manager to (default: 127.0.0.1) \n"
                " -p, --port: Port number to bind the manager to (default: 31500) \n"
            )
            sys.exit(0)
        elif currentArg in ("-i", "--ip"):
            HOST = currentVal
        elif currentArg in ("-p", "--port"):
            try:
                PORT = int(currentVal)
            except ValueError:
                print("❌ Error: Invalid port (-p or --port) value")
                sys.exit(1)
except getopt.error as err:
    print(str(err))
    sys.exit(1)

# Validate port range
if not (31500 <= PORT <= 31999):
    print(f"❌ Error: Port {PORT} must be in range 31500-31999")
    sys.exit(1)

# data-structures to store the user, disk, and dss information
user_data = {};
disk_data = {};
dss_data = {};

free_disks = set();
used_ports = set();
#-------------------------------------------------------------

#----------------------- Helpers -----------------------#
# Check if a user exists
def user_exists(addr):
    for user in user_data:
        if user_data[user]['Ipv4'] == addr[0] and user_data[user]['m-port'] == addr[1]:
            return True;
    return False;

# helpers to ensure data-structures consistency when adding and removing users and disks
def add_user(user):
    user_data[user['user-name']] = user;
    used_ports.add(user['m-port']);
    used_ports.add(user['c-port']);

def add_disk(disk):
    disk_data[disk['disk-name']] = disk;
    free_disks.add(disk['disk-name']);
    used_ports.add(disk['m-port']);
    used_ports.add(disk['c-port']);

def remove_user(user):
    used_ports.remove(user['m-port']);
    used_ports.remove(user['c-port']);
    user_data.pop(user['user-name']);


def remove_disk(disk):
    free_disks.remove(disk['disk-name']);
    used_ports.remove(disk['m-port']);
    used_ports.remove(disk['c-port']);
    disk_data.pop(disk['disk-name']);

# Helper to send a response to the user or disk process
def response(success, message, addr):
    data = {
        "status": "success" if success else "failure",
        "message": message
    }
    print(f"Sending response to {addr[0]}:{addr[1]}")
    print(f"   Response data: {json.dumps(data, indent=2)}")
    s.sendto(json.dumps(data).encode(), addr);
    return data;
#-----------------------------------------------------------------------------------

#----------------------- Commands to handle messages from user and disk processes -----------------------#
# Register a user process
def register_user(message):
    # Check if all required fields exist
    required_fields = ['user-name', 'Ipv4', 'm-port', 'c-port'];
    for field in required_fields:
        if field not in message['data']:
            print(f"❌ Missing field: {field}");
            return (False, "Missing field: " + field);

    # Check if the user already exists and or port is already in use
    if message['data']['user-name'] in user_data:
        print(f"❌ User already exists: {message['data']['user-name']}");
        return (False, "User already exists: " + message['data']['user-name']);
    
    # Check if the port is already in use
    if message['data']['m-port'] in used_ports or message['data']['c-port'] in used_ports:
            print(f"❌ Port already in use on this IP: {message['data']['Ipv4']} with port {message['data']['m-port']} or {message['data']['c-port']}");
            return (False, "Port already in use on this IP: " + message['data']['Ipv4'] + " with port " + str(message['data']['m-port']) + " or " + str(message['data']['c-port']));
    #----------------------------------------------------------

    # Register the user
    add_user(message['data']);
    print(f"✅ Successfully registered user: {message['data']['user-name']} \n");
    return (True, "Registered user: " + message['data']['user-name']);

# Register a disk process
def register_disk(message):
    # Check if all required fields exist
    required_fields = ['disk-name', 'Ipv4', 'm-port', 'c-port'];
    for field in required_fields:
        if field not in message['data']:
            print(f"❌ Missing field: {field}");
            return (False, "Missing field: " + field);

    # Check if the disk already exists and or port is already in use
    if message['data']['disk-name'] in disk_data:
        print(f"❌ Disk already exists: {message['data']['disk-name']}");
        return (False, "Disk already exists: " + message['data']['disk-name']);
    
    # Check if the port is already in use
    if message['data']['m-port'] in used_ports or message['data']['c-port'] in used_ports:
        print(f"❌ Port already in use on this IP: {message['data']['Ipv4']} with port {message['data']['m-port']} or {message['data']['c-port']}");
        return (False, "Port already in use on this IP: " + message['data']['Ipv4'] + " with port " + str(message['data']['m-port']) + " or " + str(message['data']['c-port']));
    #----------------------------------------------------------

    # Register the disk
    add_disk({**message['data'], "inDSS": False});
    print(f"✅ Successfully registered disk: {message['data']['disk-name']} \n");
    return (True, " Registered disk: " + message['data']['disk-name']);

# Configure a dss
def configure_dss(message, addr):
    # Check if the user configuring the dss exists
    if not user_exists(addr):
        print(f"❌ User not found: {addr}");
        return (False, f" User not found: {addr[0]}:{addr[1]}");

    # Check if all required fields exist
    required_fields = ['dss-name', 'n', 'striping-unit'];
    for field in required_fields:
        if field not in message['data']:
            print(f"❌ Missing field: {field}");
            return (False, "Missing field: " + field);


    # Check if the dss already exists
    if message['data']['dss-name'] in dss_data:
        print(f"❌ DSS already exists: {message['data']['dss-name']}");
        return (False, "DSS already exists: " + message['data']['dss-name']);

    # Check if the n is a number and a valid number
    n = message['data']['n']
    if not n.isdigit() or int(n) < 3:
        print(f"❌ Invalid n: {n}");
        return (False, f"Invalid n: {n} (must be greater than 2 and a number)");

    n = int(n)
    if n > len(free_disks):
        print(f"❌ Invalid n: {n} (Not enough free disks to configure the dss. Only {len(free_disks)} free disks available)");
        return (False, f"Invalid n: {n} (Not enough free disks to configure the dss. Only {len(free_disks)} free disks available)");


    # Check if the striping-unit is a valid number
    striping_unit = message['data']['striping-unit']

    if not striping_unit.isdigit() or not (128 <= int(striping_unit) <= 1048576 and (int(striping_unit) & (int(striping_unit) - 1)) == 0):
        print(f"❌ Invalid striping-unit: {striping_unit} (must be a power of 2 between 128 and 1048576 bytes)");
        return (False, f"Invalid striping-unit: {striping_unit} (must be a power of 2 between 128 and 1048576 bytes and a number)");
    striping_unit = int(striping_unit)
    ############################################################

    # configure the dss
    print(f"Configuring DSS: {message['data']['dss-name']} with data {message['data']}");
    dss_data[message['data']['dss-name']] = {
        "disks": [],
        "striping-unit": striping_unit,
        "n": n
    }
    # Pop n disks from the free disks
    for _ in range(n):
        disk_info = disk_data[free_disks.pop()];
        disk_info['inDSS'] = True;
        disk_data[disk_info['disk-name']] = disk_info;
        dss_data[message['data']['dss-name']]['disks'].append(disk_info['disk-name']);

    print(f"✅ Successfully configured DSS: {message['data']['dss-name']} \n");
    return (True, "Configured DSS: " + message['data']['dss-name']);

# Unregister a disk
def deregister_disk(message, addr):
    # Check if all required fields exist
    required_fields = ['disk-name'];
    for field in required_fields:
        if field not in message['data']:
            print(f"❌ Missing field: {field}");
            return (False, "Missing field: " + field);

    disk_name = message['data']['disk-name']
    
    # Check if the disk exists
    if disk_name not in disk_data:
        print(f"❌ Disk not found: {disk_name}");
        return (False, "Disk not found: " + disk_name);
    
    # Check if the disk is in free disks
    if not disk_name in free_disks:
        print(f"❌ Disk not in free disks: {disk_name}");
        return (False, "Disk not in free disks: " + disk_name);
    
    # check if come from the same IP and m-port as the registered disk
    disk_info = disk_data[disk_name]
    if disk_info['Ipv4'] != addr[0] or disk_info['m-port'] != addr[1]:
        print(f"❌ Deregister attempt from wrong address: got {addr[0]}:{addr[1]}, expected {disk_info['Ipv4']}:{disk_info['m-port']}")
        return (False, f"Deregister request must come from registered IP and m-port ({disk_info['Ipv4']}:{disk_info['m-port']})")
    #----------------------------------------------------------

    # deregister the disk
    remove_disk(disk_info);
    print(f"✅ Successfully deregistered disk: {disk_name} \n");
    return (True, "Deregistered disk: " + disk_name);

# Deregister a user
def deregister_user(message, addr):
    # Check if all required fields exist
    required_fields = ['user-name'];
    for field in required_fields:
        if field not in message['data']:
            print(f"❌ Missing field: {field}");
            return (False, "Missing field: " + field);
    
    # Check if the user exists
    if message['data']['user-name'] not in user_data:
        print(f"❌ User not found: {message['data']['user-name']}");
        return (False, "User not found: " + message['data']['user-name']);
    

    # Ensure the deregister request is coming from the same IP and m-port as the registered user
    user_name = message['data']['user-name']
    user_info = user_data[user_name]
    if user_info['Ipv4'] != addr[0] or user_info['m-port'] != addr[1]:
        print(f"❌ Deregister attempt from wrong address: got {addr[0]}:{addr[1]}, expected {user_info['Ipv4']}:{user_info['m-port']}")
        return (False, f"Deregister request must come from registered IP and m-port ({user_info['Ipv4']}:{user_info['m-port']})")
    ############################################################

    # Deregister the user
    remove_user(user_info);
    print(f"✅ Successfully deregistered user: {user_name} \n");
    return (True, "Deregistered user: " + message['data']['user-name']);

#-----------------------------------------------------------------------------------
    
#create a socket object
# AF_INET is the address family for IPv4
# SOCK_DGRAM is the socket type for UDP
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    # Bind the socket to the IP and port provided
    s.bind((HOST, PORT));
    print(f"Manager server started successfully!")
    print(f"Listening on {HOST}:{PORT}")
    print(f"Port range: 31500-31999")
    print("=" * 50)
    
    # start listening for messages from the user and disk processes
    while True:
        try:
            data = None;
            # Check if there is data to receive
            r, _, _ = select.select([s], [], [], 1.0)
            if r:
                data, addr = s.recvfrom(1024, )
                
            # If there is no data, continue
            if not data:
                continue;
            
            # If there is data, decode it and parse it as a json object
            message = json.loads(data.decode());
            print(f"Manager received message from {addr[0]}:{addr[1]}")
            print(f"   Message data: {json.dumps(message, indent=2)}")

            # Check if the message has a type field
            if('type' not in message):
                response(False, "Invalid message: Missing type field", addr);
                continue;

            print(f"Processing {message['type']} command from {addr[0]}:{addr[1]}")
            # Handle the message based on the type
            match message['type']:
                case "register-user":
                    res = register_user(message);
                    response(res[0], res[1], addr);
                case "register-disk":
                    res = register_disk(message);
                    response(res[0], res[1], addr);
                case "configure-dss":
                    res = configure_dss(message, addr);
                    response(res[0], res[1], addr);
                case "deregister-disk":
                    res = deregister_disk(message, addr);
                    response(res[0], res[1], addr);
                case "deregister-user":
                    res = deregister_user(message, addr);
                    response(res[0], res[1], addr);
                case _:
                    print(f"Invalid message type: {message['type']}");
                    response(False, "Invalid message type: " + message['type'], addr);
                    continue;
                                
        except KeyboardInterrupt:
            print("\nCtrl+C pressed, shutting down...")
            break;

            