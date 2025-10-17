from doctest import debug
import socket
import json
import getopt
import sys
import random


class ManagerProcess:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.blocked = False
        self.blocked_data = {}

        self.user_data = {}
        self.disk_data = {}
        self.free_disks = []
        self.dss_data = {}
        self.file_data = {}
        self.used_ports = set()
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start(self):
        """Start the manager process"""
        print(f"Starting manager process on {self.ip}:{self.port}")
        print(f"Listening on {self.ip}:{self.port}")
        print(f"Port range: 31500-31999")
        print("=" * 20)

        # Bind the socket to the IP and port provided
        with self.s:
            self.s.bind((self.ip, self.port))

            try:
                while True:
                    try:
                        # Set timeout to allow checking self.running
                        data = None
                        self.s.settimeout(1.0)
                        data, addr = self.s.recvfrom(1024)
                        message = json.loads(data.decode())
                        print(f"Manager received from {addr[0]}:{addr[1]}")

                        # Process manager messages
                        if data:
                            self.process_message(message, addr)

                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"❌ Manager port error: {e}")
            except KeyboardInterrupt:
                print("\nCtrl+C pressed, shutting down manager...")
                print("Manager stopped cleanly")

    def process_message(self, message, addr):
        """Process messages received"""
        print(f"Processing message of type {message.get('type', 'Unknown type')}")
        try:
            if self.blocked and message.get("type") != "copy-complete":
                self.send_response(
                    message.get("type"), "Copying in progress", addr, "failure"
                )
                return

            match message.get("type"):
                case "register-user":
                    self.register_user(message, addr)
                case "deregister-user":
                    self.deregister_user(message, addr)
                case "register-disk":
                    self.register_disk(message, addr)
                case "deregister-disk":
                    self.deregister_disk(message, addr)
                case "configure-dss":
                    self.configure_dss(message, addr)
                case "copy":
                    self.copy(message, addr)
                case "copy-complete":
                    self.copy_complete(message, addr)
                case "read":
                    self.read(message, addr)
                case "ls":
                    self.ls(message, addr)
                case "disk-failure":
                    self.disk_failure(message, addr)
                case _:
                    print(f"unknown message type")
                    self.send_response(
                        message.get("type"), "Unknown message type", addr, "failure"
                    )
        except Exception as e:
            print(f"❌ Error processing manager message: {e}")
            self.send_response(
                message.get("type"),
                "Error processing manager message: " + str(e),
                addr,
                "failure",
            )

    # ---------------------------------------------------------------

    def disk_failure(self, message, addr):
        """Handle disk failure"""
        try:
            data = message.get("data", {})
            dss_name = data.get("dss-name")

            if dss_name not in self.dss_data:
                self.send_response("disk-failure-res", "DSS not found", addr, "failure")
                return

            # choose dss
            dss_name = random.choice(list(self.dss_data.keys()))
            dss_data = self.dss_data.get(dss_name)
            res_data = {
                "dss-name": dss_name,
                "n": dss_data.get("n"),
                "striping-unit": dss_data.get("striping-unit"),
                "disks": [
                    {
                        "disk-name": self.disk_data[disk_name].get("disk-name"),
                        "Ipv4": self.disk_data[disk_name].get("Ipv4"),
                        "c-port": self.disk_data[disk_name].get("c-port"),
                    }
                    for disk_name in dss_data.get("disks", [])
                ],
            }
            self.send_response(
                "disk-failure-res", "Disk failure handled", addr, "success", res_data
            )

        except Exception as e:
            print(f"❌ Error handling disk failure: {e}")
            self.send_response(
                "disk-failure-res",
                "Error handling disk failure: " + str(e),
                addr,
                "failure",
            )

    def ls(self, message, addr):
        """List all dss, and their files"""
        try:
            data = {
                dss_name: list(dss_info.get("files", {}).keys())
                for dss_name, dss_info in self.dss_data.items()
            }
            self.send_response("ls-res", "Listing all data", addr, "success", data)
        except Exception as e:
            print(f"❌ Error listing data: {e}")
            self.send_response("ls", "Error listing data: " + str(e), addr, "failure")

    def copy_complete(self, message, addr):
        """Copy complete"""

        dss_data = self.dss_data.get(self.blocked_data.get("dss-name"))
        dss_data.get("files")[self.blocked_data.get("file-data").get("file-name")] = (
            self.blocked_data.get("file-data")
        )

        self.blocked = False
        self.send_response("copy-complete", "Copy complete", addr, "success")

    def read(self, message, addr):
        try:
            data = message.get("data")
            dss_name = data.get("dss-name")
            file_name = data.get("file-name")
            user_name = data.get("user-name")

            if dss_name not in self.dss_data:
                print(f"❌ DSS not found: {dss_name}")
                self.send_response("read", "DSS not found", addr, "failure")
                return

            if file_name not in self.dss_data[dss_name]["files"]:
                print(f"❌ File not found: {file_name}")
                self.send_response("read", "File not found", addr, "failure")
                return

            print(self.dss_data)
            if user_name not in self.dss_data[dss_name]["files"][file_name]["owner"]:
                print(f"❌ User not found: {user_name}")
                self.send_response(
                    "read", "User not owner of requested file", addr, "failure"
                )
                return

            read_data = {
                "file-name": file_name,
                "file-size": self.dss_data[dss_name]["files"][file_name]["file-size"],
                "dss-name": dss_name,
                "n": self.dss_data[dss_name]["n"],
                "striping-unit": self.dss_data[dss_name]["striping-unit"],
                "disks": [
                    {
                        "disk-name": self.disk_data[disk_name].get("disk-name"),
                        "Ipv4": self.disk_data[disk_name].get("Ipv4"),
                        "c-port": self.disk_data[disk_name].get("c-port"),
                    }
                    for disk_name in self.dss_data[dss_name].get("disks", [])
                ],
            }

            self.send_response("read", "File found", addr, "success", read_data)
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            self.send_response("read", "Error reading file: " + str(e), addr, "failure")

    def configure_dss(self, message, addr):
        """Configure a DSS"""
        try:
            # check if DSS already exists
            if message.get("data", {}).get("dss-name") in self.dss_data:
                print(
                    f"❌ DSS already exists: {message.get('data', {}).get('dss-name')}"
                )
                self.send_response(
                    "configure-dss", "DSS already exists", addr, "failure"
                )
                return

            # check if n and striping-unit are numbers
            try:
                n = (int)(message.get("data").get("n"))
                striping_unit = (int)(message.get("data").get("striping-unit"))
            except:
                print(
                    f"❌ Invalid n: {message.get('data').get('n')} (must be a number)"
                )
                self.send_response(
                    "configure-dss",
                    "Invalid n or striping-unit type: must be a number",
                    addr,
                    "failure",
                )
                return

            # check number of free disks
            if len(self.free_disks) < n:
                print(f"❌ Not enough free disks to configure the DSS")
                self.send_response(
                    "configure-dss",
                    "Not enough free disks to configure the DSS",
                    addr,
                    "failure",
                )
                return

            # check if n is a number and a valid number
            if n < 3:
                print(
                    f"❌ Invalid n: {message.get('data').get('n')} (must be greater than 2 and a number)"
                )
                self.send_response(
                    "configure-dss",
                    "Invalid n: "
                    + str(message.get("data").get("n"))
                    + " (must be greater than 2 and a number)",
                    addr,
                    "failure",
                )
                return

            # check if striping-unit is a power of 2 between 128 and 1048576 bytes
            if (
                striping_unit < 128
                or striping_unit > 1048576
                or striping_unit & (striping_unit - 1) != 0
            ):
                print(
                    f"❌ Invalid striping-unit: {message.get('data').get('striping-unit')} (must be a power of 2 between 128 and 1048576 bytes)"
                )
                self.send_response(
                    "configure-dss",
                    "Invalid striping-unit: "
                    + str(message.get("data").get("striping-unit"))
                    + " (must be a power of 2 between 128 and 1048576 bytes)",
                    addr,
                    "failure",
                )
                return

            # add DSS data
            self.dss_data[message.get("data").get("dss-name")] = {
                "disks": [],
                "files": {},
                "striping-unit": striping_unit,
                "n": n,
            }

            # pop n disks from the free disks
            for _ in range(n):
                disk_name = self.free_disks.pop(0)
                self.disk_data[disk_name]["inDSS"] = True
                self.dss_data[message.get("data").get("dss-name")]["disks"].append(
                    disk_name
                )

            # send response to DSS's m-port
            print(
                f"✅ DSS {message.get('data').get('dss-name')} configured successfully"
            )
            self.send_response(
                "configure-dss", "DSS configured successfully", addr, "success"
            )

        except Exception as e:
            print(f"❌ Error configuring DSS: {e}")
            self.send_response(
                "configure-dss", "Error configuring DSS: " + str(e), addr, "failure"
            )

    def register_user(self, message, addr):
        """Register a user"""
        try:
            # check if user already exists
            if message.get("data", {}).get("user-name") in self.user_data:
                print(
                    f"❌ User already exists: {message.get('data', {}).get('user-name')}"
                )
                self.send_response(
                    "register-user", "User already exists", addr, "failure"
                )
                return

            # check if port is already in use
            ports = [
                message.get("data", {}).get("m-port"),
                message.get("data", {}).get("c-port"),
            ]
            for port in ports:
                if port in self.used_ports:
                    print(f"❌ Port already in use: {port}")
                    self.send_response(
                        "register-user",
                        "One of the ports is already in use",
                        addr,
                        "failure",
                    )
                    return

            # Add user data and track ports
            user_data = message.get("data", {})
            self.user_data[user_data.get("user-name")] = user_data
            self.used_ports.add(user_data.get("m-port"))
            self.used_ports.add(user_data.get("c-port"))

            print(
                f"✅ User {message.get('data', {}).get('user-name')} registered successfully"
            )
            self.send_response(
                "register-user", "User registered successfully", addr, "success"
            )
        except Exception as e:
            print(f"❌ Error registering user: {e}")
            self.send_response(
                "register-user", "Error registering user: " + str(e), addr, "failure"
            )

    def deregister_user(self, message, addr):
        """Deregister a user"""
        try:
            user_name = message.get("data", {}).get("user-name")

            if user_name not in self.user_data:
                print(f"❌ User {user_name} not found")
                self.send_response(
                    "deregister-user", f"User {user_name} not found", addr, "failure"
                )
                return

            # Remove user and free up ports
            user_data = self.user_data[user_name]

            self.used_ports.discard(user_data.get("m-port"))
            self.used_ports.discard(user_data.get("c-port"))
            self.user_data.pop(user_name)

            # send response to user's m-port
            print(f"✅ User {user_name} deregistered successfully")
            self.send_response(
                "deregister-user", "User deregistered successfully", addr, "success"
            )
        except Exception as e:
            print(f"❌ Error deregistering user: {e}")
            self.send_response(
                "deregister-user",
                "Error deregistering user: " + str(e),
                addr,
                "failure",
            )

    def register_disk(self, message, addr):
        """Register a disk"""
        try:
            # check if disk already exists
            if message.get("data", {}).get("disk-name") in self.disk_data:
                print(
                    f"❌ Disk already exists: {message.get('data', {}).get('disk-name')}"
                )
                self.send_response(
                    "register-disk", "Disk already exists", addr, "failure"
                )
                return

            # check if port is already in use
            ports = [
                message.get("data", {}).get("m-port"),
                message.get("data", {}).get("c-port"),
            ]
            for port in ports:
                if port in self.used_ports:
                    print(f"❌ Port already in use: {port}")
                    self.send_response(
                        "register-disk",
                        "One of the ports is already in use",
                        addr,
                        "failure",
                    )
                    return

            # add disk data and track ports
            disk_data = message.get("data", {})
            self.disk_data[disk_data.get("disk-name")] = disk_data
            self.used_ports.add(disk_data.get("m-port"))
            self.used_ports.add(disk_data.get("c-port"))
            self.free_disks.append(disk_data.get("disk-name"))

            # send response to disk's m-port
            print(
                f"✅ Disk {message.get('data', {}).get('disk-name')} registered successfully"
            )
            self.send_response(
                "register-disk", "Disk registered successfully", addr, "success"
            )
        except Exception as e:
            print(f"❌ Error registering disk: {e}")
            self.send_response(
                "register-disk", "Error registering disk: " + str(e), addr, "failure"
            )

    def deregister_disk(self, message, addr):
        """Deregister a disk"""
        try:

            disk_name = message.get("data", {}).get("disk-name")
            if disk_name not in self.disk_data:
                print(f"❌ Disk {disk_name} not found")
                self.send_response(
                    "deregister-disk", f"Disk {disk_name} not found", addr, "failure"
                )
                return

            if disk_name not in self.free_disks:
                print(f"❌ Disk {disk_name} not in free disks")
                self.send_response(
                    "deregister-disk",
                    f"Disk {disk_name} is being used in a DSS",
                    addr,
                    "failure",
                )
                return

            # remove disk data and track ports
            self.disk_data.pop(disk_name)
            self.used_ports.discard(message.get("data", {}).get("m-port"))
            self.used_ports.discard(message.get("data", {}).get("c-port"))
            self.free_disks.remove(disk_name)

            print(f"✅ Disk {disk_name} deregistered successfully")
            self.send_response(
                "deregister-disk", "Disk deregistered successfully", addr, "success"
            )
        except Exception as e:
            print(f"❌ Error deregistering disk: {e}")
            self.send_response(
                "deregister-disk",
                "Error deregistering disk: " + str(e),
                addr,
                "failure",
            )

    def copy(self, message, addr):
        """Copy a file to the DSS"""
        try:

            # choose dss
            if len(self.dss_data) == 0:
                print(f"❌ No DSSs available")
                self.send_response("copy", "No DSSs available", addr, "failure")
                return

            # choose dss
            dss_name = random.choice(list(self.dss_data.keys()))
            dss_data = self.dss_data.get(dss_name)
            res_data = {
                "dss-name": dss_name,
                "n": dss_data.get("n"),
                "striping-unit": dss_data.get("striping-unit"),
                "disks": [
                    {
                        "disk-name": self.disk_data[disk_name].get("disk-name"),
                        "Ipv4": self.disk_data[disk_name].get("Ipv4"),
                        "c-port": self.disk_data[disk_name].get("c-port"),
                    }
                    for disk_name in dss_data.get("disks", [])
                ],
                **message.get("data", {}),
            }
            self.send_response("copy", "DSS chosen", addr, "success", res_data)
            self.blocked = True
            self.blocked_data["file-data"] = message.get("data", {})
            self.blocked_data["dss-name"] = dss_name

        except Exception as e:
            print(f"❌ Error copying file: {e}")
            self.send_response("copy", "Error copying file: " + str(e), addr, "failure")

    # ---------------------------------------------------------------

    def send_response(self, type, message_text, addr, status, data={}):
        """Send a response to process"""
        response = {
            "type": type,
            "data": {
                "status": status,
                "message": (
                    "✅ " + message_text
                    if status == "success"
                    else "❌ " + message_text
                ),
                "data": data,
            },
        }
        print(f"Sending response to {addr[0]}:{addr[1]}")
        # print(f"   Response: {json.dumps(response, indent=2)}")
        print("=" * 20)
        self.s.sendto(json.dumps(response).encode(), addr)


def main():
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

    manager = ManagerProcess(ip, port)
    manager.start()


if __name__ == "__main__":
    main()
