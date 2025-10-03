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
import base64
import math
import filecmp

class UserProcess:
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
        self.read_buffer = {}
        self.lock = threading.Lock()

    def handle_manager_port(self):
        """Handle manager port (m_port)"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as self.manager_socket:
            try:
                self.manager_socket.bind((self.ip, self.m_port))
            except Exception as e:
                print(f"❌ Error binding manager port: {e}")
                self.running = False
                os._exit(1)

            while self.running:
                try:
                    self.manager_socket.settimeout(1.0) # allow checking self.running
                    data, addr = self.manager_socket.recvfrom(1024)
                    message = json.loads(data.decode())

                    print(f"Manager port received message from {addr[0]}:{addr[1]}")

                    # process manager messages
                    self.process_manager_message(message)

                    print("=" * 20, "\n")
                
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
                os._exit(1)

            while self.running:
                try:
                    self.command_socket.settimeout(1.0) # allow checking self.running
                    data, addr = self.command_socket.recvfrom(8192)
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
        print(f"Process Manager response of type {message.get('type', 'Unknown type')}")
        try:
            match message.get('type'):
                case 'register-user':

                    if message.get('data', {}).get('status', 'No status') == 'success':
                            self.registered = True
                            print("✅ Registration successful!")
                    else:
                            self.running = False
                            print(f"❌ Error Registering User: {message.get('data', {}).get('message', 'No message')}")
                            os._exit(1)

                case 'deregister-user':

                    if message.get('data', {}).get('status', 'No status') == 'success':
                        print("✅ Deregistration successful! Exiting...")
                        self.running = False
                        self.registered = False
                        os._exit(0)
                    else:
                        print(f"❌ Error Deregistering User: {message.get('data', {}).get('message', 'No message')}")


                case 'copy':
                    self.handle_copy(message)

                case 'read':
                    self.handle_read(message)

                case 'configure-dss':
                    if message.get('data', {}).get('status', 'No status') == 'success':
                        print("✅ Configure DSS successful!")
                    else:
                        print(f"❌ Error Configuring DSS: {message.get('data', {}).get('message', 'No message')}")
                
                case _:
                    print(f"Unknown manager message: {message.get('type', 'Unknown type')}")
                    return

        except Exception as e:
            print(f"Error processing manager message: {e}")

    
    def process_command_message(self, message):
        """Process messages received on command port"""
        try:
            match message.get('type'):
                case 'read':
                    self.handle_read_command(message)
                case 'read-complete':
                    self.handle_read_complete(message)
                case _:
                    print(f"Unknown client message: {message.get('type', 'Unknown type')}")
        except Exception as e:
            print(f"Error processing client message: {e}")

    
    # ------------------- Response handlers ------------------------------

    def handle_read_complete(self, message):
        """Handle read complete message"""
        data = message.get('data', {})
        file_name = data.get('file-name')
        print(f"Read complete for file {file_name}")
        
        # Collect all data first
        all_data = b""
        for stripe in self.read_buffer[file_name]:
            for block in stripe:
                for chunk in block:
                    chunk_data, chunk_type = chunk['data'], chunk['type']
                    if chunk_type == "data":
                        all_data += chunk_data
        
        # Strip trailing null bytes
        all_data = all_data.rstrip(b'\x00')
        
        # Write the cleaned data to file
        with open(file_name + "_read", "wb") as f:
            f.write(all_data)
        
        self.read_buffer[file_name] = []

        res = filecmp.cmp(file_name, file_name + "_read")
        if res:
            print("Files are the same")
        else:
            print("Files are different")

    def handle_read_command(self, message):
        """Handle read message"""
        data = message.get('data', {})
        file_name = data.get('file-name')
        stripe_number = data.get('stripe-number')
        striping_unit = data.get('striping-unit')
        stripe_count = data.get('stripe-count')
        block_index = data.get('block-index')
        n = data.get('n')
        chunk_index = data.get('chunk-index')
        chunk_count = data.get('chunk-count')
        chunk = data.get('chunk')

        # Initialize buffer if needed
        if file_name not in self.read_buffer:            
            self.read_buffer[file_name] = [[[None for _ in range(chunk_count)] for _ in range(n)] for _ in range(stripe_count)]

        self.read_buffer[file_name][stripe_number][block_index % n][chunk_index] = {
            'data': base64.b64decode(chunk),
            'type': data.get('block-type', 'data'),
        }


    def calculate_parity_chunk(self, chunks):
        """Calculate parity chunk"""        
        # Initialize with the first chunk
        parity_chunk = chunks[0]
        
        # XOR with each subsequent chunk
        for chunk in chunks[1:]:
            parity_chunk = bytes(a ^ b for a, b in zip(parity_chunk, chunk))
        
        return parity_chunk

    def copy_to_disk_worker(self, disk, chunk, file_name, parity, stripe_number, block_index, striping_unit, n):
        """Copy to disk worker"""
        chunk_size = 1024
        total_chunks = (striping_unit + chunk_size - 1) // chunk_size

        for i in range(total_chunks):
            chunk_data= chunk[i:i+chunk_size]
            encoded_chunk = base64.b64encode(chunk_data).decode()
            message = {
                "type": "copy",
                "data": {
                    "chunk": encoded_chunk,
                    "chunk-index": i,
                    "chunk-count": total_chunks,
                    "block-type": "data" if not parity else "parity",
                    "file-name": file_name,
                    "stripe-number": stripe_number,
                    "block-index": block_index,
                    "n": n,
                    "striping-unit": striping_unit
                }
            }
            self.send_with_command_port(message, (disk['Ipv4'], disk['c-port']))
        

    def handle_copy(self, message):
        """Handle copy message"""
        data = message.get('data', {}).get('data', {})
        print(f"Copying data to dss: {data.get('dss-name')}")
        file_name = data.get('file-name')
        file_size = data.get('file-size')
        n = data.get('n')
        striping_unit = data.get('striping-unit')
        disks = data.get('disks')

        num_stripes = math.ceil(file_size / ((n-1) * striping_unit))
        

        with open(file_name, "rb") as f:
           
            for i in range(num_stripes):
                chunks = []
                for _ in range(n-1):
                    chunk = f.read(striping_unit)

                    # pad with nulls if not enough bytes
                    if len(chunk) < striping_unit:
                        chunk = chunk.ljust(striping_unit, b"\x00")
                    chunks.append(chunk)

                parity_chunk = self.calculate_parity_chunk(chunks)
                chunks.insert(i % n, parity_chunk)

                threads = []
                for disk_inx, chunck in enumerate(chunks):
                    print(f"Copying to disk {disks[disk_inx]['disk-name']}")
                    block_index = i*n + disk_inx
                    t = threading.Thread(target=self.copy_to_disk_worker, args=(disks[disk_inx], chunck, file_name, (disk_inx == i%n), i, block_index, striping_unit, n))
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()

        message = {
            "type": "copy-complete",
            "data": {}
        }
        self.send_to_manager(message)

    def read_disk_worker(self, disk, file_name, stripe_number, striping_unit):
        """Read from disk worker with non-blocking select approach"""
        try:
            # Send read request
            message = {
                "type": "read",
                "data": {
                    "file-name": file_name,
                    "stripe-number": stripe_number,
                    "striping-unit": striping_unit,
                }
            }
            self.send_with_command_port(message, (disk['Ipv4'], disk['c-port']))
        
        except Exception as e:
            print(f"❌ Error reading from {disk['disk-name']} stripe {stripe_number}: {e}")


    def handle_read(self, message):
        """Handle read message"""
        print(f"message: {message}")
        data = message.get('data', {}).get('data', {})
        print(f"Reading data from dss: {data.get('dss-name')}")
        file_name = data.get('file-name')
        file_size = data.get('file-size')
        n = data.get('n')
        striping_unit = data.get('striping-unit')
        disks = data.get('disks')

        num_stripes = math.ceil(file_size / ((n-1) * striping_unit))

        # Open file once for writing
        with open(file_name + "_read", "wb") as f:
            for i in range(num_stripes):
                threads = []
                for disk_inx in range(len(disks)):
                    print(f"Reading from disk {disks[disk_inx]['disk-name']}")
                    t = threading.Thread(target=self.read_disk_worker, args=(disks[disk_inx], file_name, i, striping_unit))
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()

                # Write data for this stri
    # ---------------------------------------------------------------

    def send_to_manager(self, message):
        """Send message to manager and return response"""
        print(f"Sending {message.get('type')} message to manager address {self.manager_address[0]}:{self.manager_address[1]}")
        
        self.manager_socket.sendto(json.dumps(message).encode(), self.manager_address)

    def send_with_command_port(self, message, addr):
        """Send message to command and return response"""
        print(f"Sending {message.get('type')} message to command address {addr[0]}:{addr[1]}")
        
        self.command_socket.sendto(json.dumps(message).encode(), addr)

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
        print("\n")
        
        message = {
            "type": "configure-dss",
            "data": {
                "dss-name": dss_name,
                "n": n,
                "striping-unit": striping_unit
            }
        }
        self.send_to_manager(message)
    
    def send_copy_file_to_dss(self):
        """Send copy file to dss message to manager"""
        # file_name = input("Enter file name: ")
        file_name = "a.txt"
        file_size = os.path.getsize("./" + file_name)
        print(f"\n")
        
        message = {
            "type": "copy",
            "data": {
                "file-name": file_name,
                "file-size": file_size,
                "owner": self.name
            }
        }
        self.send_to_manager(message)

    def send_read_file_from_dss(self):
        """Send read file from dss message to manager"""
        # file_name = input("Enter file name: ")
        file_name = "a.txt"
        dss_name = "dss1"
        # dss_name = input("Enter dss name: ")
        print(f"\n")
        
        message = {
            "type": "read",
            "data": {
                "file-name": file_name,
                "dss-name": dss_name,
                "user-name": self.name
            }
        }
        self.send_to_manager(message)

    # ---------------------------------------------------------------


    # ---------------------------------------------------------------

    def start(self):
        """Start the user process"""

        """Start both port handlers in separate threads"""
        print(f"Starting user process: {self.name}")
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

        print("=" * 20, "\n")

        # Register with manager
        if self.running:
            self.send_to_manager({'type': 'copy-complete'})
            time.sleep(0.5)
            self.send_register_user()
        else:
            return
        
        # Main command loop
        try:
            while self.running:

                # Only show commands if user is registered
                if not self.registered:
                    time.sleep(0.1)                    
                    continue

                """Print commands"""
                print("=" * 20)
                print("Commands:")
                print("1. configure-dss")
                print("2. deregister-user")
                print("3. copy file to dss")
                print("4. reprint commands")
                print("5. exit")
                print("6. read file from dss")
                print("=" * 20)
                
                # Check if we're still running before waiting for input
                # if not self.running:
                #     break
                    
                command = input("Enter command: ").strip()
                
                # Check if we're still running after getting input
                # if not self.running:
                #     break
                    
                if command == "1":
                    self.send_configure_dss()
                elif command == "2":
                    self.send_deregister_user()
                elif command == "3":
                    self.send_copy_file_to_dss()
                elif command == "4":
                    continue
                elif command == "5":
                    break
                elif command == "6":
                    self.send_read_file_from_dss()
                else:
                    print("❌ Invalid command")

                time.sleep(0.5)

        except KeyboardInterrupt:
            self.send_deregister_user()
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
            