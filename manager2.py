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
        self.dss_data = {}
        self.user_ports = set()

    def start(self):
        """Start the manager process"""
        print(f"Starting manager process on {self.ip}:{self.port}")
        print(f"Listening on {self.ip}:{self.port}")
        print(f"Port range: 31500-31999")
        print("=" * 50)

        # Bind the socket to the IP and port provided
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((self.ip, self.port))
            
            try:
                while True:
                    try:
                        # Set timeout to allow checking self.running
                        data = None;
                        s.settimeout(1.0)
                        data, addr = s.recvfrom(1024)
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
        print(f"Processing message from {addr[0]}:{addr[1]}")
        print(f"   Message: {json.dumps(message, indent=2)}")
        try:
            if message.get('type') == 'register-user':
                self.register_user(message)
            elif message.get('type') == 'deregister-user':
                self.deregister_user(message)
            else:
                print(f"unknown message type")
        except Exception as e:
            print(f"❌ Error processing manager message: {e}")

    # ---------------------------------------------------------------

    def register_user(self, message):
        """Register a user"""
        print(f"Processing register-user message")

        addr = (message.get('data', {}).get('Ipv4'), message.get('data', {}).get('m-port'))

        # check if user already exists
        if message.get('data', {}).get('user-name') in self.user_data:
            print(f"❌ User already exists: {message.get('data', {}).get('user-name')}")
            self.send_response("register-user-response", "User already exists", addr, "failure")
            return

        # check if port is already in use
        ports = [message.get('data', {}).get('m-port'), message.get('data', {}).get('c-port')]
        for port in ports:
            if port in self.user_ports:
                print(f"❌ Port already in use: {port}")
                self.send_response("register-user-response", "One of the ports is already in use", addr, "failure")
                return
        
        # Add user data and track ports
        user_data = message.get('data', {})
        self.user_data[user_data.get('user-name')] = user_data
        self.user_ports.add(user_data.get('m-port'))
        self.user_ports.add(user_data.get('c-port'))

        print(f"✅ User {message.get('data', {}).get('user-name')} registered successfully")
        self.send_response("register-user-response", "User registered successfully", addr, "success")

    def deregister_user(self, message):
        """Deregister a user"""
        user_name = message.get('data', {}).get('user-name')
        print(f"Processing deregister-user message")
        
        addr = (message.get('data', {}).get('Ipv4'), message.get('data', {}).get('m-port'))

        if user_name not in self.user_data:
            print(f"❌ User {user_name} not found")
            self.send_response("deregister-user-response", f"User {user_name} not found", addr, "failure")
            return
        
        # Remove user and free up ports
        user_data = self.user_data[user_name]
        user_m_port = user_data.get('m-port')
        user_ip = user_data.get('Ipv4')
        
        self.user_ports.discard(user_data.get('m-port'))
        self.user_ports.discard(user_data.get('c-port'))
        self.user_data.pop(user_name)

        # send response to user's m-port
        print(f"✅ User {user_name} deregistered successfully")
        self.send_response("deregister-user-response", "User deregistered successfully", addr, "success")

    def register_disk(self, message, addr):
        """Register a disk"""
        print(f"Processing register-disk message")

        addr = (message.get('data', {}).get('Ipv4'), message.get('data', {}).get('m-port'))

        # check if disk already exists
        if message.get('data', {}).get('disk-name') in self.disk_data:
            print(f"❌ Disk already exists: {message.get('data', {}).get('disk-name')}")
            self.send_response("register-disk-response", "Disk already exists", addr, "failure")
            return
        
        # check if port is already in use
        ports = [message.get('data', {}).get('m-port'), message.get('data', {}).get('c-port')]
        for port in ports:
            if port in self.disk_ports:
                print(f"❌ Port already in use: {port}")
                self.send_response("register-disk-response", "One of the ports is already in use", addr, "failure")
                return
        
        # add disk data and track ports
        disk_data = message.get('data', {})
        self.disk_data[disk_data.get('disk-name')] = disk_data
        self.disk_ports.add(disk_data.get('m-port'))
        self.disk_ports.add(disk_data.get('c-port'))

        # send response to disk's m-port
        print(f"✅ Disk {message.get('data', {}).get('disk-name')} registered successfully")
        self.send_response("register-disk-response", "Disk registered successfully", addr, "success")

    def deregister_disk(self, message):
        """Deregister a disk"""
        print(f"Processing deregister-disk message")

        addr = (message.get('data', {}).get('Ipv4'), message.get('data', {}).get('m-port'))

        disk_name = message.get('data', {}).get('disk-name')
        if disk_name not in self.disk_data:
            print(f"❌ Disk {disk_name} not found")
            self.send_response("deregister-disk-response", f"Disk {disk_name} not found", addr, "failure")
            return
        
        # remove disk data and track ports
        self.disk_data.pop(disk_name)
        self.disk_ports.discard(message.get('data', {}).get('m-port'))
        self.disk_ports.discard(message.get('data', {}).get('c-port'))

        print(f"✅ Disk {disk_name} deregistered successfully")
        self.send_response("deregister-disk-response", "Disk deregistered successfully", addr, "success")

    # ---------------------------------------------------------------

    def send_response(self, type, message_text, addr, status):
        """Send a response to process"""
        response = {
            "type": type,
            "data": {
                "status": status,
                "message": message_text
            }
        }
        print(f"Sending response to {addr[0]}:{addr[1]}")
        print(f"   Response: {json.dumps(response, indent=2)}")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(json.dumps(response).encode(), addr)



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
            