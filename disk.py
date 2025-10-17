# disk.py
# Hunter Flechsig, 1225292005
# Create a disk process
# Disk process is responsible for the storage of data
# Disk process uses separate threads to manage manager (m) and client (c) ports

import socket
import threading
import sys
from utils import (
    recieve_message,
    disk_command_line_args,
    send_message,
    ok_request,
    ok_response,
    check_ok,
    ThreadEvents,
    generate_id,
    store_chunk,
)


def print_commands():
    print("Disk Commands")
    print("1. deregister        - deregister with manager and exit")


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
        self.register_user()

    def register_user(self):
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

        message, _ = recieve_message(self.manager_socket, 3)

        print(message)

        if message is None:
            print("No register disk message recieved from manager")
            sys.exit(1)

        if not check_ok(message, "response", "register-disk"):
            print("Failed to register disk : ", message.get("error"))
            sys.exit(1)

        print("Disk registered successfully")
        self.start()

    def deregister_disk(self):
        id = generate_id()
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

        message = self.events.add_event_and_wait(id, timeout=5)

        if message is None:
            print("❌ Deregister timeout - no response from manager")
            return

        if not check_ok(message, "response", "deregister-disk"):
            print("deregister unsucessful")
            return

        print("dergister sucessful")
        self.running = False

    def start(self):
        # Start the manager port listener thread
        threading.Thread(target=self.handle_manager_port, daemon=True).start()
        # Start the command port listener thread
        threading.Thread(target=self.handle_command_port, daemon=True).start()

        with self.manager_socket, self.command_socket:
            while self.running:
                print_commands()
                command = input("input command:")

                match command:
                    case "1":
                        self.deregister_disk()
                    case _:
                        print("Unkown Command")

    def handle_manager_port(self):
        """Handle manager port (m_port)"""
        while self.running:
            message, addr = recieve_message(self.manager_socket)
            if message is None:
                continue

            print(message)

            type, action, id = (
                message.get("type"),
                message.get("action"),
                message.get("id"),
            )
            match type, action:
                case "response", "deregister-disk":
                    self.events.set_event(id, message)
                case _:
                    print(f"❌ Unknown message ({type}, {action}) from manager")

    def handle_command_port(self):
        """Handle command port (c_port)"""
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
                case "request", "copy-block":
                    self.handle_copy_block(message, addr)

                case "request", "copy-chunk":
                    self.handle_copy_chunk(message, addr)
                case _:
                    print(f"❌ Unknown message ({type}, {action}) from client")

    def handle_copy_block(self, message, addr):
        """Handle initial copy-block request - sets up for receiving chunks"""
        data = message.get("data")
        filename = data.get("file-name")
        block_index = data.get("block-index")
        block_type = data.get("block-type")
        stripe_index = data.get("stripe-index")
        num_stripes = data.get("num-stripes")
        num_chunks = data.get("num-chunks")
        id = message.get("id")

        # Initialize file storage if needed
        if filename not in self.files_data:
            self.files_data[filename] = {}

        if stripe_index not in self.files_data[filename]:
            self.files_data[filename][stripe_index] = {}

        self.files_data[filename][stripe_index][block_index] = {
            "chunks": [None] * num_chunks,  # Pre-allocate for indexed insertion
            "expected_chunks": num_chunks,
            "metadata": {
                "block_type": block_type,
                "stripe_index": stripe_index,
                "num_stripes": num_stripes,
            },
        }

        # Send immediate response
        response = ok_response("copy-block", {}, id=id)
        send_message(self.command_socket, addr, response)

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


def main():
    name, ip, m_port, c_port, manager_address = disk_command_line_args()
    disk = DiskProcess(name, ip, m_port, c_port, manager_address)
    disk.start()


if __name__ == "__main__":

    main()
