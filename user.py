# user_threaded_v1.py
# Hunter Flechsig, 1225292005
# Approach #1: Separate Threads for Each Port
# User process uses separate threads to manage manager (m) and client (c) ports

import socket
import threading
import sys
from utils import (
    recieve_message,
    user_command_line_args,
    send_message,
    ok_request,
    check_ok,
    ThreadEvents,
    generate_id,
    print_files_in_directory,
    ok_response,
    read_blocks_from_file,
    calculate_num_stripes,
    calculate_parity,
    split_block_into_chunks,
    store_chunk,
    calculate_num_chunks,
)
import os


def print_commands():
    print("User Commands")
    print("1. deregister        - deregister with manager and exit")
    print("2. configure-dss     - configure a distributed storage system")
    print("3. copy-file         - copy a file to the distributed storage system")
    print("4. read-file         - read a file from the distributed storage system")


class UserProcess:
    def __init__(self, name, ip, m_port, c_port, manager_address):
        self.name = name
        self.ip = ip
        self.m_port = m_port
        self.c_port = c_port
        self.manager_address = manager_address

        self.running = True

        self.manager_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.manager_socket.bind((self.ip, self.m_port))
        self.command_socket.bind((self.ip, self.c_port))

        self.files_data = {}
        self.events = ThreadEvents()
        self.register_user()

    def register_user(self):
        send_message(
            self.manager_socket,
            self.manager_address,
            ok_request(
                "register-user",
                {
                    "name": self.name,
                    "ip": self.ip,
                    "c_port": self.c_port,
                    "m_port": self.m_port,
                },
            ),
        )

        message, _ = recieve_message(self.manager_socket, 3)

        print(message)

        if message is None:
            print("No register user message recieved from manager")
            sys.exit(1)

        if not check_ok(message, "response", "register-user"):
            print("Failed to register user : ", message.get("error"))
            sys.exit(1)

        print("User registered successfully")
        self.start()

    def configure_dss(self):
        dss_name = input("Enter DSS name: ")
        num_disks = int(input("Enter number of disks: "))
        striping_unit = int(input("Enter striping unit (in bytes): "))
        id = generate_id()
        send_message(
            self.manager_socket,
            self.manager_address,
            ok_request(
                "configure-dss",
                {
                    "name": dss_name,
                    "num_disks": num_disks,
                    "striping_unit": striping_unit,
                },
                id=id,
            ),
        )

        message = self.events.add_event_and_wait(id, timeout=5)

        if message is None:
            print("❌ Configure DSS timeout - no response from manager")
            return

        if not check_ok(message, "response", "configure-dss"):
            print("Configure DSS unsuccessful: ", message.get("error"))
            return

        print("Configure DSS successful")

    def deregister_user(self):
        id = generate_id()
        send_message(
            self.manager_socket,
            self.manager_address,
            ok_request(
                "deregister-user",
                {
                    "name": self.name,
                },
                id=id,
            ),
        )

        message = self.events.add_event_and_wait(id, timeout=5)

        if message is None:
            print("❌ Deregister timeout - no response from manager")
            return

        if not check_ok(message, "response", "deregister-user"):
            print("deregister unsucessful")
            return

        print("dergister sucessful")
        self.running = False

    def copy_file(self):
        try:
            print_files_in_directory()
            filename = input("Enter filename to copy: ")
            path = f"./files-copy/{filename}"
            id = generate_id()
            try:
                file_size = os.path.getsize(path)

            except FileNotFoundError:
                print("File not found in files-copy directory")
                return

            send_message(
                self.manager_socket,
                self.manager_address,
                ok_request(
                    "copy-file",
                    {
                        "owner": self.name,
                        "file-name": filename,
                        "file-size": file_size,
                    },
                    id=id,
                ),
            )

            message = self.events.add_event_and_wait(id, timeout=5)

            if message is None:
                print("❌ Copy file timeout - no response from manager")
                return

            if not check_ok(message, "response", "copy-file"):
                print("Copy file unsuccessful: ", message.get("error"))
                return

            data = message.get("data", {})
            num_disks = data.get("num_disks")
            striping_unit = data.get("striping_unit")
            disks = data.get("disks", [])

            print(f"📋 Copying file: {filename} ({file_size} bytes)")
            print(f"   Disks: {num_disks}, Striping unit: {striping_unit}")

            # Calculate number of stripes
            num_stripes = calculate_num_stripes(file_size, striping_unit, num_disks)
            print(f"   Total stripes: {num_stripes}")

            # Read file blocks
            reader = read_blocks_from_file(path, striping_unit)

            block_index = 0
            for stripe_index in range(num_stripes):
                print(f"\n📦 Processing stripe {stripe_index + 1}/{num_stripes}")

                # Read (num_disks - 1) data blocks for this stripe
                blocks_data = []
                for disk_idx in range(num_disks - 1):
                    try:
                        block = next(reader)
                        blocks_data.append(block)
                    except StopIteration:
                        print(f"⚠️  Unexpected end of file at stripe {stripe_index}")
                        break

                # If we didn't get any blocks, we're done
                if not blocks_data:
                    print(f"ℹ️  No more data to process")
                    break

                # Calculate parity block
                parity_block = calculate_parity(blocks_data)

                # Insert parity at rotating position
                parity_index = stripe_index % num_disks
                blocks_data.insert(parity_index, parity_block)

                # Send each block to corresponding disk
                threads = []
                for disk_idx, block_data in enumerate(blocks_data):
                    # Make sure we have a corresponding disk
                    if disk_idx >= len(disks):
                        print(f"⚠️  Warning: No disk for block index {disk_idx}")
                        continue

                    disk = disks[disk_idx]
                    block_type = "parity" if disk_idx == parity_index else "data"

                    t = threading.Thread(
                        target=self.send_block,
                        args=(
                            block_data,
                            block_index,
                            block_type,
                            stripe_index,
                            num_stripes,
                            filename,
                            disk,
                        ),
                    )
                    t.start()
                    threads.append(t)
                    block_index += 1

                # Wait for all blocks in this stripe to be sent
                for t in threads:
                    t.join()

            print(f"\n✅ File '{filename}' copied successfully to DSS")

            # Notify manager that copy is complete
            send_message(
                self.manager_socket,
                self.manager_address,
                ok_response(
                    "copy-complete", {"file-name": filename, "owner": self.name}
                ),
            )
        except Exception as e:
            print(f"❌ Error copying file '{filename}': {e}")
            return

    def send_block(
        self,
        block_data,
        block_index,
        block_type,
        stripe_index,
        num_stripes,
        filename,
        disk,
    ):
        try:
            # Use c_port (with underscore) as that's what the manager sends
            disk_addr = (disk.get("ip"), disk.get("c_port"))
            id = generate_id()
            chunks = split_block_into_chunks(block_data)
            event = self.events.add_event(id)
            send_message(
                self.command_socket,
                disk_addr,
                ok_request(
                    "copy-block",
                    {
                        "file-name": filename,
                        "block-index": block_index,
                        "block-type": block_type,
                        "stripe-index": stripe_index,
                        "num-stripes": num_stripes,
                        "num-chunks": len(chunks),
                    },
                    id=id,
                ),
            )
            event.wait()
            response = self.events.get_event_data(id)

            if response is None:
                print(
                    f"❌ Store block timeout - no response from disk {disk.get('name')} for block {block_index}"
                )
                return

            if not check_ok(response, "response", "copy-block"):
                print(
                    f"❌ Store block unsuccessful from disk {disk.get('name')} for block {block_index}: ",
                    response.get("error"),
                )
                return

            # Send all chunks for this block (each chunk gets its own ID)
            for chunk_index, chunk in enumerate(chunks):
                chunk_id = generate_id()
                send_message(
                    self.command_socket,
                    disk_addr,
                    ok_request(
                        "copy-chunk",
                        {
                            "file-name": filename,
                            "block-index": block_index,
                            "stripe-index": stripe_index,
                            "chunk-index": chunk_index,
                            "chunk-data": list(chunk),
                        },
                        id=chunk_id,
                    ),
                )

            print(f"✅ Sent block {block_index} ({block_type}) to {disk.get('name')}")

        except Exception as e:
            print(
                f"❌ Error sending block {block_index} to disk {disk.get('name')}: {e}"
            )
            return

    def read_file(self):
        try:
            dss_name = input("Enter DSS name to read from: ")
            filename = input("Enter filename to read: ")
            id = generate_id()

            send_message(
                self.manager_socket,
                self.manager_address,
                ok_request(
                    "read-file",
                    {
                        "dss-name": dss_name,
                        "file-name": filename,
                        "owner": self.name,
                    },
                    id=id,
                ),
            )

            message = self.events.add_event_and_wait(id, timeout=5)

            if message is None:
                print("❌ Read file timeout - no response from manager")
                return

            if not check_ok(message, "response", "read-file"):
                print("❌ Read file unsuccessful: ", message.get("error"))
                return

            print(f"✅ Read file '{filename}' from DSS '{dss_name}' successful")
            message_data = message.get("data", {})
            file_size = message_data.get("file-size")
            num_disks = message_data.get("num_disks")
            striping_unit = message_data.get("striping_unit")
            num_stripes = calculate_num_stripes(file_size, striping_unit, num_disks)

            print(f"📋 Reading file: {filename} ({file_size} bytes)")

            # Initialize file storage structure
            if filename not in self.files_data:
                self.files_data[filename] = {}

            # Initialize storage for each stripe and block
            for stripe_index in range(num_stripes):
                if stripe_index not in self.files_data[filename]:
                    self.files_data[filename][stripe_index] = {}

                # Initialize storage for each block in this stripe (num_disks blocks per stripe)
                for block_index in range(num_disks):
                    # Calculate number of chunks per block (assuming same chunk size as sending)
                    num_chunks = calculate_num_chunks(striping_unit)

                    self.files_data[filename][stripe_index][block_index] = {
                        "chunks": [None] * num_chunks,  # Pre-allocated list
                        "expected_chunks": num_chunks,
                        "metadata": {
                            "block_type": "unknown",  # Will be determined when reading
                            "stripe_index": stripe_index,
                            "num_stripes": num_stripes,
                        },
                    }

            print(
                f"✅ Initialized storage for {num_stripes} stripes, {num_disks} blocks per stripe"
            )

        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return

    def start(self):
        # Start the manager port listener thread
        threading.Thread(target=self.handle_manager_port, daemon=True).start()
        # Start the command port listener thread for disk responses
        threading.Thread(target=self.handle_command_port, daemon=True).start()

        with self.manager_socket, self.command_socket:
            while self.running:
                print_commands()
                command = input("input command:")

                match command:
                    case "1":
                        self.deregister_user()
                    case "2":
                        self.configure_dss()
                    case "3":
                        self.copy_file()
                    case "4":
                        self.read_file()
                    case _:
                        print("Unkown Command")

    def handle_command_port(self):
        """Handle command port (c_port) - receives responses from disks"""
        while self.running:
            message, addr = recieve_message(self.command_socket)
            if message is None:
                continue

            type, action, id = (
                message.get("type"),
                message.get("action"),
                message.get("id"),
            )

            # Check if this is a response to a waiting event
            if self.events.event_exists(id):
                self.events.set_event(id, message)
                continue

            match type, action:
                case "respond", "copy-chunk":
                    self.handle_copy_chunk(message, addr)
                case _:
                    print(f"⚠️  Received unexpected message from {addr}: {action}")

    def handle_copy_chunk(self, message, addr):
        """Handle individual chunk of a block"""
        data = message.get("data")
        filename = data.get("file-name")
        block_index = data.get("block-index")
        stripe_index = data.get("stripe-index")
        chunk_index = data.get("chunk-index")
        chunk_data = data.get("chunk-data")

        print(
            f"Received chunk {chunk_index} for block {block_index} of file {filename} stripe {stripe_index}"
        )

        # Store the chunk using utility function
        success = store_chunk(
            self.files_data,
            filename,
            stripe_index,
            block_index,
            chunk_index,
            chunk_data,
        )

        if not success:
            print(
                f"❌ Received chunk for unknown block: {filename} stripe {stripe_index} block {block_index}"
            )
            return

    def handle_manager_port(self):
        """Handle manager port (m_port)"""
        while self.running:
            message, addr = recieve_message(self.manager_socket)
            if message is None:
                continue

            type, action, id = (
                message.get("type"),
                message.get("action"),
                message.get("id"),
            )

            if self.events.event_exists(id):
                self.events.set_event(id, message)
                continue

            match type, action:
                case _:
                    print(f"❌ Unknown message ({type}, {action}) from manager")


def main():

    name, ip, m_port, c_port, manager_address = user_command_line_args()

    # Create and start user process
    user = UserProcess(name, ip, m_port, c_port, manager_address)


if __name__ == "__main__":
    main()
