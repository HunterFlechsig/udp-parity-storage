# disk.py
# Hunter Flechsig, 1225292005
# Create a disk process
# Disk process is responsible for the storage of data
# Disk process uses separate threads to manage manager (m) and client (c) ports

from email.mime import message
import socket
import threading
import sys
import random
from utils import (
    recieve_message,
    disk_command_line_args,
    send_message,
    ok_request,
    ok_response,
    error_response,
    check_ok,
    ThreadEvents,
    generate_id,
)
from time import sleep


def print_commands():
    print("Disk Commands")
    print("--- ---")
    print("exit. deregister     - deregister with manager and exit")
    print("help.                - print this help message")
    print("--- ---")

# DiskProcess class for managing disk operations
class DiskProcess:
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
        self.register_disk()

    def register_disk(self):
        """ Register disk with manager """
        # Send register-disk request to manager
        print ("Registering disk with manager...")
        send_message(
            self.manager_socket,
            self.manager_address,
            ok_request(
                "register-disk",
                {
                    "name": self.name,
                    "ip": self.ip,
                    "c_port": self.c_port,
                    "m_port": self.m_port,
                },
            ),
        )

        # Wait for register-disk response from manager
        message, _ = recieve_message(self.manager_socket, 3)

        if message is None:
            print("No register disk message recieved from manager")
            sys.exit(1)

        if not check_ok(message, "response", "register-disk"):
            print("Failed to register disk : ", message.get("error"))
            sys.exit(1)

        print("Disk registered successfully \n")
        self.start()

    def deregister_disk(self):
        """ Deregister disk with manager """
        print("Deregistering disk with manager...")
        id = generate_id()
        # Send deregister-disk request to manager
        send_message(
            self.manager_socket,
            self.manager_address,
            ok_request(
                "deregister-disk",
                {
                    "name": self.name,
                },
                id=id,
            ),
        )

        # Wait for deregister-disk response from manager
        message = self.events.add_event_and_wait(id, timeout=5)

        # Check response
        if message is None:
            print("❌ Deregister timeout - no response from manager")
            return

        if not check_ok(message, "response", "deregister-disk"):
            print("Deregister unsuccessful : ", message.get("error"))
            return


        print("Deregister successful")
        self.running = False

    def start(self):
        """ start disk process """

        # Start the manager port listener thread
        threading.Thread(target=self.handle_manager_port, daemon=True).start()
        # Start the command port listener thread
        threading.Thread(target=self.handle_command_port, daemon=True).start()

        # Main loop for user commands
        with self.manager_socket, self.command_socket:
            while self.running:
                command = input("input command:")

                match command:
                    case "exit":
                        self.deregister_disk()
                    case "help":
                        print_commands()
                    case _:
                        print("Unknown Command")
                        print_commands()

    def handle_manager_port(self):
        """Handle manager port (m_port)"""
        # Listen for messages from the manager
        while self.running:
            message, addr = recieve_message(self.manager_socket)
            if message is None:
                continue

            type, action, id = (
                message.get("type"),
                message.get("action"),
                message.get("id"),
            )
            # handle messages
            match type, action:
                case "response", "deregister-disk":
                    self.events.set_event(id, message)
                case "request", "decomission-disk":
                    self.handle_decomission_disk(message, addr)
                case _:
                    print(f"❌ Unknown message ({type}, {action}) from manager")

            if message:
                print(" ")

    def handle_command_port(self):
        """Handle command port (c_port)"""

        # Listen for messages from clients
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

            # handle messages
            match type, action:
                case "request", "copy-block":
                    self.handle_copy_block(message, addr)
                case "request", "copy-chunk":
                    self.handle_store_chunk(message, addr)
                case "request", "read-block":
                    self.handle_read_block(message, addr)
                case "request", "read-chunks":
                    self.handle_read_chunks(message, addr)
                case "request", "fail":
                    self.handle_fail_disk(message, addr)
                case _:
                    print(f"❌ Unknown message ({type}, {action}) from client")

            if message:
                print(" ")

    def handle_decomission_disk(self, message, addr):
        """Handle decomission-disk request"""
        id = message.get("id")
        print(f"🗑️  Decomissioning disk - clearing all files")

        # Simulate disk decomission by clearing the file's data
        self.files_data = {}

        response = ok_response(
            "decomission-disk",
            {},
            id=id,
        )
        # Send response back to manager
        send_message(self.manager_socket, addr, response)

    def handle_fail_disk(self, message, addr):
        """Handle fail-disk request"""
        id = message.get("id")
        print(f"💥 Simulating disk failure - clearing all files")

        # Simulate disk failure by clearing the file's data
        self.files_data = {}

        # Send response back to requester
        response = ok_response(
            "fail",
            {},
            id=id,
        )
        send_message(self.command_socket, addr, response)

    def handle_read_block(self, message, addr):
        """Handle read-block request"""
        data = message.get("data")
        filename = data.get("file-name")
        stripe_index = data.get("stripe-index")
        id = message.get("id")

        # Check if file exists (could be missing due to disk failure)
        if filename not in self.files_data or stripe_index not in self.files_data.get(
            filename, {}
        ):
            print(
                f"⚠️  Cannot read block - file '{filename}' stripe {stripe_index} not found (disk may have failed)"
            )
            response = error_response(
                "read-block",
                f"File '{filename}' stripe {stripe_index} not found",
                id=id,
            )
            send_message(self.command_socket, addr, response)
            return

        # Send block info response
        block_info = self.files_data[filename][stripe_index]
        response = ok_response(
            "read-block",
            {
                "block-type": block_info["block_type"],
                "num-chunks": len(block_info["chunks"]),
                "file-name": filename,
                "block-index": block_info["block_index"],
            },
            id=id,
        )
        send_message(self.command_socket, addr, response)

    def handle_read_chunks(self, message, addr):
        """Handle read-chunks request - send all chunks for a block"""
        data = message.get("data")
        filename = data.get("file-name")
        stripe_index = data.get("stripe-index")
        block_index = data.get("block-index")
        finish_id = data.get("finish-id")

        
        block_info = self.files_data[filename][stripe_index]

        print(
            f"📤 Sending {len(block_info['chunks'])} chunks for stripe {stripe_index}"
        )

        # Send each chunk individually
        for chunk_index, chunk_data in enumerate(block_info["chunks"]):
            chunk_response = ok_response(
                "read-chunk",
                {
                    "file-name": filename,
                    "block-index": block_index,  # Echo back block_index so user knows where to store
                    "chunk-index": chunk_index,
                    "chunk-data": list(chunk_data),
                    "finish-id": finish_id,
                },
                id=generate_id(),
            )
            send_message(self.command_socket, addr, chunk_response)

        # Send finish notification
        finish_response = ok_response(
            "read-chunks",
            {},
            id=finish_id,
        )
        send_message(self.command_socket, addr, finish_response)
        print(f"✅ Sent all chunks for stripe {stripe_index}")

    def handle_copy_block(self, message, addr):
        """Handle initial copy-block request - sets up for receiving chunks"""
        data = message.get("data")
        filename = data.get("file-name")
        block_index = data.get("block-index")
        block_type = data.get("block-type")
        stripe_index = data.get("stripe-index")
        num_chunks = data.get("num-chunks")
        id = message.get("id")

        print(
            f"📦 Received copy-block: file={filename}, stripe={stripe_index}, block={block_index}, type={block_type}, chunks={num_chunks}"
        )

        # Initialize file storage if needed
        if filename not in self.files_data:
            self.files_data[filename] = {}

        # Initialize stripe storage if needed
        if stripe_index not in self.files_data[filename]:
            self.files_data[filename][stripe_index] = {}

        # Set up storage for chunks
        self.files_data[filename][stripe_index] = {
            "chunks": [None] * num_chunks,
            "block_type": block_type,
            "block_index": block_index,
            "stripe_index": stripe_index,
        }

        print(f"✅ Initialized storage for {num_chunks} chunks")

        response = ok_response("copy-block", {}, id=id)
        send_message(self.command_socket, addr, response)

    def handle_store_chunk(self, message, addr):
        """Handle store-chunk request"""
        data = message.get("data")
        filename = data.get("file-name")
        stripe_index = data.get("stripe-index")
        chunk_index = data.get("chunk-index")
        chunk_data = data.get("chunk-data")

        # Store the chunk data
        self.files_data[filename][stripe_index]["chunks"][chunk_index] = bytes(
            chunk_data
        )

        # Count how many chunks have been received
        total_chunks = len(self.files_data[filename][stripe_index]["chunks"])
        received_chunks = sum(
            1
            for c in self.files_data[filename][stripe_index]["chunks"]
            if c is not None
        )

        print(
            f"📥 Chunk {chunk_index} received for stripe {stripe_index} ({received_chunks}/{total_chunks} chunks complete)"
        )


def main():
    name, ip, m_port, c_port, manager_address = disk_command_line_args()
    disk = DiskProcess(name, ip, m_port, c_port, manager_address)
    disk.start()


if __name__ == "__main__":

    main()
