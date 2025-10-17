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
    check_parity,
    construct_read_file,
    compare_files,
)
import os
import random


def print_commands():
    print("User Commands")
    print("1. deregister        - deregister with manager and exit")
    print("2. configure-dss     - configure a distributed storage system")
    print("3. copy-file         - copy a file to the distributed storage system")
    print("4. read-file         - read a file from the distributed storage system")
    print("5. disk-failure      - simulate a disk failure")


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
                        # End of file reached - pad remaining blocks with nulls
                        null_block = b"\x00" * striping_unit
                        blocks_data.append(null_block)

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
        disk_addr = (disk.get("ip"), disk.get("c_port"))
        id = generate_id()
        event = self.events.add_event(id)
        chunks = split_block_into_chunks(block_data)
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

        if response is None or not check_ok(response, "response", "copy-block"):
            print(
                f"❌ Error sending block {block_index} of file '{filename}' to disk {disk.get('name')}"
            )
            return

        for chunk_index, chunk in enumerate(chunks):
            chunk_id = generate_id()
            send_message(
                self.command_socket,
                disk_addr,
                ok_request(
                    "copy-chunk",
                    {
                        "file-name": filename,
                        "stripe-index": stripe_index,
                        "chunk-index": chunk_index,
                        "chunk-data": list(chunk),
                    },
                    id=chunk_id,
                ),
            )

        print(
            f"✅ Sent block {block_index} ({block_type}) of file '{filename}' to disk {disk.get('name')}"
        )

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
            disks = message_data.get("disks", [])
            num_stripes = calculate_num_stripes(file_size, striping_unit, num_disks)

            all_stripe_data = self.read_file_2(
                filename, file_size, num_stripes, disks, num_disks
            )

            print(f"\n✅ File '{filename}' read completed")

            # Write the reconstructed file
            construct_read_file("./files-read", filename, all_stripe_data, file_size)
            compare_files(f"./files-copy/{filename}", f"./files-read/{filename}")

        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return

    def read_file_2(self, filename, file_size, num_stripes, disks, num_disks):
        print(f"📋 Reading file: {filename} ({file_size} bytes)")
        self.files_data[filename] = {}

        # List to store all stripe data for file reconstruction
        all_stripe_data = []

        for stripe_index in range(num_stripes):
            print(f"\n📦 Reading stripe {stripe_index + 1}/{num_stripes}")
            data_incorrect = True
            while data_incorrect:
                stripe_blocks = {}  # Use dictionary, not list
                threads = []

                for disk_index, disk in enumerate(disks):
                    t = threading.Thread(
                        target=self.read_block,
                        args=(
                            disk,
                            stripe_index,
                            filename,
                            disk_index,
                            stripe_blocks,  # Pass dict to store result
                        ),
                    )
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()

                # Separate parity block from data blocks
                parity_block = None
                data_blocks_dict = {}  # Use dict to track block_index -> block_data
                parity_disk_index = None

                for disk_idx, block_info in stripe_blocks.items():
                    if block_info is None:
                        print(f"⚠️  Block from disk {disk_idx} is None")
                        continue
                    block_data, block_type, block_index = block_info
                    if block_type == "parity":
                        parity_block = block_data
                        parity_disk_index = disk_idx
                    else:
                        data_blocks_dict[block_index] = block_data

                # Sort data blocks by block_index to maintain correct order
                data_blocks = [
                    data_blocks_dict[i] for i in sorted(data_blocks_dict.keys())
                ]

                # Check if we have all blocks
                if parity_block is None or len(data_blocks) != num_disks - 1:
                    print(f"❌ Missing blocks for stripe {stripe_index}, retrying...")
                    data_incorrect = True
                    continue

                # Verify data integrity with parity
                if check_parity(data_blocks, parity_block):
                    data_incorrect = False
                else:
                    print("❌ Data integrity check failed, re-reading stripe")
                    data_incorrect = True

            # Check if we got all blocks for this stripe
            print(
                f"   Retrieved {len(stripe_blocks)} blocks from stripe {stripe_index}"
            )

            # Store the stripe data for file reconstruction
            stripe_data_list = [
                block_info
                for block_info in stripe_blocks.values()
                if block_info is not None
            ]
            all_stripe_data.append(stripe_data_list)

        return all_stripe_data

    def read_block(self, disk, stripe_index, filename, disk_index, result_dict):
        """Read a block from a disk and store result in result_dict"""
        disk_addr = (disk.get("ip"), disk.get("c_port"))
        id = generate_id()
        event = self.events.add_event(id)
        send_message(
            self.command_socket,
            disk_addr,
            ok_request(
                "read-block",
                {
                    "file-name": filename,
                    "stripe-index": stripe_index,
                },
                id=id,
            ),
        )
        event.wait()
        response = self.events.get_event_data(id)

        if response is None or not check_ok(response, "response", "read-block"):
            print(
                f"❌ Error reading stripe {stripe_index} of file '{filename}' from disk {disk.get('name')}"
            )
            result_dict[disk_index] = None
            return

        data = response.get("data", {})
        block_type = data.get("block-type")
        block_index = data.get("block-index")
        num_chunks = data.get("num-chunks")

        # Use block_index as storage key (globally unique across entire file)
        if filename not in self.files_data:
            self.files_data[filename] = {}

        self.files_data[filename][block_index] = {
            "chunks": [None] * num_chunks,
            "block_type": block_type,
            "block_index": block_index,
        }

        finish_id = generate_id()

        send_message(
            self.command_socket,
            disk_addr,
            ok_request(
                "read-chunks",
                {
                    "file-name": filename,
                    "stripe-index": stripe_index,
                    "block-index": block_index,  # Include block_index so chunks know where to go
                    "finish-id": finish_id,
                },
                id=id,
            ),
        )

        message = self.events.add_event_and_wait(finish_id, timeout=10)

        if message is None or not check_ok(message, "response", "read-chunks"):
            print("❌ Read chunks timeout - no response from disk OR error")
            result_dict[disk_index] = None
            return

        # Reconstruct block from chunks using block_index as key
        chunks_list = self.files_data[filename][block_index]["chunks"]

        # Check if all chunks were received
        if any(chunk is None for chunk in chunks_list):
            print(
                f"❌ Missing chunks for stripe {stripe_index} from disk {disk.get('name')}"
            )
            result_dict[disk_index] = None
            return

        # Concatenate all chunks to reconstruct the block
        block = b"".join(chunks_list)

        # Clean up storage
        del self.files_data[filename][block_index]

        result_dict[disk_index] = (block, block_type, block_index)

    def disk_failure(self):
        dss_name = input("Enter DSS name: ")
        id = generate_id()
        send_message(
            self.manager_socket,
            self.manager_address,
            ok_request(
                "disk-failure",
                {
                    "dss-name": dss_name,
                },
                id=id,
            ),
        )

        message = self.events.add_event_and_wait(id, timeout=5)

        if message is None:
            print("❌ Disk failure timeout - no response from manager")
            return

        if not check_ok(message, "response", "disk-failure"):
            print("Disk failure unsuccessful: ", message.get("error"))
            return

        data = message.get("data", {})
        disks = data.get("disks", [])
        striping_unit = data.get("striping_unit")
        num_disks = data.get("num_disks")
        files = data.get("files", [])
        failed_disk = random.choice(disks)

        response = self.fail_disk(failed_disk)
        if not response:
            print("Disk failure unsuccessful during fail_disk call")
            return

        for file in files:
            filename = file.get("file-name")
            file_size = file.get("file-size")
            print(
                f"✅ Disk failure simulated for DSS '{dss_name}' on file '{filename}'"
            )

    def fail_disk(self, disk):
        disk_addr = (disk.get("ip"), disk.get("c_port"))
        id = generate_id()
        send_message(
            self.command_socket,
            disk_addr,
            ok_request(
                "fail",
                {},
                id=id,
            ),
        )

        message = self.events.add_event_and_wait(id, timeout=5)

        if message is None:
            print("❌ Fail disk timeout - no response from disk")
            return

        if not check_ok(message, "response", "fail-disk"):
            print("Disk failure unsuccessful: ", message.get("error"))
            return False

        return True

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
                    case "5":
                        self.disk_failure()
                    case _:
                        print("Unkown Command")

    def handle_read_chunk(self, message, addr):
        """Handle store-chunk request"""
        data = message.get("data")
        filename = data.get("file-name")
        block_index = data.get("block-index")
        chunk_index = data.get("chunk-index")
        chunk_data = data.get("chunk-data")

        # Store the chunk data using block_index as key
        self.files_data[filename][block_index]["chunks"][chunk_index] = bytes(
            chunk_data
        )

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
                case "response", "read-chunk":
                    self.handle_read_chunk(message, addr)
                case _:
                    print(
                        f"⚠️  Received unexpected message from {addr}: {action}, id={id}"
                    )

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
