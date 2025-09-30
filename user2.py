# user_threaded_v1.py
# Hunter Flechsig, 1225292005
# Approach #1: Separate Threads for Each Port
# User process uses separate threads to manage manager (m) and client (c) ports

import socket
import json
import threading
import time
import getopt
import sys
import os

class UserProcess:
    def __init__(self, name, ip, m_port, c_port, manager_address):
        self.name = name
        self.ip = ip
        self.m_port = m_port
        self.c_port = c_port
        self.manager_address = manager_address
        self.running = True
        self.registered = False

        # thread safe data structures
        self.lock = threading.Lock()

    def handle_manager_port(self):
        """Handle manager port (m_port)"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((self.ip, self.m_port))
            print(f"✅ Manager port {self.m_port} listening on {self.ip}")

            while self.running:
                try:
                    s.settimeout(1.0) # allow checking self.running
                    data, addr = s.recvfrom(1024)
                    message = json.loads(data.decode())
                    print("--------------------------------")
                    print(f"Manager port received from {addr[0]}:{addr[1]}")
                    print(f"   Message: {json.dumps(message, indent=2)}")

                    # process manager messages
                    self.process_manager_message(message, addr, s)
                
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"❌ Manager port error: {e}")
    
    def handle_command_port(self):
        """Handle command port (c_port)"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((self.ip, self.c_port))
            print(f"✅ Client port {self.c_port} listening on {self.ip}")

            while self.running:
                try:
                    s.settimeout(1.0) # allow checking self.running
                    data, addr = s.recvfrom(1024)
                    message = json.loads(data.decode())
                    print("--------------------------------")
                    print(f"Client port received from {addr[0]}:{addr[1]}")
                    print(f"   Message: {json.dumps(message, indent=2)}")
                    
                    # process client messages
                    self.process_command_message(message, addr, s)
                
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"❌ Client port error: {e}")

    # ---------------------------------------------------------------
    
    def process_manager_message(self, message, addr, socket):
        """Process messages received on manager port"""
        print(f"Manager response: {message.get('data', {}).get('status', 'No status')}")
        print(f"Manager response: {message.get('data', {}).get('message', 'No message')}")
        try:
            if message.get('type') == 'register-user-response':
                if message.get('data', {}).get('status', 'No status') == 'success':
                    with self.lock:
                        self.registered = True
                else:
                    sys.exit(1)
            elif message.get('type') == 'deregister-user-response':
                if message.get('data', {}).get('status', 'No status') == 'success':
                    with self.lock:
                        self.registered = False
                        sys.exit(0)
                else:
                    print(f"❌ Error Deregistering User: {message.get('data', {}).get('message', 'No message')}")
            elif message.get('type') == 'copy-response':
                self.handle_copy_response(message)
            else:
                print(f"Processing manager message: {message.get('type', 'Unknown type')}")

            if self.registered:
                print("Enter command: ", end="", flush=True)

        except Exception as e:
            print(f"Error processing manager message: {e}")

    
    def process_command_message(self, message, addr, socket):
        """Process messages received on command port"""
        try:
            print(f"Processing client message: {message.get('type', 'Unknown type')}")
            # add client-specific message handling here
        except Exception as e:
            print(f"Error processing client message: {e}")

    
    # ---------------------------------------------------------------

    def send_to_manager(self, message):
        """Send message to manager and return response"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(json.dumps(message).encode(), self.manager_address)

    def send_to_command(self, message):
        """Send message to command and return response"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(json.dumps(message).encode(), self.command_address)

    # ---------------------------------------------------------------

    def send_register_user(self):
        """Send register user message to manager"""
        message = {
            "type": "register-user",
            "data": {
                "user-name": self.name,
                "Ipv4": self.ip,
                "m-port": self.m_port,
                "c-port": self.c_port
            }
        }
        self.send_to_manager(message)
        print(f"Register user message sent to manager address {self.manager_address[0]}:{self.manager_address[1]}")
        print(f"   Message: {json.dumps(message, indent=2)}")

    def send_deregister_user(self):
        """Send deregister user message to manager"""
        message = {
            "type": "deregister-user",
            "data": {
                "user-name": self.name
            }
        }
        self.send_to_manager(message)

    def send_configure_dss(self):
        """Send configure dss message to manager"""
        dss_name = input("Enter DSS name: ")
        n = input("Enter number of disks: ")
        striping_unit = input("Enter striping unit: ")
        
        message = {
            "type": "configure-dss",
            "data": {
                "dss-name": dss_name,
                "n": n,
                "striping-unit": striping_unit
            }
        }
        self.send_to_manager(message)

    # ---------------------------------------------------------------

    def start(self):
        """Start the user process"""

        """Start both port handlers in separate threads"""
        print(f"Starting user process: {self.name}")
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
        self.send_register_user()
        
        # Main command loop
        try:
            while True:
                if self.registered:
                    print("\n" + "=" * 40)
                    print("Commands:")
                    print("1. configure-dss")
                    print("2. deregister-user and exit")
                    print("3. exit")
                    print("=" * 40)
                    
                    command = input("Enter command: ").strip()
                    
                    if command == "1":
                        self.send_configure_dss()
                    elif command == "2":
                        self.send_deregister_user()
                    elif command == "3":
                        break
                    else:
                        print("❌ Invalid command")
                    
        except KeyboardInterrupt:
            print("\n Ctrl+C pressed, shutting down...")
        finally:
            print("Shutting down user process...")
            self.running = False
            print("Shutdown complete")


def main():
    """Main function to parse command line arguments and start the user process"""

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
                print("User Process Help \n" 
                    " -n: Name of the user (required) \n"
                    " -i: IP address of the user (default: 127.0.0.1) \n"
                    " -m: M port of the user (required) \n"
                    " -c: C port of the user (required) \n"
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
    
    # Create and start user process
    user = UserProcess(name, ip, m_port, c_port, manager_address)
    user.start()

if __name__ == "__main__":
    main()
            