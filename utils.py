import sys
import getopt
import uuid
import json
import select
import os
import math


def user_command_line_args():
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
    return name, ip, m_port, c_port, manager_address


def manager_command_line_args():
    """Main function to parse command line arguments and start the manager process"""

    ip = "127.0.0.1"
    port = 31500

    args = sys.argv[1:]
    options = "hi:p:h"

    try:
        arguments, values = getopt.getopt(args, options)
        for currentArg, currentVal in arguments:
            if currentArg in ("-h", "--help"):
                print(
                    "Manager Process Help \n"
                    " -i: IP address to bind the manager to (default: 127.0.0.1) \n"
                    " -p: Port number to bind the manager to (default: 31500) \n"
                )
                sys.exit(0)
    except getopt.error as err:
        print(str(err))
        sys.exit(1)

    if ip is None or port is None:
        print("❌ Error: Missing required arguments:")
        sys.exit(1)

    if not (31500 <= port <= 31999):
        print(f"❌ Error: Port {port} must be in range 31500-31999")
        sys.exit(1)
    return ip, port


def disk_command_line_args():
    """Main function to parse command line arguments and start the disk process"""

    name = None
    ip = "127.0.0.1"
    m_port = 31501
    c_port = 31502
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
                    "Disk Process Help \n"
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
        print(
            f"❌ Error: manager-port {manager_port} must be in range {ports[0]}-{ports[1]}"
        )
        sys.exit(1)

    if name is None or ip is None or m_port is None or c_port is None:
        print("❌ Error: Missing a required argument")
        sys.exit(1)

    manager_address = (manager_ip, manager_port)
    return name, ip, m_port, c_port, manager_address


# message format
# {
#   "command": <command>,
#   "type": <type> # request/response/ack,
#   "status": <status>, # ok/error
#   "data": <data>,
#   "error": <error>
#   "id" : <id>
# }
def create_message(command, type, data=None, error=None, status=None, id=None):
    """Helper function to create a JSON message"""
    message = {
        "action": command,
        "type": type,
    }
    if error is not None:
        message["error"] = error
    if status is not None:
        message["status"] = status
    if data is not None:
        message["data"] = data
    if id is not None:
        message["id"] = id
    else:
        message["id"] = uuid.uuid4().hex

    return json.dumps(message).encode("utf-8")


def ok_request(command, data=None, id=None):
    return create_message(command, "request", data=data, status="ok", id=id)


def error_response(command, error, id=None):
    return create_message(command, "response", error=error, status="error", id=id)


def ok_response(command, data=None, id=None):
    return create_message(command, "response", data=data, status="ok", id=id)


def recieve_message(socket, timeout=1):
    """Helper function to receive a message from a socket"""
    data, selected_sockets, errors = select.select([socket], [], [], timeout)
    if not data:
        return None, None
    message, address = socket.recvfrom(1048576 * 2)  # 2 MB buffer
    return json.loads(message.decode("utf-8")), address


def send_message(sock, addr, message):
    """Helper function to send a message to a socket"""
    sock.sendto(message, addr)


def check_ok(message, type, action):
    if (
        message.get("status") == "ok"
        and message.get("type") == type
        and message.get("action") == action
    ):
        return True
    return False


import threading


class ThreadEvents:
    def __init__(self):
        self.events = {}
        self.data = {}

    def add_event(self, id):
        self.events[id] = threading.Event()
        return self.events[id]

    def set_event(self, id, data):
        try:
            self.events[id].set()
            self.data[id] = data
        except:
            print("Event doesnt exist")

    def get_event_data(self, id):
        return self.data.get(id)

    def add_event_and_wait(self, id, timeout=None):
        """
        Add an event and wait for it to be set.

        Args:
            id: Event identifier
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            Event data if received, None if timeout
        """
        event = self.add_event(id)
        success = event.wait(timeout)

        if not success:
            # Timeout occurred
            self.events.pop(id, None)  # Clean up
            return None

        return self.get_event_data(id)

    def event_exists(self, id):
        return id in self.events


def generate_id():
    return uuid.uuid4().hex


def check_striping_unit(striping_unit):
    """
    Check if striping unit is a power of two between 128 bytes and 1 MB.
    """
    # Check if it's in the valid range (128 bytes to 1 MB)
    if striping_unit < 128 or striping_unit > 1048576:  # 1 MB = 1024 * 1024
        return False

    # Check if it's a power of two
    # A number is a power of two if it has only one bit set
    # This can be checked by: n & (n-1) == 0
    if striping_unit & (striping_unit - 1) != 0:
        return False

    return True


def print_files_in_directory(directory="./files-copy"):
    print("files:")
    print("--- ---")
    for f in os.listdir(directory):
        print(f)
    print("--- ---")


def read_blocks_from_file(file_path, block_size):
    """
    Read blocks of data from a file, yielding one block at a time.
    Automatically null-pads the last block if it's smaller than block_size.
    """
    with open(file_path, "rb") as f:
        while True:
            block = f.read(block_size)
            if not block:
                break

            # Null-pad if block is smaller than block_size
            if len(block) < block_size:
                block = block.ljust(block_size, b"\x00")

            yield block


def calculate_num_stripes(file_size, striping_unit, num_disks):
    """
    Calculate the number of stripes needed to store a file.
    Takes into account that one disk per stripe is used for parity (RAID-4).
    """
    # Only (num_disks - 1) disks hold data per stripe, one holds parity
    data_blocks_per_stripe = num_disks - 1
    bytes_per_stripe = striping_unit * data_blocks_per_stripe

    num_stripes = math.ceil(file_size / bytes_per_stripe)

    return num_stripes


def split_block_into_chunks(block, chunk_size=2048):
    """
    Split a block of data into smaller chunks of specified size.
    """
    return [block[i : i + chunk_size] for i in range(0, len(block), chunk_size)]


def send_block():
    pass


def calculate_parity(blocks):
    """
    Calculate the parity block for a list of data blocks using XOR.
    Assumes all blocks are of the same length.
    """
    parity = bytearray(blocks[0])  # Start with the first block

    for block in blocks[1:]:
        for i in range(len(parity)):
            parity[i] ^= block[i]  # XOR each byte

    return bytes(parity)


def store_chunk(
    files_data, filename, stripe_index, block_index, chunk_index, chunk_data
):
    """
    Store a chunk of data in the files_data structure.

    Args:
        files_data: Dictionary storing file data [filename][stripe_index][block_index]
        filename: Name of the file
        stripe_index: Index of the stripe
        block_index: Index of the block within the stripe
        chunk_index: Index of the chunk within the block
        chunk_data: The actual chunk data (list or bytes)

    Returns:
        True if chunk was stored successfully, False if block doesn't exist
    """
    # Store the chunk
    if (
        filename in files_data
        and stripe_index in files_data[filename]
        and block_index in files_data[filename][stripe_index]
    ):
        block_info = files_data[filename][stripe_index][block_index]
        block_info["chunks"][chunk_index] = bytes(chunk_data)
        return True
    else:
        return False


def calculate_num_chunks(block_size, chunk_size=2048):
    return math.ceil(block_size / chunk_size)
