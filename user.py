# user.py
# Hunter Flechsig, 1225292005

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
    check_ok_message,
)
import os
import random


# Print available user commands
def print_commands():
    print("User Commands")
    print("--- ---")
    print("1. configure-dss     - configure a distributed storage system")
    print("2. copy-file         - copy a file to the distributed storage system")
    print("3. read-file         - read a file from the distributed storage system")
    print("4. disk-failure      - simulate a disk failure")
    print("5. ls                - list files ")
    print("6. decomission-dss   - decomission a distributed storage system")
    print("exit. deregister        - deregister with manager and exit")
    print("help. help              - show this help message")
    print("--- ---")


# UserProcess class for managing user operations
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
        print("Registering user with manager...")
        try:
            # send register user message to manager
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

            # wait for response from manager
            message, _ = recieve_message(self.manager_socket, 5)

            # check if response came in and status is successful
            if message is None:
                print("❌ Register user timeout - no response from manager")
                sys.exit(1)

            status, error_message = check_ok_message(
                message, "response", "register-user"
            )
            if not status:
                print("Failed to register user : ", error_message)
                sys.exit(1)

            # User registered successfully - start main loop
            print("User registered successfully \n")
            self.start()
        except Exception as e:
            print(f"❌ Error registering user: {e}")
            sys.exit(1)

    def configure_dss(self):
        """Configure a distributed storage system (DSS)"""
        try:
            dss_name = input("Enter DSS name: ")
            num_disks = int(input("Enter number of disks: "))
            striping_unit = int(input("Enter striping unit (in bytes): "))
            # Send configure-dss request to manager
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

            # Wait response from manager with id of request
            message = self.events.add_event_and_wait(id, timeout=5)

            # Check if response came in and status is successful
            if message is None:
                print("❌ Configure DSS timeout - no response from manager")
                return

            status, error_message = check_ok_message(
                message, "response", "configure-dss"
            )

            if not status:
                print("Configure DSS unsuccessful: ", error_message)
                return

            print("Configure DSS successful")
        except Exception as e:
            print(f"❌ Error configuring DSS: {e}")
            return

    def deregister_user(self):
        """Deregister user from manager and exit"""
        try:
            # Send deregister user request to manager
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

            # Wait response from manager with id of request
            message = self.events.add_event_and_wait(id, timeout=5)

            # Check if response came in and status is successful
            if message is None:
                print("❌ Deregister user timeout - no response from manager")
                return

            status, error_message = check_ok_message(
                message, "response", "deregister-user"
            )

            if not status:
                print("Deregister unsuccessful: ", error_message)
                return

            # set running to false to exit main loop
            self.running = False
            print("Deregister successful, exiting...")
        except Exception as e:
            print(f"❌ Error deregistering user: {e}")
            return

    def copy_file(self):
        """Copy a file to the distributed storage system (DSS)"""
        try:
            # Get file to copy from user
            print_files_in_directory()
            filename = input("Enter filename to copy: ")
            print("")
            path = f"./files-copy/{filename}"
            id = generate_id()
            try:
                file_size = os.path.getsize(path)

            # File not found
            except FileNotFoundError:
                print("File not found in files-copy directory")
                return

            # Send copy-file request to manager
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

            # Wait response from manager with id of request
            message = self.events.add_event_and_wait(id, timeout=5)

            # Check if response came in and status is successful
            if message is None:
                print("❌ Copy file timeout - no response from manager")
                return

            status, error_message = check_ok_message(message, "response", "copy-file")

            if not status:
                print("Copy file unsuccessful: ", error_message)
                return

            # Get DSS configuration from manager response
            data = message.get("data", {})
            num_disks = data.get("num_disks")
            striping_unit = data.get("striping_unit")
            disks = data.get("disks", [])

            # send file to DSS
            self.send_file(filename, path, file_size, num_disks, striping_unit, disks)

            # Notify manager that copy is complete
            id = generate_id()
            send_message(
                self.manager_socket,
                self.manager_address,
                ok_request(
                    "copy-complete", {}, id=id
                ),
            )

            response = self.events.add_event_and_wait(id, timeout=5)

            if response is None:
                print("❌ Copy complete timeout - no response from manager")
                return
            
            if not check_ok(response, "response", "copy-complete"):
                print("❌ Copy complete unsuccessful: ", response.get("error"))
                return
            
            print("✅ Copy complete successful")
        except Exception as e:
            print(f"❌ Error copying file '{filename}': {e}")
            return

    def send_file(self, filename, path, file_size, num_disks, striping_unit, disks):
        """Send file to DSS using RAID 5 striping with parity"""

        print("\n--- Starting file copy process ---")
        print(f"📋 Copying file: {filename} ({file_size} bytes)")
        print(f"   Disks: {num_disks}, Striping unit: {striping_unit}")

        # Calculate number of stripes
        num_stripes = calculate_num_stripes(file_size, striping_unit, num_disks)
        print(f"   Total stripes: {num_stripes}")

        # Read file blocks
        reader = read_blocks_from_file(path, striping_unit)

        block_index = 0

        # Process each stripe
        for stripe_index in range(num_stripes):
            print(f"\n📦 Sending stripe {stripe_index + 1}/{num_stripes}")

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
                disk = disks[disk_idx]
                block_type = "parity" if disk_idx == parity_index else "data"

                # Start a thread to send the block
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

    # thread to send a block to a disk
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
        """Send a block to a disk in the DSS"""
        disk_addr = (disk.get("ip"), disk.get("c_port"))
        id = generate_id()
        event = self.events.add_event(id)
        # split block into chunks
        chunks = split_block_into_chunks(block_data)
        print(f"\n--- Sending block {block_index} in {len(chunks)} chunks ---")

        # Send copy-block request to disk
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
        # Wait for copy-block response - indicates disk is ready for chunks
        event.wait()
        response = self.events.get_event_data(id)

        # Check if response came in and status is successful
        if response is None or not check_ok(response, "response", "copy-block"):
            print(
                f"❌ Error sending block {block_index} of file '{filename}' to disk {disk.get('name')}"
            )
            return

        # Send each chunk to disk
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

    def read_file(self):
        """Read a file from the distributed storage system (DSS)"""
        try:
            dss_name = input("Enter DSS name to read from: ")
            filename = input("Enter filename to read: ")
            id = generate_id()

            # Send read-file request to manager
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

            # Wait response from manager with id of request
            message = self.events.add_event_and_wait(id, timeout=5)

            if message is None:
                print("❌ Read file timeout - no response from manager")
                return

            if not check_ok(message, "response", "read-file"):
                print("❌ Read file unsuccessful: ", message.get("error"))
                return

            print(
                f"\n✅ File data retrieved for file '{filename}' from DSS '{dss_name}' successful"
            )

            # Get DSS configuration from manager response and other data needed to read file
            message_data = message.get("data", {})
            file_size = message_data.get("file-size")
            num_disks = message_data.get("num_disks")
            striping_unit = message_data.get("striping_unit")
            disks = message_data.get("disks", [])
            num_stripes = calculate_num_stripes(file_size, striping_unit, num_disks)

            # Read the file from DSS - get all stripe data back
            all_stripe_data = self.read_file_helper(
                filename, file_size, num_stripes, disks, num_disks, False
            )

            print(f"\n✅ File '{filename}' read completed")

            # Reconstructed file and compare
            construct_read_file("./files-read", filename, all_stripe_data, file_size)
            compare_files(f"./files-copy/{filename}", f"./files-read/{filename}")

            # Notify manager that read is complete
            id = generate_id()
            send_message(
                self.manager_socket,
                self.manager_address,
                ok_response(
                    "read-complete",
                    { "dss-name": dss_name},
                    id=id,
                ),
            )

            response = self.events.add_event_and_wait(id, timeout=5)

            if response is None:
                print("❌ Read complete timeout - no response from manager")
                return

            if not check_ok(response, "response", "read-complete"):
                print("❌ Read complete unsuccessful: ", response.get("error"))
                return

            print("✅ Read complete successful")


        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return

    def read_file_helper(
        self,
        filename,
        file_size,
        num_stripes,
        disks,
        num_disks,
        reconstruct,
        failed_disk=None,
    ):
        """Read file from DSS - 2 modes

        Modes:
        - Normal Read: reconstruct=False, failed_disk=None
            Reads all blocks from all disks, verifies data integrity with parity.
            Retries reading stripes until data integrity is confirmed.
        - Reconstruction Read: reconstruct=True, failed_disk=<disk_name>
            Skips reading from the failed disk and reconstructs missing blocks using parity.
        """

        print(f"📋 Reading file: {filename} ({file_size} bytes)")
        # Initialize storage for file data if not already present
        self.files_data[filename] = {}

        # List to store all stripe data for file reconstruction
        all_stripe_data = []

        # List to store reconstructed blocks to send after all reads complete
        reconstructed_blocks = []

        # Determine the index of the missing disk if in reconstruct mode
        missing_disk_idx = disks.index(failed_disk) if failed_disk else None

        # Iterate through each stripe in the file
        for stripe_index in range(num_stripes):
            print(f"\n📦 Reading stripe {stripe_index + 1}/{num_stripes}")
            data_incorrect = True

            # Retry reading stripes until data integrity is confirmed
            while data_incorrect:
                stripe_blocks = {}
                threads = []

                # Iterate through all disks with their original indices
                for disk_index, disk in enumerate(disks):
                    # Skip the failed disk if we're in reconstruct mode
                    if reconstruct and disk_index == missing_disk_idx:
                        print(f"   Skipping failed disk at index {disk_index}")
                        continue

                    # Start a thread to read the block
                    t = threading.Thread(
                        target=self.read_block,
                        args=(
                            disk,
                            stripe_index,
                            filename,
                            disk_index,
                            stripe_blocks,
                        ),
                    )
                    t.start()
                    threads.append(t)

                # Wait for all reads to complete
                for t in threads:
                    t.join()

                # If reconstruct mode and exactly one block is missing, reconstruct it
                if reconstruct:
                    print(
                        f"🔧 Reconstructing missing block from disk {missing_disk_idx}"
                    )

                    # Collect all available blocks IN DISK ORDER - needed for XOR
                    available_blocks = []
                    available_block_info = []
                    for disk_idx in range(num_disks):
                        if disk_idx != missing_disk_idx:
                            block_info = stripe_blocks.get(disk_idx)
                            if block_info:
                                block_data, block_type, block_index = block_info
                                available_blocks.append(block_data)
                                available_block_info.append(
                                    (disk_idx, block_type, block_index)
                                )

                    # Check if we have enough blocks to reconstruct
                    if len(available_blocks) < num_disks - 1:
                        print(
                            f"❌ Not enough blocks to reconstruct (got {len(available_blocks)}, need {num_disks - 1}), retrying..."
                        )
                        data_incorrect = True
                        continue

                    # XOR all available blocks to reconstruct the missing one
                    reconstructed_block = calculate_parity(available_blocks)

                    # Determine the type and index of the reconstructed block
                    # The missing block is either data or parity
                    parity_position = stripe_index % num_disks
                    reconstructed_index = stripe_index * num_disks + missing_disk_idx
                    if missing_disk_idx == parity_position:
                        reconstructed_type = "parity"
                    else:
                        reconstructed_type = "data"

                    reconstructed_blocks.append(
                        {
                            "block": reconstructed_block,
                            "index": reconstructed_index,
                            "type": reconstructed_type,
                            "stripe_index": stripe_index,
                            "disk": failed_disk,
                            "disk_idx": missing_disk_idx,
                        }
                    )

                    # Add reconstructed block to stripe_blocks for verification
                    stripe_blocks[missing_disk_idx] = (
                        reconstructed_block,
                        reconstructed_type,
                        reconstructed_index,
                    )

                    print(f"✅ Block reconstructed for disk {missing_disk_idx}")

                # Separate parity block from data blocks
                parity_block = None
                data_blocks_dict = {}  # Use dict to track block_index -> block_data

                for disk_idx, block_info in stripe_blocks.items():
                    if block_info is None:
                        print(f"⚠️  Block from disk {disk_idx} is None")
                        continue
                    block_data, block_type, block_index = block_info
                    if block_type == "parity":
                        parity_block = block_data
                    else:
                        data_blocks_dict[block_index] = block_data

                # Sort data blocks by block_index to maintain correct order
                data_blocks = [
                    data_blocks_dict[i] for i in sorted(data_blocks_dict.keys())
                ]

                data_blocks, parity_block = self.simulate_bit_flip(
                    data_blocks, parity_block, reconstruct
                )

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
                    if reconstruct:
                        print(f"   Debug: Reconstructed block may be incorrect")
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

        # After all stripes are read, send reconstructed blocks back to failed disk
        if reconstructed_blocks:
            print(
                f"\n📤 Sending {len(reconstructed_blocks)} reconstructed block(s) to failed disk"
            )
            for rb in reconstructed_blocks:
                print(
                    f"   Sending block {rb['index']} (type={rb['type']}) to {rb['disk'].get('name')}"
                )
                self.send_block(
                    rb["block"],
                    rb["index"],
                    rb["type"],
                    rb["stripe_index"],
                    num_stripes,
                    filename,
                    rb["disk"],
                )
            print("✅ All reconstructed blocks sent")

        return all_stripe_data

    def simulate_bit_flip(self, data_blocks, parity_block, reconstruct):
        """Simulate random bit flip in one of the blocks with 10% chance"""
        # Simulate random bit flip during normal reads (not reconstruction)
        if not reconstruct and random.random() < 0.10:  # 10% chance
            # Pick a random block to corrupt (could be data or parity)
            all_blocks = data_blocks + [parity_block] if parity_block else data_blocks
            corrupt_idx = random.randint(0, len(all_blocks) - 1)
            block_to_corrupt = all_blocks[corrupt_idx]

            # Convert to bytearray to modify
            corrupted_block = bytearray(block_to_corrupt)
            # Pick a random byte and bit position
            byte_pos = random.randint(0, len(corrupted_block) - 1)
            bit_pos = random.randint(0, 7)
            # Flip the bit
            corrupted_block[byte_pos] ^= 1 << bit_pos

            # Replace the block with corrupted version
            if corrupt_idx < len(data_blocks):
                data_blocks[corrupt_idx] = bytes(corrupted_block)
                print(
                    f"🔥 CORRUPTED: Flipped bit {bit_pos} in byte {byte_pos} of data block {corrupt_idx}"
                )
            else:
                parity_block = bytes(corrupted_block)
                print(
                    f"🔥 CORRUPTED: Flipped bit {bit_pos} in byte {byte_pos} of parity block"
                )
        return data_blocks, parity_block

    # thread to read a block from a disk
    def read_block(self, disk, stripe_index, filename, disk_index, result_dict):
        """Read a block from a disk and store result in result_dict"""
        disk_addr = (disk.get("ip"), disk.get("c_port"))
        id = generate_id()
        event = self.events.add_event(id)

        # Send read-block request to disk
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
        # Get read-block response
        response = self.events.get_event_data(id)

        # Check if response came in and status is successful
        if response is None or not check_ok(response, "response", "read-block"):
            print(
                f"❌ Error reading stripe {stripe_index} of file '{filename}' from disk {disk.get('name')}"
            )
            result_dict[disk_index] = None
            return

        # Extract block metadata from response
        data = response.get("data", {})
        block_type = data.get("block-type")
        block_index = data.get("block-index")
        num_chunks = data.get("num-chunks")

        # Use block_index to store chunks
        if filename not in self.files_data:
            self.files_data[filename] = {}

        self.files_data[filename][block_index] = {
            "chunks": [None] * num_chunks,
            "block_type": block_type,
            "block_index": block_index,
        }

        finish_id = generate_id()
        # Send read-chunks request to disk - disk will respond with chunks
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

        # Wait for read-chunks response indicating all chunks sent
        message = self.events.add_event_and_wait(finish_id, timeout=10)

        # Check if response came in and status is successful
        if message is None or not check_ok(message, "response", "read-chunks"):
            print("❌ Read chunks timeout - no response from disk OR error")
            result_dict[disk_index] = None
            return

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
        """Simulate a disk failure in the DSS and reconstruct data"""
        try:
            dss_name = input("Enter DSS name: ")
            id = generate_id()

            # Send disk-failure request to manager
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
            # Wait response from manager with id of request
            message = self.events.add_event_and_wait(id, timeout=5)

            # Check if response came in and status is successful
            if message is None:
                print("❌ Disk failure timeout - no response from manager")
                return

            if not check_ok(message, "response", "disk-failure"):
                print("Disk failure unsuccessful: ", message.get("error"))
                return

            # Get DSS configuration from manager response
            data = message.get("data", {})
            disks = data.get("disks", [])
            striping_unit = data.get("striping_unit")
            num_disks = data.get("num_disks")
            files = data.get("files", [])
            failed_disk = random.choice(disks)

            # Simulate disk failure on the chosen disk
            print(f"\n💥 Failing disk: {failed_disk.get('name')}")
            response = self.fail_disk(failed_disk)
            if not response:
                print("Disk failure unsuccessful during fail_disk call")
                return

            print(f"\n🔧 Starting reconstruction for {len(files)} file(s)...")

            # Reconstruct each file in the DSS
            for file in files:
                filename = file.get("file-name")
                file_size = file.get("file-size")
                print(f"\n📋 Reconstructing file '{filename}' ({file_size} bytes)")

                num_stripes = calculate_num_stripes(file_size, striping_unit, num_disks)

                # Read file with reconstruction enabled
                all_stripe_data = self.read_file_helper(
                    filename,
                    file_size,
                    num_stripes,
                    disks,
                    num_disks,
                    reconstruct=True,
                    failed_disk=failed_disk,
                )

                print(f"✅ File '{filename}' reconstructed successfully")

            id = generate_id()
            # Notify manager that disk failure handling is complete
            send_message(
                self.manager_socket,
                self.manager_address,
                ok_request(
                    "recovery-complete",
                    { "dss-name": dss_name },
                    id=id,
                ),
            )

            response = self.events.add_event_and_wait(id, timeout=5)
            if response is None:
                print("❌ Failure complete timeout - no response from manager")
                return
            if not check_ok(response, "response", "recovery-complete"):
                print("❌ Failure complete unsuccessful: ", response.get("error"))
                return
            print("✅ Disk failure complete")

        except Exception as e:
            print(f"❌ Error during disk failure handling: {e}")
            return

    def fail_disk(self, disk):
        """Send fail command to disk to simulate failure"""
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

        if not check_ok(message, "response", "fail"):
            print("Disk failure unsuccessful: ", message.get("error"))
            return False

        return True

    def ls(self):
        """List files in the DSS"""
        try:
            id = generate_id()
            send_message(
                self.manager_socket,
                self.manager_address,
                ok_request(
                    "ls",
                    {},
                    id=id,
                ),
            )

            # Wait for response from manager
            response = self.events.add_event_and_wait(id, timeout=5)

            # Check if response came in and status is successful
            if response is None:
                print("No list files message recieved from manager")
                return

            if not check_ok(response, "response", "ls"):
                print("Failed to list files : ", response.get("error"))
                return

            data = response.get("data", {})

            # ls-data is a dictionary where keys are DSS names and values are DSS configs
            if isinstance(data, dict):
                for dss_name, dss_config in data.items():
                    # dss_config contains: dss-name, n, disks, striping-unit, files
                    num_disks = dss_config.get("n")
                    striping_unit = dss_config.get("striping-unit")
                    disks_list = dss_config.get("disks", [])
                    files = dss_config.get("files", [])

                    # Handle disks_list being either strings or dicts
                    if disks_list:
                        disk_names = ", ".join(
                            d.get("name", "unknown") if isinstance(d, dict) else str(d)
                            for d in disks_list
                        )
                    else:
                        disk_names = ""

                    if striping_unit is None:
                        su_str = "unknown"
                    else:
                        # Display striping unit in KB (1 KB = 1024 bytes).
                        if isinstance(striping_unit, int) and striping_unit % 1024 == 0:
                            su_str = f"{striping_unit // 1024} KB"
                        else:
                            su_str = f"{striping_unit / 1024:.2f} KB"

                    print(
                        f"{dss_name}: Disk array with n={num_disks} ({disk_names}) with striping-unit {su_str}."
                    )

                    # Print files in this DSS
                    if files:
                        for f in files:
                            if isinstance(f, dict):
                                fname = f.get("file-name", "unknown")
                                fsize = f.get("file-size", 0) or 0
                                owner = f.get("owner", "unknown")
                                print(f"  {fname}       {int(fsize):,} B       {owner}")

            else:
                print("No DSS configurations found")
        except Exception as e:
            print(f"❌ Error listing files: {e}")
            import traceback

            traceback.print_exc()
            return

    def decomission_dss(self):
        """Decomission a DSS"""
        try:
            dss_name = input("Enter DSS name to decommission: ")
            id = generate_id()

            # Send decomission-dss request to manager
            send_message(
                self.manager_socket,
                self.manager_address,
                ok_request(
                    "decomission-dss",
                    {
                        "dss-name": dss_name,
                    },
                    id=id,
                ),
            )
            # Wait response from manager with id of request
            message = self.events.add_event_and_wait(id, timeout=5)

            # Check if response came in and status is successful
            if message is None:
                print("❌ Decomission DSS timeout - no response from manager")
                return

            if not check_ok(message, "response", "decomission-dss"):
                print("Decomission DSS unsuccessful: ", message.get("error"))
                return

            print("Decomission DSS successful")

            id = generate_id()
            # Notify manager that decomissioning is complete
        except Exception as e:
            print(f"❌ Error during decomissioning DSS: {e}")
            return

    # main loop
    def start(self):
        """Start the user process"""
        print(f"🚀 User '{self.name}' started at {self.ip}:{self.m_port}/{self.c_port}")
        # Start the manager port listener thread
        threading.Thread(target=self.handle_manager_port, daemon=True).start()
        # Start the command port listener thread
        threading.Thread(target=self.handle_command_port, daemon=True).start()

        with self.manager_socket, self.command_socket:
            while self.running:
                print_commands()
                command = input("input command: ")
                print("")

                match command:
                    case "exit":
                        self.deregister_user()
                    case "1":
                        self.configure_dss()
                    case "2":
                        self.copy_file()
                    case "3":
                        self.read_file()
                    case "4":
                        self.disk_failure()
                    case "5":
                        self.ls()
                    case "6":
                        self.decomission_dss()
                    case "help":
                        continue
                    case _:
                        print("Unknown Command")

                print("")

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

            # Handle messages
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

            # Check if this is a response to a waiting event
            if self.events.event_exists(id):
                self.events.set_event(id, message)
                continue

            # Handle messages
            match type, action:
                case _:
                    print(f"❌ Unknown message ({type}, {action}) from manager")


def main():
    # Parse command line arguments
    name, ip, m_port, c_port, manager_address = user_command_line_args()

    # Create and start user process
    user = UserProcess(name, ip, m_port, c_port, manager_address)


if __name__ == "__main__":
    main()
