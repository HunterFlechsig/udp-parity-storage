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
import base64

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
            self.manager_socket.bind((self.ip, self.m_port))
            print(f"✅ Manager port {self.m_port} listening on {self.ip}")

            while self.running:
                try:
                    self.manager_socket.settimeout(1.0) # allow checking self.running
                    data, addr = self.manager_socket.recvfrom(1024)
                    message = json.loads(data.decode())

                    print(f"Manager port received from {addr[0]}:{addr[1]}")
                    print(f"   Message: {json.dumps(message, indent=2)}")

                    # process manager messages
                    self.process_manager_message(message)

                    print("=" * 20)
                
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
        try:
            match message.get('type'):
                case 'register-disk':
                    if message.get('data', {}).get('status', 'No status') == 'success':
                        self.registered = True
                        print(f"✅ Disk {self.name} registered successfully")
                    else:
                        self.running = False
                        print(f"message: {message.get('data', {}).get('message', 'No message')}")
                        sys.exit(1)

                case 'deregister-disk':
                    if message.get('data', {}).get('status', 'No status') == 'success':
                        self.running = False
                        self.registered = False
                        print(f"✅ Disk {self.name} deregistered successfully")
                        sys.exit(0)
                    else:
                        print(f"message: {message.get('data', {}).get('message', 'No message')}")

                case 'copy':
                    if message.get('data', {}).get('status', 'No status') == 'success':
                        print(f"✅ Got copy data from manager")
                        self.handle_copy(message)
                    else:
                        print(f"{message.get('data', {}).get('message', 'No message')}")
                        sys.exit(1)
                
                case _:
                    print(f"Unknown manager message: {message.get('type', 'Unknown type')}")
                    return
        except Exception as e:
            print(f"Error processing manager message: {e}")

    
    def process_command_message(self, message):
        """Process messages received on command port"""
        try:
            print(f"Processing client message: {message.get('type', 'Unknown type')}")
            # add client-specific message handling here
        except Exception as e:
            print(f"Error processing client message: {e}")

    
    # ------------------- Response handlers ------------------------------

    def calculate_parity_chunk(self, chunks):
        """Calculate parity chunk"""
        parity_chunk = ""
        for chunk in chunks:
            parity_chunk ^= chunk
        return parity_chunk

    def copy_to_disk_worker(self, disk, chunk, file_name, parity, stripe_number):
        """Copy to disk worker"""
        block = base64.b64encode(chunk).decode("utf-8")
        message = {
            "type": "copy",
            "data": {
                "block": block,
                "block-type": "data" if not parity else "parity",
                "file-name": file_name,
                "stripe-number": stripe_number
            }
        }
        self.send_with_command_port(message, (disk['ip'], disk['c-port']))


    def handle_copy(self, message):
        """Handle copy message"""
        print(f"Copying data to dss: {message.get('data', {}).get('dss-name')}")
        file_name = message.get('data', {}).get('file-name')
        file_size = message.get('data', {}).get('file-size')
        owner = message.get('data', {}).get('owner')
        n = message.get('data', {}).get('n')
        striping_unit = message.get('data', {}).get('striping-unit')
        disks = message.get('data', {}).get('disks')

        num_stripes = -(-file_size // -((n-1) * striping_unit))

        with open(file_name, "rb") as f:
            for i in range(num_stripes):
                chunks = []
                for _ in range(n-1):
                    chunk = f.read(striping_unit)

                    # pad with nulls if not enough bytes
                    if len(chunk) < striping_unit:
                        chunk = chunk.ljust(striping_unit, b"\x00")

                parity_chunk = self.calculate_parity_chunk(chunks)
                chunks.insert(n%i, parity_chunk)

                threads = []
                for disk_inx, chunck in enumerate(chunks):
                    print(f"Copying to disk {disks[disk_inx]['disk-name']}")
                    t = threading.Thread(target=self.copy_to_disk_worker, args=(disks[disk_inx], chunck, file_name, (disk_inx == n%i), i))
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()

        message = {
            "type": "copy-complete",
            "data": {}
        }
        self.send_to_manager(message)

    # ---------------------------------------------------------------

    def send_to_manager(self, message):
        """Send message to manager and return response"""
        print(f"Sending message.{message.get('type')} to manager address {self.manager_address[0]}:{self.manager_address[1]}")
        print("=" * 20)

        self.manager_socket.sendto(json.dumps(message).encode(), self.manager_address)

    def send_with_command_port(self, message, address):
        """Send message to command and return response"""
        print(f"Sending message.{message.get('type')} to command address {self.command_address[0]}:{self.command_address[1]}")
        print("=" * 20)

        self.command_socket.sendto(json.dumps(message).encode(), address)

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


    # ---------------------------------------------------------------

    def start(self):
        """Start the disk process"""

        """Start both port handlers in separate threads"""
        print(f"Starting disk process: {self.name}")
        print(f"Manager port: {self.ip}:{self.m_port}")
        print(f"Client port: {self.ip}:{self.c_port}")
        print(f"Manager address: {self.manager_address[0]}:{self.manager_address[1]}")

        # Create separate threads for each port
        manager_thread = threading.Thread(target=self.handle_manager_port, daemon=True)
        command_thread = threading.Thread(target=self.handle_command_port, daemon=True)

        # Start both threads
        manager_thread.start()
        command_thread.start()

        # Give threads time to start
        time.sleep(0.5)

        print("=" * 20)

        # Register with manager
        if self.running:
            self.send_register_disk()
        else:
            return
        
        # Main command loop
        try:
            while self.running:
                # Only show commands if disk is registered
                if not self.registered:
                    time.sleep(0.1)                    
                    continue

                """Print commands"""
                print("\n" + "=" * 20)
                print("Commands:")
                print("1. deregister-disk and exit")
                print("2. exit")
                print("=" * 20)
                
                command = input("Enter command: ").strip()
                    
                if command == "1":
                    self.send_deregister_disk()
                elif command == "2":
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
                print("Disk Process Help \n" 
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

if __name__ == "__main__":
    main()
            