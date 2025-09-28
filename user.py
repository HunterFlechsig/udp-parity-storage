# user.py
# Hunter Flechsig, 1225292005
# Create a user process
# User process uses the manager to configure the dss and disks and uses the dss to store and retrieve data

import socket;
import json;
import getopt, sys

name = None
ip = None
m_port = None
c_port = None
manager_ip = "127.0.0.1"
manager_port = 65432
manager_address = (manager_ip, manager_port)

#--------------- Get arguments ---------------#
args = sys.argv[1:]
options = "hn:i:m:c:d"
long_options = ["name", "ip", "m-port", "c-port", "help"]

try:
    arguments, values = getopt.getopt(args, options, long_options)
    for currentArg, currentVal in arguments:
        if currentArg in ("-h", "--help"):
            print("Showing Help \n" 
                " -n, --name: Name of the user \n"
                " -i, --ip: IP address of the user \n"
                " -m, --m-port: M port of the user \n"
                " -c, --c-port: C port of the user \n"
            )
        elif currentArg in ("-n", "--name"):
            name = currentVal
        elif currentArg in ("-i", "--ip"):
            ip = currentVal
        elif currentArg in ("-m", "--m-port"):
            try:
                m_port = int(currentVal)
            except ValueError:
                print("❌ Error: Invalid m-port (-m or --m-port) value")
                sys.exit(1)
        elif currentArg in ("-c", "--c-port"):
            try:
                c_port = int(currentVal)
            except ValueError:
                print("❌ Error: Invalid c-port (-c or --c-port) value")
                sys.exit(1)
except getopt.error as err:
    print(str(err))

# check if all arguments are provided
if name is None or ip is None or m_port is None or c_port is None:
    print("❌ Error: Missing required arguments:")
    if name is None:
        print("  - Missing name (-n or --name)")
    if ip is None:
        print("  - Missing IP (-i or --ip)")
    if m_port is None:
        print("  - Missing m-port (-m or --m-port)")
    if c_port is None:
        print("  - Missing c-port (-c or --c-port)")
    print("Use -h or --help for usage information\n")
    sys.exit(1)
#--------------------------------------------------------#

# ------ Command functions ---------------------
# Configure a dss
def send_configure_dss():
    # get the dss name, number of disks, and striping unit from the user
    dss_name = input("Enter DSS name: ");
    n = input("Enter number of disks: ");
    striping_unit = input("Enter striping unit: ");

# constructe configure-dss message
    message = {
        "type": "configure-dss",
        "data": {
            "dss-name": dss_name,
            "n": n,
            "striping-unit": striping_unit
        }
    }
    # send the message to the manager
    s.sendto(json.dumps(message).encode(), manager_address);
    response = json.loads(s.recvfrom(1024)[0].decode());

    if response['status'] == 'failure':
        print(f"❌ Error: {response['message']} \n");
        return;

    if response['status'] == 'success':
        print(f"✅ DSS {dss_name} configured successfully \n");

# Deregister a user
def send_deregister_user():
    # constructe deregister-user message
    message = {
        "type": "deregister-user",
        "data": {
            "user-name": name
        }
    }
    # send the message to the manager
    s.sendto(json.dumps(message).encode(), manager_address);
    response = json.loads(s.recvfrom(1024)[0].decode());

    if response['status'] == 'success':
        print(f"✅ User {name} deregistered successfully \n");
        sys.exit(0);

    if response['status'] == 'failure':
        print(f"❌ Error: {response['message']} \n try again...\n");

# Register a user
def send_register_user():
    # constructe register-user message
    message = {
        "type": "register-user",
        "data": {
            "user-name": name,
            "Ipv4": ip,
            "m-port": int(m_port),
            "c-port": int(c_port)
        }
    }
    # send the message to the manager
    s.sendto(json.dumps(message).encode(), manager_address);
    response = json.loads(s.recvfrom(1024)[0].decode());

    if response['status'] == 'success':
        print(f"✅ User {name} registered successfully \n");
        return;

    if response['status'] == 'failure':
        print(f"❌ Error Registering User: {response['message']} \n");
        sys.exit(1);

# ---------------------------------------------------------------

# AF_INET is the address family for IPv4
# SOCK_DGRAM is the socket type for UDP
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:

# ------ start socket and register the user with manager ---------------------
    # Bind the socket to the IP and port provided
    s.bind((ip, m_port));
    print(f"User {name} started on {ip}:{m_port} \n");

    send_register_user()
# ---------------------------------------------------------------

# ------ start commands loop ---------------------
    while True:
        try:
            print ("Commands: \n"
                "1. configure-dss \n"
                "2. deregister-user and exit \n"
                "3. exit \n"
            )
            command = input("Enter command: ");

            match command:
                case "1":
                    send_configure_dss()
                case "2":
                    send_deregister_user()
                case "3":
                    sys.exit(0)
                case _:
                    print("Invalid command \n");
 
        except KeyboardInterrupt:
            print("\nCtrl+C pressed, shutting down...")
            break;