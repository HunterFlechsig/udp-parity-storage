import socket
import json
import select
import getopt
import sys

class ManagerProcess:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

        self.user_data = {}
        self.disk_data = {}
        self.free_disks = set()
        self.dss_data = {}
        self.used_ports = set()

        self.s = None

    def start(self):
        """Start the manager process"""
        print(f"Starting manager process on {self.ip}:{self.port}")
        print(f"Listening on {self.ip}:{self.port}")
        print(f"Port range: 31500-31999")
        print("=" * 50)

        # Bind the socket to the IP and port provided
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as self.s:
            self.s.bind((self.ip, self.port))
            
            try:
                while True:
                    try:
                        # Set timeout to allow checking self.running
                        data = None;
                        self.s.settimeout(1.0)
                        data, addr = self.s.recvfrom(1024)
                        message = json.loads(data.decode())
                        print(f"Manager received from {addr[0]}:{addr[1]}")
                        print(f"   Message: {json.dumps(message, indent=2)}")
                        
                        # Process manager messages
                        if data:
                            self.process_message(message, addr)
                        
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"❌ Manager port error: {e}")
            except KeyboardInterrupt:
                print("\nCtrl+C pressed, shutting down manager...")
                print("Manager stopped cleanly")
    
    def process_message(self, message, addr):
        """Process messages received"""
        print(f"Processing message of type {message.get('type', 'Unknown type')}")
        try:
            if message.get('type') == 'register-user':
                self.register_user(message, addr)
            elif message.get('type') == 'deregister-user':
                self.deregister_user(message, addr)
            elif message.get('type') == 'register-disk':
                self.register_disk(message, addr)
            elif message.get('type') == 'deregister-disk':
                self.deregister_disk(message, addr)
            elif message.get('type') == 'configure-dss':
                self.configure_dss(message, addr)
            else:
                print(f"unknown message type")
        except Exception as e:
            print(f"❌ Error processing manager message: {e}")
            self.send_response("manager-response", "Error processing manager message: " + str(e), addr, "failure")

    # ---------------------------------------------------------------

    def configure_dss(self, message, addr):
        """Configure a DSS"""
        try:
            print(f"Processing configure-dss message")

            # check if DSS already exists
            if message.get('data', {}).get('dss-name') in self.dss_data:
                print(f"❌ DSS already exists: {message.get('data', {}).get('dss-name')}")
                self.send_response("configure-dss-response", "DSS already exists", addr, "failure")
                return
            
            # check if n and striping-unit are numbers
            try:
                n = (int)(message.get('data').get('n'))
                striping_unit = (int)(message.get('data').get('striping-unit'))
            except:
                print(f"❌ Invalid n: {message.get('data').get('n')} (must be a number)")
                self.send_response("configure-dss-response", "Invalid n or striping-unit type: must be a number", addr, "failure")
                return

            # check number of free disks
            if len(self.free_disks) < n:
                print(f"❌ Not enough free disks to configure the DSS")
                self.send_response("configure-dss-response", "Not enough free disks to configure the DSS", addr, "failure")
                return

            # check if n is a number and a valid number
            if n < 3:
                print(f"❌ Invalid n: {message.get('data').get('n')} (must be greater than 2 and a number)")
                self.send_response("configure-dss-response", "Invalid n: " + str(message.get('data').get('n')) + " (must be greater than 2 and a number)", addr, "failure")
                return

            # check if striping-unit is a power of 2 between 128 and 1048576 bytes
            if striping_unit < 128 or striping_unit > 1048576 or striping_unit & (striping_unit - 1) != 0:
                print(f"❌ Invalid striping-unit: {message.get('data').get('striping-unit')} (must be a power of 2 between 128 and 1048576 bytes)")
                self.send_response("configure-dss-response", "Invalid striping-unit: " + str(message.get('data').get('striping-unit')) + " (must be a power of 2 between 128 and 1048576 bytes)", addr, "failure")
                return

            # add DSS data
            self.dss_data[message.get('data').get('dss-name')] = {
                "disks": [],
                "striping-unit": message.get('data').get('striping-unit'),
                "n": message.get('data').get('n')
            }
            
            # pop n disks from the free disks
            for _ in range(n):
                disk_name = self.free_disks.pop()
                self.disk_data[disk_name]['inDSS'] = True
                self.dss_data[message.get('data').get('dss-name')]['disks'].append(disk_name)
            
            # send response to DSS's m-port
            print(f"✅ DSS {message.get('data').get('dss-name')} configured successfully")
            self.send_response("configure-dss-response", "DSS configured successfully", addr, "success")

        except Exception as e:
            print(f"❌ Error configuring DSS: {e}")
            self.send_response("configure-dss-response", "Error configuring DSS: " + str(e), addr, "failure")

    def register_user(self, message, addr):
        """Register a user"""
        try:
            print(f"Processing register-user message")

            # check if user already exists
            if message.get('data', {}).get('user-name') in self.user_data:
                print(f"❌ User already exists: {message.get('data', {}).get('user-name')}")
                self.send_response("register-user-response", "User already exists", addr, "failure")
                return

            # check if port is already in use
            ports = [message.get('data', {}).get('m-port'), message.get('data', {}).get('c-port')]
            for port in ports:
                if port in self.used_ports:
                    print(f"❌ Port already in use: {port}")
                    self.send_response("register-user-response", "One of the ports is already in use", addr, "failure")
                    return
            
            # Add user data and track ports
            user_data = message.get('data', {})
            self.user_data[user_data.get('user-name')] = user_data
            self.used_ports.add(user_data.get('m-port'))
            self.used_ports.add(user_data.get('c-port'))

            print(f"✅ User {message.get('data', {}).get('user-name')} registered successfully")
            self.send_response("register-user-response", "User registered successfully", addr, "success")
        except Exception as e:
            print(f"❌ Error registering user: {e}")
            self.send_response("register-user-response", "Error registering user: " + str(e), addr, "failure")

    def deregister_user(self, message, addr):
        """Deregister a user"""
        try:
            user_name = message.get('data', {}).get('user-name')
            print(f"Processing deregister-user message")

            if user_name not in self.user_data:
                print(f"❌ User {user_name} not found")
                self.send_response("deregister-user-response", f"User {user_name} not found", addr, "failure")
                return
            
            # Remove user and free up ports
            user_data = self.user_data[user_name]
            user_m_port = user_data.get('m-port')
            user_ip = user_data.get('Ipv4')
            
            self.used_ports.discard(user_data.get('m-port'))
            self.used_ports.discard(user_data.get('c-port'))
            self.user_data.pop(user_name)

            # send response to user's m-port
            print(f"✅ User {user_name} deregistered successfully")
            self.send_response("deregister-user-response", "User deregistered successfully", addr, "success")
        except Exception as e:
            print(f"❌ Error deregistering user: {e}")
            self.send_response("deregister-user-response", "Error deregistering user: " + str(e), addr, "failure")

    def register_disk(self, message, addr):
        """Register a disk"""
        print(f"Processing register-disk message")
        try:
            # check if disk already exists
            if message.get('data', {}).get('disk-name') in self.disk_data:
                print(f"❌ Disk already exists: {message.get('data', {}).get('disk-name')}")
                self.send_response("register-disk-response", "Disk already exists", addr, "failure")
                return
            
            # check if port is already in use
            ports = [message.get('data', {}).get('m-port'), message.get('data', {}).get('c-port')]
            for port in ports:
                if port in self.used_ports:
                    print(f"❌ Port already in use: {port}")
                    self.send_response("register-disk-response", "One of the ports is already in use", addr, "failure")
                    return
            
            # add disk data and track ports
            disk_data = message.get('data', {})
            self.disk_data[disk_data.get('disk-name')] = disk_data
            self.used_ports.add(disk_data.get('m-port'))
            self.used_ports.add(disk_data.get('c-port'))
            self.free_disks.add(disk_data.get('disk-name'))

            # send response to disk's m-port
            print(f"✅ Disk {message.get('data', {}).get('disk-name')} registered successfully")
            self.send_response("register-disk-response", "Disk registered successfully", addr, "success")
        except Exception as e:
            print(f"❌ Error registering disk: {e}")
            self.send_response("register-disk-response", "Error registering disk: " + str(e), addr, "failure")

    def deregister_disk(self, message, addr):
        """Deregister a disk"""
        try:
            print(f"Processing deregister-disk message")
            
            disk_name = message.get('data', {}).get('disk-name')
            if disk_name not in self.disk_data:
                print(f"❌ Disk {disk_name} not found")
                self.send_response("deregister-disk-response", f"Disk {disk_name} not found", addr, "failure")
                return
            
            # remove disk data and track ports
            self.disk_data.pop(disk_name)
            self.used_ports.discard(message.get('data', {}).get('m-port'))
            self.used_ports.discard(message.get('data', {}).get('c-port'))
            self.free_disks.discard(disk_name)

            print(f"✅ Disk {disk_name} deregistered successfully")
            self.send_response("deregister-disk-response", "Disk deregistered successfully", addr, "success")
        except Exception as e:
            print(f"❌ Error deregistering disk: {e}")
            self.send_response("deregister-disk-response", "Error deregistering disk: " + str(e), addr, "failure")

    # ---------------------------------------------------------------

    def send_response(self, type, message_text, addr, status):
        """Send a response to process"""
        response = {
            "type": type,
            "data": {
                "status": status,
                "message": ("✅ " + message_text if status == "success" else "❌ " + message_text)
            }
        }
        print(f"Sending response to {addr[0]}:{addr[1]}")
        print(f"   Response: {json.dumps(response, indent=2)}")
        self.s.sendto(json.dumps(response).encode(), addr)



def main():
    """Main function to parse command line arguments and start the manager process"""

    ip = "127.0.0.1"
    port = 31500

    args = sys.argv[1:]
    options = "hi:p:h"

    try:
        arguments, values = getopt.getopt(args, options)
        for currentArg, currentVal in arguments:
            if currentArg in ("-h", "--help"):
                print("Manager Process Help \n" 
                    " -i: IP address to bind the manager to (default: 127.0.0.1) \n"
                    " -p: Port number to bind the manager to (default: 31500) \n"
                )
                sys.exit(0)
    except getopt.error as err:
        print(str(err))
        sys.exit(1)
    
    if ip is None or port is None:
        print("❌ Error: Missing required arguments:")
        sys.exit(1)

    if not (31500 <= port <= 31999):
        print(f"❌ Error: Port {port} must be in range 31500-31999")
        sys.exit(1)

    manager = ManagerProcess(ip, port)
    manager.start()

if __name__ == "__main__":
    main()
            