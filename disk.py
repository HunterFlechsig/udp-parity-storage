# disk.py
# Hunter Flechsig, 1225292005
# Create a disk process
# Disk process is responsible for the storage of data

import socket;
import json;
import getopt, sys

name = None
ip = "127.0.0.1"
m_port = None
c_port = None

ports = [31500, 31999]
manager_ip = "127.0.0.1"
manager_port = ports[0]
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
                " -n, --name: Name of the disk \n"
                " -i, --ip: IP address of the disk (default: 127.0.0.1) \n"
                " -m, --m-port: M port of the disk \n"
                " -c, --c-port: C port of the disk \n"
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

# Validate port ranges
if not (ports[0] <= m_port <= ports[1]):
    print(f"❌ Error: m-port {m_port} must be in range {ports[0]}-{ports[1]}")
    sys.exit(1)

if not (ports[0] <= c_port <= ports[1]):
    print(f"❌ Error: c-port {c_port} must be in range {ports[0]}-{ports[1]}")
    sys.exit(1)
#--------------------------------------------------------#

#---------------------- Commands to send messages to the manager ---------------------------------------
# Send a deregister-disk message to the manager
def send_deregister_disk():
    message = {
        "type": "deregister-disk",
        "data": {
            "disk-name": name
        }
    }
    s.sendto(json.dumps(message).encode(), ("127.0.0.1", 65432));
    response = json.loads(s.recvfrom(1024)[0].decode());
    if response['status'] == 'success':
        print(f"✅ Disk {name} deregistered successfully \n");
        sys.exit(0);
    if response['status'] == 'failure':
        print(f"❌ Error: {response['message']} \n try again...\n");

# Send a register-disk message to the manager
def send_register_disk():
    message = {
        "type": "register-disk",
        "data": {
            "disk-name": name,
            "Ipv4": ip,
            "m-port": int(m_port),
            "c-port": int(c_port)
        }
    }
    s.sendto(json.dumps(message).encode(), manager_address);
    response = json.loads(s.recvfrom(1024)[0].decode());

    if response['status'] == 'failure':
        print(f"❌ Error: {response['message']} \n");
        sys.exit(1)

    if response['status'] == 'success':
        print(f"✅ Disk {name} registered successfully \n");
#-----------------------------------------------------------------------------------


# AF_INET is the address family for IPv4
# SOCK_DGRAM is the socket type for UDP
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind((ip, m_port));
    print(f"Disk {name} started on {ip}:{m_port} \n");

    send_register_disk()

    # start commands loop
    while True:
        try:
            print ("Commands: \n"
                "1. deregister-disk and exit \n"
                "2. exit \n"
            )
            command = input("Enter command: ");
            match command:
                case "1":
                    send_deregister_disk()
                case "2":
                    sys.exit(0)
                case _:
                    print("Invalid command \n");

        except KeyboardInterrupt:
            print("\nCtrl+C pressed, shutting down...")
            break;
