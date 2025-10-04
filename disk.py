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
import random

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

        self.random_bit_flip = 30

        self.files = {}  # dictionary to store files and their data

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
                    data, addr = self.manager_socket.recvfrom(8024)
                    message = json.loads(data.decode())

                    print(f"📩 Manager port received message from {addr[0]}:{addr[1]} of type {message.get('type', 'Unknown type')}")

                    # process manager messages
                    self.process_manager_message(message, addr)
                
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
                    data, addr = self.command_socket.recvfrom(8192)
                    message = json.loads(data.decode())

                    print(f"📩 Command port received message from {addr[0]}:{addr[1]} of type {message.get('type', 'Unknown type')}")

                    # process client messages
                    self.process_command_message(message, addr)

                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"❌ Client port error: {e}")

    # ---------------------------------------------------------------
    
    def process_manager_message(self, message, addr):
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
                
                case _:
                    print(f"Unknown manager message: {message.get('type', 'Unknown type')}")
                    return
        except Exception as e:
            print(f"Error processing manager message: {e}")

    
    def process_command_message(self, message, addr):
        """Process messages received on command port"""
        try:
            print(f"Processing command message: {message.get('type', 'Unknown type')}")
            match message.get('type'):
                case 'copy':
                    self.handle_copy(message, addr)
                case 'read':
                    self.handle_read(message, addr)
                case _:
                    print(f"Unknown command message: {message.get('type', 'Unknown type')}")
        except Exception as e:
            print(f"Error processing client message: {e}")

    
    # ------------------- Response handlers ------------------------------


    def handle_copy(self, message, addr):
        """Handle copy message"""
        try: 
            data = message.get('data', {})
            file_name = data.get('file-name')
            block_type = data.get('block-type')
            stripe_index = data.get('stripe-index')
            stripe_count = data.get('stripe-count')
            block_index = data.get('block-index')
            chunk = data.get('chunk')
            chunk_index = data.get('chunk-index')
            chunk_count = data.get('chunk-count')
            n = data.get('n')


            # Initialize as empty bytes if it doesn't exist
            if file_name not in self.files:
                self.files[file_name] = {"data": [[None for _ in range(chunk_count)] for _ in range (stripe_count)], 
                    'type': [None for _ in range (stripe_count)], 'block_index': [None for _ in range (stripe_count)], 'n': n }

            # Store chunk and metadata for this stripe
            self.files[file_name]['data'][stripe_index][chunk_index] = chunk
            self.files[file_name]['type'][stripe_index] = block_type
            self.files[file_name]['block_index'][stripe_index] = block_index

            print(f"Storing block {block_index} of type {block_type} for file {file_name}, stripe {stripe_index}")

            ack_message = {
                "type": "copy-ack",
                "data": {
                    "status": "success",
                    "message": f"✅ Block {block_index} of type {block_type} for file {file_name}, stripe {stripe_index} stored successfully"

                }
            }
            self.send_with_command_port(ack_message, addr)
            
        except Exception as e:
            print(f"❌ Error handling copy message: {e}")
            ack_message = {
                "type": "acknowledge",
                "data": {
                    "status": "error",
                    "message": f"❌ Error storing block: {e}"
                }
            }
            self.send_with_command_port(ack_message, addr)

    def handle_read(self, message, addr):
        """Handle read message"""
        try:

            data = message.get('data', {})
            file_name = data.get('file-name')
            stripe_number = data.get('stripe-number')

            random_bit_flip = random.randint(0, 100) < self.random_bit_flip

            stripe_data = self.files[file_name]['data'][stripe_number]        
            stripe_type = self.files[file_name]['type'][stripe_number]
            stripe_index = self.files[file_name]['block_index'][stripe_number]
            n = self.files[file_name]['n']

            # Flip the first bit of the first chunk if random_bit_flip is True
            print(f"🔄 Flipping first bit: {random_bit_flip}")
            if random_bit_flip and stripe_data and stripe_data[0] is not None:
                # Decode the base64 chunk to bytes
                try:
                    decoded_chunk = base64.b64decode(stripe_data[0])
                    if len(decoded_chunk) > 0:
                        # Convert to bytearray to allow modification
                        chunk_bytes = bytearray(decoded_chunk)
                        # Flip the first bit (LSB) of the first byte
                        chunk_bytes[0] ^= 1
                        # Re-encode back to base64
                        stripe_data[0] = base64.b64encode(bytes(chunk_bytes)).decode('utf-8')
                        print(f"✅ Flipped first bit of first chunk in stripe {stripe_number}")
                except Exception as e:
                    print(f"❌ Error flipping bit: {e}")

            for i in range(len(stripe_data)):
                chunk = stripe_data[i]
                block_type = stripe_type
                block_index = stripe_index
                total_chunks = len(stripe_data)
                stripe_count = len(self.files[file_name]['data'])
                # if random_bit_flip and chunck:
                #     chunck = chunck[1:]

                message = {
                    "type": "read",
                    "data": {
                        "chunk": chunk,
                        "chunk-index": i,
                        "chunk-count": total_chunks,
                        "block-type": block_type,
                        "block-index": block_index,
                        "stripe-number": stripe_number,
                        "stripe-count": stripe_count,
                        "n": n,
                        "file-name": file_name,
                    }
                }
                print(f"Reading chunk {i} of block {block_index} of type {block_type} for file {file_name}, stripe {stripe_number}")
                self.send_with_command_port(message, addr)

            message = {
                "type": "read-complete",
                "data": {
                    "status": "success",
                    "message": f"✅ Read block {stripe_number} for file {file_name} successfully",
                    "file-name": file_name,
                    "n": n,
                }
            }
            self.send_with_command_port(message, addr)

        except Exception as e:
            print(f"❌ Error handling read message: {e}")
            ack_message = {
                "type": "read-ack",
                "data": {
                    "status": "error",
                    "message": f"❌ Error reading block: {e}"
                }
            }
            self.send_with_command_port(ack_message, addr)


    # ---------------------------------------------------------------

    def send_to_manager(self, message):
        """Send message to manager and return response"""
        print(f"📨 Sending {message.get('type')} message to manager address {self.manager_address[0]}:{self.manager_address[1]}")

        self.manager_socket.sendto(json.dumps(message).encode(), self.manager_address)

    def send_with_command_port(self, message, addr):
        """Send message to command and return response"""
        print(f"📨 Sending {message.get('type')} message to command address {addr[0]}:{addr[1]}")

        self.command_socket.sendto(json.dumps(message).encode(), addr)

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
                print("3. print files")
                print("=" * 20)
                
                command = input("Enter command: ").strip()
                    
                if command == "1":
                    self.send_deregister_disk()
                elif command == "2":
                    break
                elif command == "3":
                    print("files: ", self.files['a.txt'])
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
            