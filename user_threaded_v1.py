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
        
        # Thread-safe data structures
        self.lock = threading.Lock()
        self.registered = False
        
    def handle_manager_port(self):
        """Handle communication on manager port (m_port)"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((self.ip, self.m_port))
            print(f"✅ Manager port {self.m_port} listening on {self.ip}")
            
            while self.running:
                try:
                    # Set timeout to allow checking self.running
                    s.settimeout(1.0)
                    data, addr = s.recvfrom(1024)
                    message = json.loads(data.decode())
                    print(f"{self.name} Manager port received from {addr[0]}:{addr[1]}")
                    print(f"   Message: {json.dumps(message, indent=2)}")
                    
                    # Process manager messages
                    self.process_manager_message(message, addr, s)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"❌ Manager port error: {e}")
    
    def handle_client_port(self):
        """Handle communication on client port (c_port)"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((self.ip, self.c_port))
            print(f"{self.name} Client port {self.c_port} listening on {self.ip}")
            
            while self.running:
                try:
                    s.settimeout(1.0)
                    data, addr = s.recvfrom(1024)
                    message = json.loads(data.decode())
                    print(f"📨 Client port received from {addr[0]}:{addr[1]}")
                    print(f"   Message: {json.dumps(message, indent=2)}")
                    
                    # Process client messages
                    self.process_client_message(message, addr, s)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"❌ Client port error: {e}")
    
    def process_manager_message(self, message, addr, socket):
        """Process messages received on manager port"""
        try:
            if message.get('type') == 'response':
                print(f"📋 Manager response: {message.get('data', {}).get('message', 'No message')}")
            else:
                print(f"🔧 Processing manager message: {message.get('type', 'Unknown type')}")
        except Exception as e:
            print(f"❌ Error processing manager message: {e}")
    
    def process_client_message(self, message, addr, socket):
        """Process messages received on client port"""
        try:
            print(f"💾 Processing client message: {message.get('type', 'Unknown type')}")
            # Add client-specific message handling here
        except Exception as e:
            print(f"❌ Error processing client message: {e}")
    
    def send_to_manager(self, message):
        """Send message to manager and return response"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                print(f"📤 Sending to manager {self.manager_address[0]}:{self.manager_address[1]}")
                print(f"   Message: {json.dumps(message, indent=2)}")
                
                s.sendto(json.dumps(message).encode(), self.manager_address)
                response = json.loads(s.recvfrom(1024)[0].decode())
                
                print(f"📥 Received from manager {self.manager_address[0]}:{self.manager_address[1]}")
                print(f"   Response: {json.dumps(response, indent=2)}")
                
                return response
        except Exception as e:
            print(f"❌ Error communicating with manager: {e}")
            return None
    
    def send_to_disk(self, disk_address, message):
        """Send message to disk and return response"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                print(f"📤 Sending to disk {disk_address[0]}:{disk_address[1]}")
                print(f"   Message: {json.dumps(message, indent=2)}")
                
                s.sendto(json.dumps(message).encode(), disk_address)
                response = json.loads(s.recvfrom(1024)[0].decode())
                
                print(f"📥 Received from disk {disk_address[0]}:{disk_address[1]}")
                print(f"   Response: {json.dumps(response, indent=2)}")
                
                return response
        except Exception as e:
            print(f"❌ Error communicating with disk: {e}")
            return None
    
    # Command functions (adapted from original user.py)
    def send_configure_dss(self):
        """Configure a DSS"""
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
        
        response = self.send_to_manager(message)
        if response and response['data']['status'] == 'success':
            print(f"✅ DSS {dss_name} configured successfully\n")
        elif response:
            print(f"❌ Error: {response['message']}\n")
    
    def send_register_user(self):
        """Register user with manager"""
        message = {
            "type": "register-user",
            "data": {
                "user-name": self.name,
                "Ipv4": self.ip,
                "m-port": int(self.m_port),
                "c-port": int(self.c_port)
            }
        }
        
        response = self.send_to_manager(message)
        if response and response['data']['status'] == 'success':
            print(f"✅ User {self.name} registered successfully\n")
            with self.lock:
                self.registered = True
        elif response:
            print(f"❌ Error Registering User: {response['message']}\n")
            return False
        return True
    
    def send_deregister_user(self):
        """Deregister user from manager"""
        message = {
            "type": "deregister-user",
            "data": {
                "user-name": self.name
            }
        }
        
        response = self.send_to_manager(message)
        if response and response['data']['status'] == 'success':
            print(f"✅ User {self.name} deregistered successfully\n")
            with self.lock:
                self.registered = False
            return True
        elif response:
            print(f"❌ Error: {response['message']}\n")
        return False
    
    def send_copy_file_to_dss(self):
        """Copy file to DSS"""
        file_name = input("Enter file name: ")
        owner = input("Enter owner: ")
        
        try:
            file_size = os.path.getsize("./" + file_name)
        except FileNotFoundError:
            print(f"❌ Error: File '{file_name}' not found\n")
            return
        
        message = {
            "type": "copy",
            "data": {
                "file-name": file_name,
                "file-size": file_size,
                "owner": owner
            }
        }
        
        response = self.send_to_manager(message)
        if response and response['data']['status'] == 'success':
            print(f"✅ Manager has accepted the copy request\n")
            self.send_copy_to_disks(response['data']['response-data'], file_name)
        elif response:
            print(f"❌ Error Copying File: {response['message']}\n")
    
    def send_copy_to_disks(self, data, file_name):
        """Send copy messages to disks"""
        dss_name = data['dss-name']
        n = data['n']
        striping_unit = data['striping-unit']
        disks = data['disks']
        
        print(f"📁 Copying file '{file_name}' to DSS '{dss_name}'")
        print(f"   Using {n} disks with striping unit {striping_unit}")
        
        try:
            with open(file_name, "rb") as file:
                file_data = file.read()
            
            # For now, just print disk information
            # In a full implementation, you would send data to each disk
            for i, disk in enumerate(disks):
                print(f"   Disk {i+1}: {disk}")
                
        except Exception as e:
            print(f"❌ Error reading file: {e}")
    
    def start(self):
        """Start both port handlers in separate threads"""
        print(f"🚀 Starting user process: {self.name}")
        print(f"   Manager port: {self.ip}:{self.m_port}")
        print(f"   Client port: {self.ip}:{self.c_port}")
        print(f"   Manager address: {self.manager_address[0]}:{self.manager_address[1]}")
        print("=" * 60)
        
        # Create separate threads for each port
        manager_thread = threading.Thread(target=self.handle_manager_port, daemon=True)
        client_thread = threading.Thread(target=self.handle_client_port, daemon=True)
        
        # Start both threads
        manager_thread.start()
        client_thread.start()
        
        # Give threads time to start
        time.sleep(0.5)
        
        # Register with manager
        if not self.send_register_user():
            print("❌ Failed to register user. Exiting...")
            return
        
        # Main thread handles user input
        try:
            while True:
                print("\n" + "=" * 40)
                print("Commands:")
                print("1. configure-dss")
                print("2. deregister-user and exit")
                print("3. copy file to dss")
                print("4. exit")
                print("=" * 40)
                
                command = input("Enter command: ").strip()
                
                if command == "1":
                    self.send_configure_dss()
                elif command == "2":
                    if self.send_deregister_user():
                        break
                elif command == "3":
                    self.send_copy_file_to_dss()
                elif command == "4":
                    break
                else:
                    print("❌ Invalid command")
                    
        except KeyboardInterrupt:
            print("\n⚠️  Ctrl+C pressed, shutting down...")
        finally:
            print("🛑 Shutting down user process...")
            self.running = False
            print("✅ Shutdown complete")

def main():
    print("Starting user process...")
    """Main function with argument parsing"""
    name = None
    ip = "127.0.0.1"
    m_port = None
    c_port = None
    ports = [31500, 31999]
    
    manager_ip = "127.0.0.1"
    manager_port = ports[0]
    
    # Parse command line arguments
    args = sys.argv[1:]
    options = "hn:i:m:c:M:P:h"
    long_options = ["name", "ip", "m-port", "c-port", "manager-ip", "manager-port", "help"]
    
    try:
        arguments, values = getopt.getopt(args, options, long_options)
        for currentArg, currentVal in arguments:
            if currentArg in ("-h", "--help"):
                print("Threaded User Process (Approach #1) Help\n" 
                    " -n, --name: Name of the user\n"
                    " -i, --ip: IP address of the user (default: 127.0.0.1)\n"
                    " -m, --m-port: M port of the user\n"
                    " -c, --c-port: C port of the user\n"
                    " -M, --manager-ip: IP address of the manager (default: 127.0.0.1)\n"
                    " -P, --manager-port: Port of the manager (default: 31500)\n"
                )
                sys.exit(0)
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
            elif currentArg in ("-M", "--manager-ip"):
                manager_ip = currentVal
            elif currentArg in ("-P", "--manager-port"):
                try:
                    manager_port = int(currentVal)
                except ValueError:
                    print("❌ Error: Invalid manager-port (-P or --manager-port) value")
                    sys.exit(1)
    except getopt.error as err:
        print(str(err))
        sys.exit(1)
    
    # Validate required arguments
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
    
    if not (ports[0] <= manager_port <= ports[1]):
        print(f"❌ Error: manager-port {manager_port} must be in range {ports[0]}-{ports[1]}")
        sys.exit(1)
    
    # Create and start user process
    manager_address = (manager_ip, manager_port)
    user = UserProcess(name, ip, m_port, c_port, manager_address)
    user.start()

if __name__ == "__main__":
    main()
