import sys
import getopt
import uuid
import json
import select
import os
import math

chunk_size = 8192  # 8 KB chunk size for sending data

# Return the dictionary mapping disk names to their ports - used for messages
name_dict = {
    31501 or 31502 : "alpha",
    31503 or 31504 : "bravo",
    31505 or 31506 : "charlie",
    31507 or 31508 : "delta",
    31509 or 31510 : "echo",
    31511 or 31512 : "foxtrot",

    31513 or 31514 : "sudo",
    31517 or 31518 : "user",
    31500 : "manager"
}

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

    # Parse command line arguments
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

    # Parse command line arguments
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

    # Validate port ranges

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

    # Parse command line arguments

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

    # create JSON string and encode to bytes
    return json.dumps(message).encode("utf-8")


def ok_request(command, data=None, id=None):
    """ create a successful request message """
    return create_message(command, "request", data=data, status="SUCCESS", id=id)


def error_response(command, error, id=None):
    """ create an error response message """
    return create_message(command, "response", error=error, status="FAILURE", id=id)


def ok_response(command, data=None, id=None):
    """ create a successful response message """
    return create_message(command, "response", data=data, status="SUCCESS", id=id)


def recieve_message(socket, timeout=1):
    """Helper function to receive a message from a socket"""
    data, selected_sockets, errors = select.select([socket], [], [], timeout)
    if not data:
        return None, None
    message, address = socket.recvfrom(32768 * 2)  # 64 KB buffer
    decoded_message = json.loads(message.decode("utf-8"))
    print(
        "📬 Received ",
        (
            decoded_message.get("type"),
            decoded_message.get("action"),
            decoded_message.get("status"),
        ),
        "from ",
        address,
        name_dict.get(address[1], "unknown")
    )
    return decoded_message, address


def send_message(sock, addr, message):
    """Helper function to send a message to a socket"""
    print(
        "📤 Sending",
        (
            json.loads(message.decode("utf-8")).get("type"),
            json.loads(message.decode("utf-8")).get("action"),
            json.loads(message.decode("utf-8")).get("status"),
        ),
        "to",
        name_dict.get(addr[1], "unknown"),
    )
    sock.sendto(message, addr)


def check_ok(message, type, action):
    """ Check if a message is an OK message of the expected type and action """
    if (
        message.get("status") == "SUCCESS"
        and message.get("type") == type
        and message.get("action") == action
    ):
        return True
    return False


import threading
class ThreadEvents:
    """ Class to manage threading events with associated data """
    def __init__(self):
        self.events = {}
        self.data = {}

    def add_event(self, id):
        """ Add a new event with the given id """
        self.events[id] = threading.Event()
        return self.events[id]

    def set_event(self, id, data):
        """ Set the event with the given id and store associated data """
        try:
            self.events[id].set()
            self.data[id] = data
        except KeyError:
            print("Event doesnt exist")

    def get_event_data(self, id):
        """ Get the data associated with an event """
        return self.data.get(id)

    def add_event_and_wait(self, id, timeout=None):
        """
        Add an event and wait for it to be set.
        """
        event = self.add_event(id)
        success = event.wait(timeout)

        if not success:
            # Timeout occurred
            self.events.pop(id, None)  # Clean up
            return None

        return self.get_event_data(id)

    def event_exists(self, id):
        """ Check if an event with the given id exists """
        return id in self.events


def generate_id():
    """ Generate a unique identifier """
    return uuid.uuid4().hex


def check_striping_unit(striping_unit):
    """
    Check if striping unit is a power of two between 128 bytes and 1 MB.
    """
    # Check if it's in the valid range (128 bytes to 1 MB)
    if striping_unit < 128 or striping_unit > 1048576:
        return False

    # Check if it's a power of two
    if striping_unit & (striping_unit - 1) != 0:
        return False

    return True


def print_files_in_directory(directory="./files-copy"):
    """ Print all files in the specified directory """
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


def split_block_into_chunks(block, chunk_size=chunk_size):
    """
    Split a block of data into smaller chunks of specified size.
    """
    return [block[i : i + chunk_size] for i in range(0, len(block), chunk_size)]


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


def calculate_num_chunks(block_size, chunk_size=chunk_size):
    """ Calculate the number of chunks needed for a block of given size """
    return math.ceil(block_size / chunk_size)


def check_parity(blocks, parity_block):
    """
    Check if the parity block matches the calculated parity from data blocks.
    Returns True if parity matches, False otherwise.
    """
    calculated_parity = calculate_parity(blocks)
    return calculated_parity == parity_block


def construct_read_file(directory, filename, stripe_data, file_size):
    """
    Construct a file from stripe data, removing parity blocks and null padding
    """
    # Create directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)

    file_path = os.path.join(directory, filename)

    # Sort all blocks by block_index to get correct order
    all_blocks = []
    for stripe_blocks in stripe_data:
        for block_data, block_type, block_index in stripe_blocks:
            if block_type == "data":  # Skip parity blocks
                all_blocks.append((block_index, block_data))

    # Sort by block_index
    all_blocks.sort(key=lambda x: x[0])

    # Concatenate all data blocks
    full_data = b"".join(block_data for _, block_data in all_blocks)

    # Trim to actual file size (removes null padding)
    actual_data = full_data[:file_size]

    # Write to file
    with open(file_path, "wb") as f:
        f.write(actual_data)

    print(f"✅ File '{filename}' written to {file_path} ({len(actual_data)} bytes)")

    return file_path


def compare_files(original_path, reconstructed_path):
    """
    Compare two files using the diff command.
    """
    import subprocess
    
    try:
        # Run diff command - returns 0 if files are identical, 1 if different, 2 if error
        result = subprocess.run(
            ['diff', '-q', original_path, reconstructed_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ File integrity verified: Files match perfectly")
        elif result.returncode == 1:
            print(f"❌ File integrity check FAILED: Files differ")
            # Run diff again without -q to show the differences
            diff_result = subprocess.run(
                ['diff', '-u', original_path, reconstructed_path],
                capture_output=True,
                text=True
            )
            print(diff_result.stdout)
        else:
            print(f"⚠️  Error running diff: {result.stderr}")
    except FileNotFoundError:
        print(f"⚠️  diff command not found or file does not exist")
    except Exception as e:
        print(f"⚠️  Cannot compare files: {e}")


def check_ok_message(message, expected_type, expected_action):
    """
    Check if a message has status 'ok', and matches expected type and action.

    """
    if (
        not message.get("type") == expected_type
        and not message.get("action") == expected_action
    ):
        return False, "❌ Error: Unexpected message type/action"

    if message.get("status") == "FAILURE":
        return False, message.get("error")

    return True, None

