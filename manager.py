import socket;
import json;
import select;

HOST = '127.0.0.1';
PORT = 65432;

user_data = {};
disk_data = {};
dss_data = {};

free_disks = set();
used_ports = set();

# Check if a user exists
def user_exists(addr):
    for user in user_data:
        if user_data[user]['Ipv4'] == addr[0] and user_data[user]['m-port'] == addr[1]:
            return True;
    return False;

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
    
    if message['data']['m-port'] in used_ports or message['data']['c-port'] in used_ports:
            print(f"❌ Port already in use on this IP: {message['data']['Ipv4']} with port {message['data']['m-port']} or {message['data']['c-port']}");
            return (False, "Port already in use on this IP: " + message['data']['Ipv4'] + " with port " + message['data']['m-port'] + " or " + message['data']['c-port']);
    ############################################################

    # Register the user
    user_data[message['data']['user-name']] = message['data'];
    used_ports.add(message['data']['m-port']);
    used_ports.add(message['data']['c-port']);
    print(f"✅ Registered user: {message['data']['user-name']} \n");
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
    
    if message['data']['m-port'] in used_ports or message['data']['c-port'] in used_ports:
        print(f"❌ Port already in use on this IP: {message['data']['Ipv4']} with port {message['data']['m-port']} or {message['data']['c-port']}");
        return (False, "Port already in use on this IP: " + message['data']['Ipv4'] + " with port " + message['data']['m-port'] + " or " + message['data']['c-port']);
    ############################################################

    # Register the disk
    disk_data[message['data']['disk-name']] = {**message['data'], "free": False};
    free_disks.add(message['data']['disk-name']);
    used_ports.add(message['data']['m-port']);
    used_ports.add(message['data']['c-port']);
    print(f"✅ Registered disk: {message['data']['disk-name']} \n");
    return (True, " Registered disk: " + message['data']['disk-name']);

# Configure a dss
def configure_dss(message, addr):
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
    if not n.isdigit() or int(n) < 3 or int(n) > len(free_disks):
        print(f"❌ Invalid n: {n}");
        return (False, "Invalid n: " + n + f" (must be greater than 2 and less than {len(free_disks)} and a number)");
    n = int(n)

    # Check if the striping-unit is a valid number
    striping_unit = message['data']['striping-unit']

    if not striping_unit.isdigit() or not (128 <= int(striping_unit) <= 1048576 and (int(striping_unit) & (int(striping_unit) - 1)) == 0):
        print(f"❌ Invalid striping-unit: {striping_unit} (must be a power of 2 between 128 and 1048576 bytes)");
        return (False, f"Invalid striping-unit: {striping_unit} (must be a power of 2 between 128 and 1048576 bytes and a number)");
    striping_unit = int(striping_unit)
    ############################################################

    # configure the dss
    dss_data[message['data']['dss-name']] = {
        "disks": [],
        "striping-unit": striping_unit,
        "n": n
    }
    # Pop n disks from the free disks
    for _ in range(n):
        dss_data[message['data']['dss-name']]['disks'].append(free_disks.pop());

    print(f"✅ Configured DSS: {message['data']['dss-name']} \n");
    return (True, "Configured DSS: " + message['data']['dss-name']);

    
def response(success, message, addr):
    data = {
        "status": "success" if success else "failure",
        "message": message
    }

    s.sendto(json.dumps(data).encode(), addr);
    return data;



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
                data, addr = s.recvfrom(1024, )

            if not data:
                continue;

            message = json.loads(data.decode());

            if('type' not in message):
                response(False, "Invalid message: Missing type field", addr);
                continue;

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
                case _:
                    print(f"Invalid message type: {message['type']}");
                    response(False, "Invalid message type: " + message['type'], addr);
                    continue;
                                
        except KeyboardInterrupt:
            print("\nCtrl+C pressed, shutting down...")
            break;

            