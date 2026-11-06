# user_threaded_v1.py
# Hunter Flechsig, 1225292003
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
import random


class UserProcess:
    def __init__(self, name, ip, m_port, c_port, manager_address):
        self.name = name
        self.ip = ip
        self.m_port = m_port
        self.c_port = c_port
        self.manager_address = manager_address
        self.running = True
        self.registered = False
        self.manager_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.read_complete = False

        self.chunk_size = 1024

        # thread safe data structures
        self.read_buffer = {}
        self.read_complete_buffer = {}
        self.lock = threading.Lock()

    # ----------------- Port handlers ------------------------------

    def handle_manager_port(self):
        """Handle manager port (m_port)"""
        with self.manager_socket:
            try:
                self.manager_socket.bind((self.ip, self.m_port))
            except Exception as e:
                print(f"❌ Error binding manager port: {e}")
                self.running = False
                os._exit(1)

            while self.running:
                try:
                    self.manager_socket.settimeout(1.0)  # allow checking self.running
                    data, addr = self.manager_socket.recvfrom(1024)
                    message = json.loads(data.decode())

                    print(
                        f"📩 Manager port received message from {addr[0]}:{addr[1]} of type {message.get('type', 'Unknown type')}"
                    )

                    # process manager messages
                    self.process_manager_message(message)

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
                    self.command_socket.settimeout(1.0)  # allow checking self.running
                    data, addr = self.command_socket.recvfrom(8192)
                    message = json.loads(data.decode())

                    print(
                        f"📩 Command port received message from {addr[0]}:{addr[1]} of type {message.get('type', 'Unknown type')}"
                    )

                    # process client messages
                    self.process_command_message(message)

                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"❌ Client port error: {e}")

    # ----------------- Message handlers ------------------------------

    def process_manager_message(self, message):
        """Process messages received on manager port"""
        try:
            match message.get("type"):
                case "register-user":

                    if message.get("data", {}).get("status", "No status") == "success":
                        self.registered = True
                        print("✅ Registration successful!")
                    else:
                        self.running = False
                        print(
                            f"❌ Error Registering User: {message.get('data', {}).get('message', 'No message')}"
                        )
                        os._exit(1)

                case "deregister-user":

                    if message.get("data", {}).get("status", "No status") == "success":
                        self.running = False
                        self.registered = False
                        print("✅ Deregistration successful! Exiting...")
                        os._exit(0)
                    else:
                        print(
                            f"❌ Error Deregistering User: {message.get('data', {}).get('message', 'No message')}"
                        )

                case "copy":
                    self.handle_copy(message)

                case "read":
                    self.handle_read(message)

                case "configure-dss":
                    if message.get("data", {}).get("status", "No status") == "success":
                        print("✅ Configure DSS successful!")
                    else:
                        print(
                            f"❌ Error Configuring DSS: {message.get('data', {}).get('message', 'No message')}"
                        )

                case "ls-res":
                    if message.get("data", {}).get("status", "No status") == "success":
                        files = message.get("data", {}).get("data", [])
                        print("Files in system:")
                        print(files)

                case "disk-failure-res":
                    self.handle_disk_failure(message)

                case _:
                    print(
                        f"Unknown manager message: {message.get('type', 'Unknown type')}"
                    )
                    return

        except Exception as e:
            print(f"Error processing manager message: {e}")

    def process_command_message(self, message):
        """Process messages received on command port"""
        try:
            match message.get("type"):
                case "read":
                    self.handle_read_command(message)
                case "read-complete":
                    self.handle_read_complete(message)
                case "copy-ack":
                    print(f"{message.get('data', {}).get('message', 'No message')}")
                case _:
                    print(
                        f"Unknown client message: {message.get('type', 'Unknown type')}"
                    )
        except Exception as e:
            print(f"Error processing client message: {e}")

    # ------------------- Response handlers ------------------------------

    def handle_disk_failure(self, message):
        dss_data = message.get("data", {}).get("data", {})

        print(f"Handling disk failure: {dss_data}")

        # pick a disk
        disk = random.choice(dss_data.get("disks", []))

        print(f"Handling disk failure. Disk: {disk['disk-name']}")

        message = {
            "type": "fail",
        }
        self.send_with_command_port(message, (disk["Ipv4"], disk["c-port"]))

        try:
            # Note: using existing command_socket from thread, don't close it
            original_timeout = self.command_socket.gettimeout()
            self.command_socket.settimeout(10.0)  # wait up to 10 seconds
            data, addr = self.command_socket.recvfrom(1024)
            response = json.loads(data.decode())

            print(
                f"📩 Command port received message from {addr[0]}:{addr[1]} of type {response.get('type', 'Unknown type')}"
            )

            if response.get("type") == "fail-ack":
                self.disk_failure(dss_data, disk)
        except socket.timeout:
            print("❌ Timeout waiting for fail-ack from disk")
        except Exception as e:
            print(f"❌ Client port error while handling disk failure: {e}")
        finally:
            # Restore original timeout
            self.command_socket.settimeout(original_timeout)

    def handle_read_complete(self, message):
        """Handle read complete message"""

        data = message.get("data", {})
        file_name = data.get("file-name")
        n = data.get("n")
        block_index = data.get("block-index")
        stripe_index = data.get("stripe-index")

        print(
            f"Read complete message received for file {file_name}, stripe {stripe_index}, block {block_index}"
        )

        if file_name not in self.read_complete_buffer:
            self.read_complete_buffer[file_name] = 0

        self.read_complete_buffer[file_name] += 1

        if self.read_complete_buffer[file_name] == n:
            del self.read_complete_buffer[file_name]
            self.read_complete = True

    def handle_read_command(self, message):
        """Handle read message"""

        data = message.get("data", {})
        file_name = data.get("file-name")
        stripe_number = data.get("stripe-number")
        stripe_count = data.get("stripe-count")
        block_index = data.get("block-index")
        n = data.get("n")
        chunk_index = data.get("chunk-index")
        chunk_count = data.get("chunk-count")
        chunk = data.get("chunk")
        block_type = data.get("block-type")

        print(
            f"Saving data for file {file_name}, stripe {stripe_number}, block {block_index}, chunk {chunk_index}"
        )

        # Initialize buffer if needed
        if file_name not in self.read_buffer:
            self.read_buffer[file_name] = {
                "data": [
                    [[None for _ in range(chunk_count)] for _ in range(n)]
                    for _ in range(stripe_count)
                ],
                "type": [[None for _ in range(n)] for _ in range(stripe_count)],
                "block_index": [[None for _ in range(n)] for _ in range(stripe_count)],
                "n": n,
            }

        self.read_buffer[file_name]["data"][stripe_number][block_index % n][
            chunk_index
        ] = base64.b64decode(chunk)
        self.read_buffer[file_name]["type"][stripe_number][block_index % n] = block_type
        self.read_buffer[file_name]["block_index"][stripe_number][
            block_index % n
        ] = block_index

    def copy_to_disk_worker(
        self,
        disk,
        file_name,
        block,
        block_type,
        stripe_index,
        stripe_count,
        block_index,
        n,
        chunk_count,
    ):
        """Copy to disk worker"""

        for i in range(chunk_count):
            print(
                f"Copying Stripe {stripe_index}, block {block_index}, chunk {chunk_count}"
            )
            chunk_data = block[i * self.chunk_size : (i + 1) * self.chunk_size]
            encoded_chunk = base64.b64encode(chunk_data).decode()
            message = {
                "type": "copy",
                "data": {
                    "chunk": encoded_chunk,
                    "chunk-index": i,
                    "chunk-count": chunk_count,
                    "block-type": block_type,
                    "file-name": file_name,
                    "stripe-index": stripe_index,
                    "stripe-count": stripe_count,
                    "block-index": block_index,
                    "n": n,
                },
            }
            self.send_with_command_port(message, (disk["Ipv4"], disk["c-port"]))

    def handle_copy(self, message):
        """Handle copy message"""
        data = message.get("data", {}).get("data", {})
        file_name = data.get("file-name")
        file_size = data.get("file-size")
        n = data.get("n")
        striping_unit = data.get("striping-unit")
        disks = data.get("disks")
        dss_name = data.get("dss-name", "No DSS name")

        num_stripes = math.ceil(file_size / ((n - 1) * striping_unit))

        print(f"Copying file {file_name} to dss {dss_name}")

        with open(self.file_copy_path(file_name), "rb") as f:

            for i in range(num_stripes):
                blocks = []
                stripe = None
                for _ in range(n - 1):
                    block = f.read(striping_unit)

                    # pad with nulls if not enough bytes
                    if len(block) < striping_unit:
                        block = block.ljust(striping_unit, b"\x00")
                    blocks.append(block)
                    stripe = block if stripe is None else stripe + block

                parity_block = self.calculate_parity_chunk(blocks)
                blocks.insert(i % n, parity_block)

                threads = []
                total_chunks = (striping_unit + self.chunk_size - 1) // self.chunk_size
                for disk_inx, block in enumerate(blocks):
                    block_index = i * n + disk_inx
                    parity = disk_inx == i % n
                    block_type = "parity" if parity else "data"
                    t = threading.Thread(
                        target=self.copy_to_disk_worker,
                        args=(
                            disks[disk_inx],
                            file_name,
                            block,
                            block_type,
                            i,
                            num_stripes,
                            block_index,
                            n,
                            total_chunks,
                        ),
                    )
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()
        message = {"type": "copy-complete", "data": {}}
        self.send_to_manager(message)

    def read_disk_worker(self, disk, file_name, stripe_number, striping_unit):
        """Read from disk worker with non-blocking select approach"""
        try:
            print(
                f"Reading Block from Stripe {stripe_number}, from disk {disk['disk-name']}"
            )
            # Send read request
            message = {
                "type": "read",
                "data": {
                    "file-name": file_name,
                    "stripe-number": stripe_number,
                    "striping-unit": striping_unit,
                },
            }
            self.send_with_command_port(message, (disk["Ipv4"], disk["c-port"]))

        except Exception as e:
            print(
                f"❌ Error reading from {disk['disk-name']} stripe {stripe_number}: {e}"
            )

    def handle_read(self, message):
        """Handle read message"""
        data = message.get("data", {}).get("data", {})
        file_name = data.get("file-name")
        file_size = data.get("file-size")
        n = data.get("n")
        striping_unit = data.get("striping-unit")
        disks = data.get("disks")

        num_stripes = math.ceil(file_size / ((n - 1) * striping_unit))

        for i in range(num_stripes):
            # while not verified success
            while True:
                self.read_complete = False
                threads = []
                for disk_inx in range(len(disks)):
                    t = threading.Thread(
                        target=self.read_disk_worker,
                        args=(disks[disk_inx], file_name, i, striping_unit),
                    )
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()

                while not self.read_complete:
                    time.sleep(0.1)

                if self.check_stripe(i, file_name, n):
                    print(f"⌛ Checking Stripe {i}")
                    break

        self.construct_file(file_name)

    # -----------------  Helpers ------------------------------

    def send_to_manager(self, message):
        """Send message to manager and return response"""
        print(
            f"📨 Sending {message.get('type')} message to manager address {self.manager_address[0]}:{self.manager_address[1]}"
        )

        self.manager_socket.sendto(json.dumps(message).encode(), self.manager_address)

    def send_with_command_port(self, message, addr):
        """Send message to command and return response"""
        print(
            f"📨 Sending {message.get('type')} message to command address {addr[0]}:{addr[1]}"
        )

        self.command_socket.sendto(json.dumps(message).encode(), addr)

    def construct_file(self, file_name):
        """Handle read complete message"""
        # Write the cleaned data to file
        # delete file if it already exists
        file_path = "./files-read/" + file_name + ".txt"
        if os.path.exists(file_path):
            os.remove(file_path)

        # Collect all data first - only from data blocks, not parity blocks
        all_data = b""

        for stripe_index, stripe in enumerate(self.read_buffer[file_name]["data"]):
            for block_index, block in enumerate(stripe):
                # Check if this is a data block (not parity)
                if block and all(chunk for chunk in block):
                    block_type = self.read_buffer[file_name]["type"][stripe_index][
                        block_index
                    ]
                    if block_type == "data":
                        # This is a data block, collect all chunks
                        block_data = b""
                        for chunk in block:
                            if chunk is not None:
                                block_data += chunk
                        all_data += block_data

        # Strip trailing null bytes
        all_data = all_data.rstrip(b"\x00")
        with open(file_path, "wb") as f:
            f.write(all_data)

        del self.read_buffer[file_name]

        res = filecmp.cmp(file_path, self.file_copy_path(file_name))
        if res:
            print("Files are the same")
        else:
            print("Files are different")

    def calculate_parity_chunk(self, chunks):
        """Calculate parity chunk"""
        # Initialize with the first chunk
        parity_chunk = chunks[0]

        # XOR with each subsequent chunk
        for chunk in chunks[1:]:
            parity_chunk = bytes(a ^ b for a, b in zip(parity_chunk, chunk))

        return parity_chunk

    def check_stripe(self, stripe_number, file_name, n):
        print(f"Checking stripe {stripe_number} for file {file_name}")
        """Check stripe and return blocks for parity comparison"""
        data_blocks = []
        parity_block = None

        try:
            stripe = self.read_buffer[file_name]["data"][stripe_number]

            for block_index, block in enumerate(stripe):
                block_data = b""
                for chunk in block:
                    if chunk is not None:
                        block_data += chunk

                block_type = self.read_buffer[file_name]["type"][stripe_number][
                    block_index
                ]

                if block_type == "data":
                    data_blocks.append(block_data)
                elif block_type == "parity":
                    parity_block = block_data

            calculated_parity_block = self.calculate_parity_chunk(data_blocks)
            if parity_block == calculated_parity_block:
                print(f"✅ Stripe {stripe_number} is correct")
                return True
            else:
                print(f"❌ Stripe {stripe_number} is incorrect, 🔄 retrying... ")
                return False

        except Exception as e:
            print(f"❌ Error checking stripe {stripe_number} for file {file_name}: {e}")
            return False

    def file_copy_path(self, file_name):
        return "./files-copy/" + file_name + ".txt"

    # -----------------  Commands ------------------------------

    def send_register_user(self):
        """Send register user message to manager"""
        message = {
            "type": "register-user",
            "data": {
                "user-name": self.name,
                "Ipv4": self.ip,
                "m-port": self.m_port,
                "c-port": self.c_port,
            },
        }
        self.send_to_manager(message)

    def send_deregister_user(self):
        """Send deregister user message to manager"""
        message = {"type": "deregister-user", "data": {"user-name": self.name}}
        self.send_to_manager(message)

    def send_configure_dss(self):
        """Send configure dss message to manager"""
        dss_name = input("Enter DSS name: ")
        n = input("Enter number of disks: ")
        striping_unit = input("Enter striping unit: ")
        print("\n")

        message = {
            "type": "configure-dss",
            "data": {"dss-name": dss_name, "n": n, "striping-unit": striping_unit},
        }
        self.send_to_manager(message)

    def send_copy_file_to_dss(self):
        """Send copy file to dss message to manager"""
        files = os.listdir("./files-copy")
        print("Files:")
        for file in files:
            print(file)
        file_name = input("Enter file name: ")
        try:
            file_size = os.path.getsize(self.file_copy_path(file_name))
        except Exception as e:
            print(f"❌ Error getting file size: {e}")
            return

        print(f"\n")

        message = {
            "type": "copy",
            "data": {
                "file-name": file_name,
                "file-size": file_size,
                "owner": self.name,
            },
        }
        self.send_to_manager(message)

    def send_read_file_from_dss(self):
        """Send read file from dss message to manager"""
        file_name = input("Enter file name: ")
        dss_name = input("Enter dss name: ")
        print(f"\n")

        message = {
            "type": "read",
            "data": {
                "file-name": file_name,
                "dss-name": dss_name,
                "user-name": self.name,
            },
        }
        self.send_to_manager(message)

    def send_ls(self):
        """Send ls message to manager"""
        message = {"type": "ls", "data": {}}
        self.send_to_manager(message)

    def send_disk_failure(self):
        """Send disk failure message to manager"""
        dss_name = input("Enter dss name: ")
        print(f"\n")

        message = {
            "type": "disk-failure",
            "data": {"dss-name": dss_name},
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
                print("2. copy file to dss")
                print("3. read file from dss")
                print("4. ls")
                print("5. deregister-user")
                print("6. reprint commands")
                print("7. disk failure")
                print("8. exit")
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
                    self.send_copy_file_to_dss()
                elif command == "3":
                    self.send_read_file_from_dss()
                elif command == "4":
                    self.send_ls()
                elif command == "5":
                    self.send_deregister_user()
                elif command == "6":
                    continue
                elif command == "7":
                    self.send_disk_failure()
                elif command == "8":
                    break
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
    m_port = 31503
    c_port = 31504
    ports = [31500, 31999]

    manager_ip = "127.0.0.1"
    manager_port = ports[0]

    args = sys.argv[1:]
    options = "hn:i:m:c:M:P:h"

    try:
        arguments, values = getopt.getopt(args, options)
        for currentArg, currentVal in arguments:
            if currentArg in ("-h", "--help"):
                print(
                    "User Process Help \n"
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
        print(
            f"❌ Error: manager-port {manager_port} must be in range {ports[0]}-{ports[1]}"
        )
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
