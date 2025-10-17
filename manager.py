from doctest import debug
import socket
import json
import getopt
import sys
import random
from utils import (
    manager_command_line_args,
    recieve_message,
    send_message,
    error_response,
    ok_response,
    check_striping_unit,
)


class ManagerProcess:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

        self.user_data = {}
        self.disk_data = {}

        self.free_disks = set()
        self.used_ports = set()

        self.dss_data = {}
        self.file_data = {}

        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind((self.ip, self.port))

    def start(self):
        with self.s:
            while True:
                try:
                    message, addr = recieve_message(self.s)
                    if message is None:
                        continue

                    print(f"Received message from {addr}: {message}")
                    # Handle message here

                    type, action = message.get("type"), message.get("action")
                    match type, action:
                        case "request", "register-user":
                            self.handle_register_user(message, addr)
                        case "request", "deregister-user":
                            self.handle_deregister_user(message, addr)
                        case "request", "register-disk":
                            self.handle_register_disk(message, addr)
                        case "request", "deregister-disk":
                            self.handle_deregister_disk(message, addr)
                        case "request", "configure-dss":
                            self.handle_configure_dss(message, addr)
                        case "request", "copy-file":
                            self.handle_copy_file(message, addr)
                        case "request", "read-file":
                            self.handle_read_file(message, addr)
                        case "request", "disk-failure":
                            self.handle_disk_failure(message, addr)
                        case _:
                            print(f"❌ Unknown message ({type}, {action}) from {addr}")
                except Exception as e:
                    print(f"❌ Error handling message from {addr}: {e}")

    def handle_disk_failure(self, message, addr):

        data = message.get("data")
        dss_name = data.get("dss-name")
        id = message.get("id")

        print("Handling disk failure")

        if dss_name not in self.dss_data:
            print("Disk does not exist:", dss_name)
            send_message(
                self.s,
                addr,
                error_response("disk-failure", "dss does not exist", id=id),
            )
            return

        dss_info = self.dss_data[dss_name]
        num_disks = dss_info.get("num_disks")
        striping_unit = dss_info.get("striping_unit")
        disks = dss_info.get("disks")
        disk_info = [self.disk_data[disk] for disk in disks]
        files_dict = dss_info.get("files", {})

        # Build file info list with correct keys for user code
        file_info = []
        for filename, file_data in files_dict.items():
            file_info.append(
                {
                    "file-name": filename,
                    "file-size": file_data.get("size"),
                }
            )

        data = {
            "num_disks": num_disks,
            "striping_unit": striping_unit,
            "disks": disk_info,
            "files": file_info,
        }

        send_message(self.s, addr, ok_response("disk-failure", data, id=id))

    def handle_read_file(self, message, addr):
        data = message.get("data")
        filename = data.get("file-name")
        dss_name = data.get("dss-name")
        owner = data.get("owner")
        id = message.get("id")

        print("Reading file")

        if dss_name not in self.dss_data:
            print("No DSS configured")
            send_message(
                self.s,
                addr,
                error_response("read-file", "No DSS configured", id=id),
            )
            return

        if filename not in self.file_data:
            print("File does not exist:", filename)
            send_message(
                self.s,
                addr,
                error_response("read-file", "File does not exist", id=id),
            )
            return

        if owner not in self.file_data[filename].get("owner", []):
            print("User does not own the file:", owner)
            send_message(
                self.s,
                addr,
                error_response("read-file", "User does not own the file", id=id),
            )
            return

        file_info = self.file_data[filename]
        dss_name = file_info.get("dss")
        disks = file_info.get("disks")
        striping_unit = file_info.get("striping_unit")
        num_disks = file_info.get("num_disks")
        size = file_info.get("size")

        disk_info = [self.disk_data[disk] for disk in disks]

        data = {
            "num_disks": num_disks,
            "striping_unit": striping_unit,
            "disks": disk_info,
            "file-size": size,
        }
        send_message(self.s, addr, ok_response("read-file", data, id=id))

    def handle_copy_file(self, message, addr):
        data = message.get("data")
        owner = data.get("owner")
        filename = data.get("file-name")
        file_size = data.get("file-size")
        id = message.get("id")

        print("Copying file")

        if not self.dss_data:
            print("No DSS configured")
            send_message(
                self.s,
                addr,
                error_response("copy-file", "No DSS configured", id=id),
            )
            return

        if filename in self.file_data:
            print("File already exists:", filename)
            send_message(
                self.s,
                addr,
                error_response("copy-file", "File already exists", id=id),
            )
            return

        dss_name, dss_info = random.choice(list(self.dss_data.items()))
        num_disks = dss_info.get("num_disks")
        striping_unit = dss_info.get("striping_unit")
        disks = dss_info.get("disks")
        disk_info = [self.disk_data[disk] for disk in disks]

        data = {
            "num_disks": num_disks,
            "striping_unit": striping_unit,
            "disks": disk_info,
        }
        send_message(self.s, addr, ok_response("copy-file", data, id=id))

        while True:
            message, addr = recieve_message(self.s, timeout=5)
            if message is None:
                continue
            if (
                message.get("type") == "response"
                and message.get("action") == "copy-complete"
            ):
                break
            else:
                send_message(
                    self.s,
                    addr,
                    error_response(
                        message.get("action"),
                        "No operations during copy-file",
                        id=message.get("id"),
                    ),
                )
            print("File copy complete")

        self.file_data[filename] = {
            "dss": dss_name,
            "disks": disks,
            "striping_unit": striping_unit,
            "num_disks": num_disks,
            "size": file_size,
            "owner": owner,  # Store owner as a list
        }
        dss_info["files"][filename] = self.file_data[filename]

        send_message(self.s, addr, ok_response("copy-file", {}, id=id))

    def handle_configure_dss(self, message, addr):
        data = message.get("data")
        name = data.get("name")
        num_disks = data.get("num_disks")
        striping_unit = data.get("striping_unit")
        id = message.get("id")

        print("Configuring DSS")

        if len(self.free_disks) < num_disks:
            print("not enough disks to configure dss")
            send_message(
                self.s, addr, error_response("configure-dss", "not enough disks", id=id)
            )
            return

        if not check_striping_unit(striping_unit):
            print("striping unit not valid")
            send_message(
                self.s,
                addr,
                error_response("configure-dss", "striping unit not valid", id=id),
            )
            return

        if name in self.dss_data:
            print("dss name already exists")
            send_message(
                self.s,
                addr,
                error_response("configure-dss", "dss name already exists", id=id),
            )
            return

        selected_disks = random.sample(list(self.free_disks), num_disks)
        self.free_disks.difference_update(selected_disks)
        self.dss_data[name] = {
            "disks": selected_disks,
            "striping_unit": striping_unit,
            "num_disks": num_disks,
            "files": {},
        }
        send_message(self.s, addr, ok_response("configure-dss", {}, id=id))

    def handle_register_disk(self, message, addr):
        data = message.get("data")
        name = data.get("name")
        c_port = data.get("c_port")
        m_port = data.get("m_port")
        id = message.get("id")

        print("Registing disk")

        if name in self.disk_data:
            print("Disk already exists:", name)
            send_message(
                self.s,
                addr,
                error_response("register-disk", "Disk already exists", id=id),
            )
            return

        if m_port in self.used_ports or c_port in self.used_ports:
            print("One of the ports is already registered as in use")
            send_message(
                self.s,
                addr,
                error_response(
                    "register-disk", "One of the ports is already in use", id=id
                ),
            )
            return

        self.disk_data[name] = data
        self.used_ports.add(c_port)
        self.used_ports.add(m_port)
        self.free_disks.add(name)
        send_message(self.s, addr, ok_response("register-disk", {}, id=id))

    def handle_deregister_disk(self, message, addr):
        data = message.get("data")
        name = data.get("name")
        id = message.get("id")

        print("De-Registering disk")

        if name not in self.disk_data:
            print("Disk doesnt exists:", name)
            send_message(
                self.s,
                addr,
                error_response("deregister-disk", "Disk doesnt exist", id=id),
            )
            return

        if name not in self.free_disks:
            print("Disk is currently in use:", name)
            send_message(
                self.s,
                addr,
                error_response("deregister-disk", "Disk is currently in use", id=id),
            )
            return

        disk = self.disk_data.pop(name)
        self.used_ports.remove(disk.get("c_port"))
        self.used_ports.remove(disk.get("m_port"))
        self.free_disks.remove(name)
        send_message(self.s, addr, ok_response("deregister-disk", {}, id=id))
        print("de-register successfuly")

    def handle_register_user(self, message, addr):
        data = message.get("data")
        name = data.get("name")
        c_port = data.get("c_port")
        m_port = data.get("m_port")
        id = message.get("id")

        print("Registing user")

        if name in self.user_data:
            print("User already exists:", name)
            send_message(
                self.s,
                addr,
                error_response("register-user", "User already exists", id=id),
            )
            return

        if m_port in self.used_ports or c_port in self.used_ports:
            print("One of the ports is already registered as in use")
            send_message(
                self.s,
                addr,
                error_response(
                    "register-user", "One of the ports is already in use", id=id
                ),
            )
            return

        self.user_data[name] = data
        self.used_ports.add(c_port)
        self.used_ports.add(m_port)
        send_message(self.s, addr, ok_response("register-user", {}, id=id))

    def handle_deregister_user(self, message, addr):
        data = message.get("data")
        name = data.get("name")
        id = message.get("id")

        print("De-Registering user")

        if name not in self.user_data:
            print("User doesnt exists:", name)
            send_message(
                self.s,
                addr,
                error_response("deregister-user", "User doesnt exist", id=id),
            )
            return

        user = self.user_data.pop(name)
        self.used_ports.remove(user.get("c_port"))
        self.used_ports.remove(user.get("m_port"))
        send_message(self.s, addr, ok_response("deregister-user", {}, id=id))
        print("de-register successfuly")


def main():
    ip, port = manager_command_line_args()
    manager = ManagerProcess(ip, port)
    manager.start()


if __name__ == "__main__":
    main()
