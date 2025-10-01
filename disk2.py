# disk.py
# Hunter Flechsig, 1225292005
# Create a disk process
# Disk process is responsible for the storage of data
# Disk process uses separate threads to manage manager (m) and client (c) ports

import socket
import json
import threading
import time
import getopt
import sys
import os

class DiskProcess:
    def __init__(self, name, ip, m_port, c_port, manager_address):
        self.name = name
        self.ip = ip
        self.m_port = m_port
        self.c_port = c_port
        self.manager_address = manager_address
        self.running = True
        self.registered = False
        self.manager_socket = None
        self.command_socket = None

        # thread safe data structures
        self.lock = threading.Lock()

    def handle_manager_port(self):
        """Handle manager port (m_port)"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as self.manager_socket:
            try:
                self.manager_socket.bind((self.ip, self.m_port))
            except Exception as e:
                print(f"❌ Error binding manager port: {e}")
                self.running = False
                return

            print(f"✅ Manager port {self.m_port} listening on {self.ip}")

            while self.running:
                try:
                    self.manager_socket.settimeout(1.0) # allow checking self.running
                    data, addr = self.manager_socket.recvfrom(1024)
                    message = json.loads(data.decode())
                    print ("=" * 60)
                    print(f"Manager port received from {addr[0]}:{addr[1]}")
                    print(f"   Message: {json.dumps(message, indent=2)}")

                    # process manager messages
                    self.process_manager_message(message)
                    print("=" * 60)
                
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"❌ Manager port error: {e}")
        
    
    def handle_command_port(self):
        """Handle command port (c_port)"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as self.command_socket:
            try:
                self.command_socket.bind((self.ip, self.c_port))
            except Exception as e:
                print(f"❌ Error binding client port: {e}")
                self.running = False
                return

            print(f"✅ Client port {self.c_port} listening on {self.ip}")

            while self.running:
                try:
                    self.command_socket.settimeout(1.0) # allow checking self.running
                    data, addr = self.command_socket.recvfrom(1024)
                    message = json.loads(data.decode())
                    print("--------------------------------")
                    print(f"Client port received from {addr[0]}:{addr[1]}")
                    print(f"   Message: {json.dumps(message, indent=2)}")
                    
                    # process client messages
                    self.process_command_message(message)
                
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"❌ Client port error: {e}")

    # ---------------------------------------------------------------
    
    def process_manager_message(self, message):
        """Process messages received on manager port"""
        print(f"Manager response: {message.get('data', {}).get('status', 'No status')}")
        print(f"{message.get('data', {}).get('message', 'No message')}")
        try:
            if message.get('type') == 'register-disk-response':
                if message.get('data', {}).get('status', 'No status') == 'success':
                    with self.lock:
                        self.registered = True
                else: 
                    self.running = False
            elif message.get('type') == 'deregister-disk-response':
                if message.get('data', {}).get('status', 'No status') == 'success':
                    with self.lock:
                        self.registered = False
                        sys.exit(0)
                else:
                    print(f"❌ Error Deregistering disk: {message.get('data', {}).get('message', 'No message')}")
            elif message.get('type') == 'copy-response':
                self.handle_copy_response(message)
            else:
                print(f"Processing manager message: {message.get('type', 'Unknown type')}")

            if self.registered:
                print("Enter command: ", end="", flush=True)

        except Exception as e:
            print(f"Error processing manager message: {e}")

    
    def process_command_message(self, message):
        """Process messages received on command port"""
        try:
            print(f"Processing client message: {message.get('type', 'Unknown type')}")
            # add client-specific message handling here
        except Exception as e:
            print(f"Error processing client message: {e}")

    
    # ---------------------------------------------------------------

    def send_to_manager(self, message):
        """Send message to manager and return response"""
        self.manager_socket.sendto(json.dumps(message).encode(), self.manager_address)

    def send_to_command(self, message):
        """Send message to command and return response"""
        self.command_socket.sendto(json.dumps(message).encode(), self.command_address)

    # ---------------------------------------------------------------

    def send_register_disk(self):
        """Send register disk message to manager"""
        message = {
            "type": "register-disk",
            "data": {
                "disk-name": self.name,
                "Ipv4": self.ip,
                "m-port": self.m_port,
                "c-port": self.c_port
            }
        }
        self.send_to_manager(message)
        print("=" * 60)
        print(f"Register disk message sent to manager address {self.manager_address[0]}:{self.manager_address[1]}")
        print(f"   Message: {json.dumps(message, indent=2)}")
        print("=" * 60)

    def send_deregister_disk(self):
        """Send deregister disk message to manager"""
        message = {
            "type": "deregister-disk",
            "data": {
                "disk-name": self.name
            }
        }
        self.send_to_manager(message)

    # ---------------------------------------------------------------

    def start(self):
        """Start the disk process"""

        """Start both port handlers in separate threads"""
        print(f"Starting disk process: {self.name}")
        print(f"Manager port: {self.ip}:{self.m_port}")
        print(f"Client port: {self.ip}:{self.c_port}")
        print(f"Manager address: {self.manager_address[0]}:{self.manager_address[1]}")
        print("--------------------------------")

        # Create separate threads for each port
        manager_thread = threading.Thread(target=self.handle_manager_port, daemon=True)
        command_thread = threading.Thread(target=self.handle_command_port, daemon=True)

        # Start both threads
        manager_thread.start()
        command_thread.start()

        # Give threads time to start
        time.sleep(0.5)
        
        # Register with manager
        if self.running:
            self.send_register_disk()
        
        # Main command loop
        try:
            while self.running:
                if self.registered:
                    print("\n" + "=" * 40)
                    print("Commands:")
                    print("1. deregister-disk and exit")
                    print("2. exit")
                    print("3. exit")
                    print("=" * 40)
                    
                    command = input("Enter command: ").strip()
                    
                    if command == "1":
                        self.send_deregister_disk()
                    elif command == "2":
                        break
                    elif command == "3":
                        break
                    else:
                        print("❌ Invalid command")
                    
        except KeyboardInterrupt:
            print("\n⚠️  Ctrl+C pressed, shutting down...")
        finally:
            print("🛑 Shutting down disk process...")
            self.running = False
            print("✅ Shutdown complete")    


def main():
    """Main function to parse command line arguments and start the disk process"""

    name = None
    ip = "127.0.0.1"
    m_port = None
    c_port = None
    ports = [31500, 31999]
    
    manager_ip = "127.0.0.1"
    manager_port = ports[0]

    args = sys.argv[1:]
    options = "hn:i:m:c:M:P:h"

    try: 
        arguments, values = getopt.getopt(args, options)
        for currentArg, currentVal in arguments:
            if currentArg in ("-h", "--help"):
                print("disk Process Help \n" 
                    " -n: Name of the disk (required) \n"
                    " -i: IP address of the disk (default: 127.0.0.1) \n"
                    " -m: M port of the disk (required) \n"
                    " -c: C port of the disk (required) \n"
                    " -M: IP address of the manager (default: 127.0.0.1) \n"
                    " -P: Port of the manager (default: 31500) \n"
                )
                sys.exit(0)
            elif currentArg in ("-n"):
                name = currentVal
            elif currentArg in ("-i"):
                ip = currentVal
            elif currentArg in ("-m"):
                m_port = int(currentVal)
            elif currentArg in ("-c"):
                c_port = int(currentVal)
            elif currentArg in ("-M"):
                manager_ip = currentVal
            elif currentArg in ("-P"):
                manager_port = int(currentVal)
    except getopt.error as err:
        print(str(err))
        sys.exit(1)

        # Validate port ranges
    if not (ports[0] <= m_port <= ports[1]):
        print(f"❌ Error: m-port {m_port} must be in range {ports[0]}-{ports[1]}")
        sys.exit(1)
    
    if not (ports[0] <= c_port <= ports[1]):
        print(f"❌ Error: c-port {c_port} must be in range {ports[0]}-{ports[1]}")
        sys.exit(1)
    
    if not (ports[0] <= manager_port <= ports[1]):
        print(f"❌ Error: manager-port {manager_port} must be in range {ports[0]}-{ports[1]}")
        sys.exit(1)

    if name is None or ip is None or m_port is None or c_port is None:
        print("❌ Error: Missing a required argument")
        sys.exit(1)

    manager_address = (manager_ip, manager_port)
    
    # Create and start disk process
    disk = DiskProcess(name, ip, m_port, c_port, manager_address)
    disk.start()
    sys.exit(0)

if __name__ == "__main__":
    main()
            