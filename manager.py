from doctest import debug
import socket
import json
import getopt
import sys
import random
import threading
from utils import (
    manager_command_line_args,
    recieve_message,
    send_message,
    error_response,
    ok_response,
    check_striping_unit,
    ok_request,
    check_ok_message
)

def print_commands():
    print("Manager Commands - type at any time")
    print("--- ---")
    print("help. help              - show this help message")
    print("exit. exit              - exit the manager process")
    print("--- ---")


# ManagerProcess class for managing manager operations
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
        self.running = True


    def start(self):
        """ Start the manager process """
        print(f"🚀 Manager started at {self.ip}:{self.port}")
        threading.Thread(target=self.command_thread, daemon=True).start() # Start command thread

        with self.s:
            # Listen for incoming messages
            while self.running:
                try:
                    message, addr = recieve_message(self.s)
                    if message is None:
                        continue
                    
                    # Handle messages
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
                        case "request", "ls":
                            self.handle_ls(message, addr)
                        case "request", "decomission-dss":
                            self.handle_decomission_dss(message, addr)
                        case "response", "read-complete":
                            self.handle_read_complete(message, addr)
                        case _:
                            print(f"❌ Unknown message ({type}, {action}) from {addr}")

                    if message: print("")  # Print a newline for better readability


                except Exception as e:
                    print(f"❌ Error handling message from {addr}: {e}")

    def command_thread(self):
        """ Thread for handling manager commands """
        while self.running:
            try:
                command = input("Manager Command> ").strip()
                match command:
                    case "help":
                        print_commands()
                    case "exit":
                        self.running = False
                    case _:
                        print("❌ Unknown command:", command)
                        print_commands()
            except Exception as e:
                print(f"❌ Error handling command: {e}")

    def handle_read_complete(self, message, addr):
        """ Handle read complete notification from user """
        dss_name = message.get("data").get("dss-name")
        if dss_name in self.dss_data:
            self.dss_data[dss_name]["users_reading"] = max(0, self.dss_data[dss_name].get("users_reading") - 1)
        print("User read complete. Current reading users:", self.dss_data[dss_name].get("users_reading"))
        message_id = message.get("id")
        send_message(self.s, addr, ok_response("read-complete", {}, id=message_id))

    def handle_decomission_dss(self, message, addr):
        """ Handle decomission dss request from user """
        data = message.get("data")
        dss_name = data.get("dss-name")
        id = message.get("id")

        # Save the original user address
        user_addr = addr

        print("Handling decomission-dss")

        # Check if DSS exists
        if dss_name not in self.dss_data:
            print("❌ Error DSS does not exist:", dss_name)
            send_message(
                self.s,
                user_addr,
                error_response("decomission-dss", "DSS does not exist", id=id),
            )
            return
        
        # Check if DSS being read
        if self.dss_data[dss_name].get("users_reading") > 0:
            print("Cannot decomission DSS while users are reading")
            send_message(
                self.s,
                user_addr,
                error_response("decomission-dss", "Cannot decomission DSS while users are reading", id=id),
            )
            return

        # remove disks from DSS
        dss_info = self.dss_data.pop(dss_name)
        disks = dss_info.get("disks", [])

        print("Removing disks from DSS:", disks)
        # Notify each disk to decomission
        for disk in disks:
            disk_info = self.disk_data.get(disk, {})
            disk_address = (disk_info.get("ip"), disk_info.get("m_port"))

            send_message(
                self.s, disk_address, ok_request("decomission-disk", {}, id=id)
            )

            while True:
                # Wait for response from disk
                disk_msg, disk_addr = recieve_message(self.s, timeout=5)
                if disk_msg is None:
                    continue
                
                # keep waiting until we get the correct response
                print("Received message during decomission-dss:", disk_msg)
                if (
                    check_ok_message(disk_msg, "response", "decomission-disk")
                ):
                    break
                else:
                    send_message(
                        self.s,
                        disk_addr,
                        error_response(
                            disk_msg.get("action"),
                            "No operations during decomission-dss",
                        ),
                    )

            # Add disk back to free disks
            self.free_disks.add(disk)

        # Remove files associated with this DSS
        files_dict = dss_info.get("files", {})
        for filename in files_dict.keys():
            if filename in self.file_data:
                self.file_data.pop(filename)

        print("DSS decomissioned successfully")

        send_message(self.s, user_addr, ok_response("decomission-dss", {}, id=id))

    def handle_ls(self, message, addr):
        """ Handle ls request from user """
        id = message.get("id")

        print("Handling ls")

        dss_files = {}
        for dss_name, dss_info in self.dss_data.items():
            num_disks = dss_info.get("num_disks")
            striping_unit = dss_info.get("striping_unit")
            disks = dss_info.get("disks", [])

            # Build file info list
            files_list = []
            for fname, fmeta in dss_info.get("files", {}).items():
                files_list.append(
                    {
                        "file-name": fname,
                        "file-size": fmeta.get("size"),
                        "owner": fmeta.get("owner"),
                    }
                )

            dss_files[dss_name] = {
                "dss-name": dss_name,
                "n": num_disks,
                "disks": disks,
                "striping-unit": striping_unit,
                "files": files_list,
            }

        print("LS request processed successfully")
        send_message(self.s, addr, ok_response("ls", dss_files, id=id))

    def handle_disk_failure(self, message, addr):
        """ Handle disk failure request from user """
        data = message.get("data")
        dss_name = data.get("dss-name")
        id = message.get("id")

        print("Handling disk failure")

        # Check if DSS exists
        if dss_name not in self.dss_data:
            print("Disk does not exist:", dss_name)
            send_message(
                self.s,
                addr,
                error_response("disk-failure", "dss does not exist", id=id),
            )
            return
        
        # check if DSS being read
        if self.dss_data[dss_name].get("users_reading") > 0:
            print("Cannot report simulate failure while users are reading")
            send_message(
                self.s,
                addr,
                error_response("disk-failure", "Cannot simulate disk failure while users are reading", id=id),
            )
            return

        # Gather DSS information
        dss_info = self.dss_data[dss_name]
        num_disks = dss_info.get("num_disks")
        striping_unit = dss_info.get("striping_unit")
        disks = dss_info.get("disks")
        disk_info = [self.disk_data[disk] for disk in disks]
        files_dict = dss_info.get("files", {})

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

        print("Disk failure request processed successfully")
        # Send response back to user
        send_message(self.s, addr, ok_response("disk-failure", data, id=id))

        while True:
            # Wait for disk-failure-complete response
            message, addr = recieve_message(self.s, timeout=5)
            if message is None:
                continue
            if (
                message.get("type") == "request"
                and message.get("action") == "recovery-complete"
            ):
                id = message.get("id")
                break
            else:
                send_message(
                    self.s,
                    addr,
                    error_response(
                        message.get("action"),
                        "No operations during disk-failure",
                        id=message.get("id"),
                    ),
                )
        
        print("Disk failure handling complete")      

        send_message(self.s, addr, ok_response("recovery-complete", {}, id=id))



    def handle_read_file(self, message, addr):
        """ Handle read file request from user """
        try: 
            data = message.get("data")
            filename = data.get("file-name")
            dss_name = data.get("dss-name")
            owner = data.get("owner")
            id = message.get("id")

            print("Reading file")

            # Check if DSS exists
            if dss_name not in self.dss_data:
                print("No DSS configured")
                send_message(
                    self.s,
                    addr,
                    error_response("read-file", "No DSS configured", id=id),
                )
                return

            # Check if file exists
            if filename not in self.file_data:
                print("File does not exist:", filename)
                send_message(
                    self.s,
                    addr,
                    error_response("read-file", "File does not exist", id=id),
                )
                return

            # Check if user is owner of the file
            if owner not in self.file_data[filename].get("owner", []):
                print("User does not own the file:", owner)
                send_message(
                    self.s,
                    addr,
                    error_response("read-file", "User does not own the file", id=id),
                )
                return

            # Gather file information
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
            print("Read file request processed successfully")
            # Send response back to user
            self.dss_data[dss_name]["users_reading"] = self.dss_data[dss_name].get("users_reading") + 1
            send_message(self.s, addr, ok_response("read-file", data, id=id))

        except Exception as e:
            print(f"❌ Error handling read-file: {e}")

    
    def handle_copy_file(self, message, addr):
        """ Handle copy file request from user """
        data = message.get("data")
        owner = data.get("owner")
        filename = data.get("file-name")
        file_size = data.get("file-size")
        id = message.get("id")

        print("Copying file")

        # Check if DSS exists
        if not self.dss_data:
            print("No DSS configured")
            send_message(
                self.s,
                addr,
                error_response("copy-file", "No DSS configured", id=id),
            )
            return

        # Check if file already exists
        if filename in self.file_data:
            print("File already exists:", filename)
            send_message(
                self.s,
                addr,
                error_response("copy-file", "File already exists", id=id),
            )
            return

        # Select a DSS to store the file - gather DSS info
        dss_name, dss_info = random.choice(list(self.dss_data.items()))

        # Check if DSS being read
        if self.dss_data[dss_name].get("users_reading") > 0:
            print("Cannot copy file while users are reading")
            send_message(
                self.s,
                addr,
                error_response("copy-file", "Cannot copy file while users are reading", id=id),
            )
            return

        num_disks = dss_info.get("num_disks")
        striping_unit = dss_info.get("striping_unit")
        disks = dss_info.get("disks")
        disk_info = [self.disk_data[disk] for disk in disks]

        data = {
            "num_disks": num_disks,
            "striping_unit": striping_unit,
            "disks": disk_info,
        }
        print("Selected DSS for file storage:", dss_name)
        # Send response back to user with DSS info
        send_message(self.s, addr, ok_response("copy-file", data, id=id))

        print("Waiting for copy-complete confirmation from user")
        # Wait for copy-complete confirmation
        while True:
            message, addr = recieve_message(self.s, timeout=5)
            if message is None:
                continue
            if (
                message.get("type") == "request"
                and message.get("action") == "copy-complete"
            ):
                id = message.get("id")
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

        # Store file information
        self.file_data[filename] = {
            "dss": dss_name,
            "disks": disks,
            "striping_unit": striping_unit,
            "num_disks": num_disks,
            "size": file_size,
            "owner": owner,  # Store owner as a list
        }
        dss_info["files"][filename] = self.file_data[filename]

        send_message(self.s, addr, ok_response("copy-complete", {}, id=id))

    def handle_configure_dss(self, message, addr):
        """ Handle configure dss request from user """
        data = message.get("data")
        name = data.get("name")
        num_disks = data.get("num_disks")
        striping_unit = data.get("striping_unit")
        id = message.get("id")

        print("handling configure-dss")

        # check available disks
        if len(self.free_disks) < num_disks:
            print("not enough disks to configure dss")
            send_message(
                self.s, addr, error_response("configure-dss", "not enough disks", id=id)
            )
            return
        
        # Check if DSS name length is valid
        if len(name.strip()) >= 15 or len(name.strip()) == 0:
            print("DSS name length invalid:", name)
            send_message(
                self.s,
                addr,
                error_response("configure-dss", "DSS name length invalid: must be between 1 and 15 characters", id=id),
            )
            return

        # check striping unit validity
        if not check_striping_unit(striping_unit):
            print("striping unit not valid")
            send_message(
                self.s,
                addr,
                error_response("configure-dss", "striping unit not valid", id=id),
            )
            return

        # check if dss name already exists
        if name in self.dss_data:
            print("dss name already exists")
            send_message(
                self.s,
                addr,
                error_response("configure-dss", "dss name already exists", id=id),
            )
            return

        # select disks for the DSS
        selected_disks = random.sample(list(self.free_disks), num_disks)
        for disk in selected_disks:
            self.disk_data[disk]["state"] = "in-use"
        self.free_disks.difference_update(selected_disks)
        self.dss_data[name] = {
            "disks": selected_disks,
            "striping_unit": striping_unit,
            "num_disks": num_disks,
            "files": {},
            "users_reading": 0,
        }
        print(f"DSS configured: name={name}, disks={selected_disks}, striping_unit={striping_unit}, num_disks={num_disks}")
        # send success response
        send_message(self.s, addr, ok_response("configure-dss", {}, id=id))

    def handle_register_disk(self, message, addr):
        """ Handle register disk request from disk """
        data = message.get("data")
        name = data.get("name")
        c_port = data.get("c_port")
        m_port = data.get("m_port")
        id = message.get("id")

        print("handling register disk")

        # Check if disk already exists
        if name in self.disk_data:
            print("Disk already exists:", name)
            send_message(
                self.s,
                addr,
                error_response("register-disk", "Disk already exists", id=id),
            )
            return
        
        # Check if name length is valid
        if len(name.strip()) >= 15 or len(name.strip()) == 0:
            print("Disk name length invalid:", name)
            send_message(
                self.s,
                addr,
                error_response("register-disk", "Disk name length invalid: must be between 1 and 15 characters", id=id),
            )
            return

        # Check if ports are already in use
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

        # Register the disk
        self.disk_data[name] = {**data, "state": "free"}
        self.used_ports.add(c_port)
        self.used_ports.add(m_port)
        self.free_disks.add(name)
        print(f"Disk registered: name={name}, c_port={c_port}, m_port={m_port}")
        send_message(self.s, addr, ok_response("register-disk", {}, id=id))

    def handle_deregister_disk(self, message, addr):
        """ Handle deregister disk request from disk """
        data = message.get("data")
        name = data.get("name")
        id = message.get("id")

        print("handling deregister disk")

        # Check if disk exists
        if name not in self.disk_data:
            print("Disk doesnt exists:", name)
            send_message(
                self.s,
                addr,
                error_response("deregister-disk", "Disk doesnt exist", id=id),
            )
            return
 
        # Check if disk is in use in DSS
        if name not in self.free_disks:
            print("Disk is currently in use:", name)
            send_message(
                self.s,
                addr,
                error_response("deregister-disk", "Disk is currently in use", id=id),
            )
            return

        # Deregister the disk
        disk = self.disk_data.pop(name)
        self.used_ports.remove(disk.get("c_port"))
        self.used_ports.remove(disk.get("m_port"))
        self.free_disks.remove(name)
        send_message(self.s, addr, ok_response("deregister-disk", {}, id=id))
        print(f"Disk {name} deregistered successfully")

    def handle_register_user(self, message, addr):
        data = message.get("data")
        name = data.get("name")
        c_port = data.get("c_port")
        m_port = data.get("m_port")
        id = message.get("id")

        print("handling register user")

        # Check if user already exists
        if name in self.user_data:
            print("User already exists:", name)
            send_message(
                self.s,
                addr,
                error_response("register-user", "User already exists", id=id),
            )
            return
        
        # Check user name length
        if len(name.strip()) >= 15 or len(name.strip()) == 0:
            print("User name length invalid:", name)
            send_message(
                self.s,
                addr,
                error_response("register-user", "User name length invalid: must be between 1 and 15 characters", id=id),
            )
            return
        
        # Check if ports are already in use
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

        # Register the user
        self.user_data[name] = data
        self.used_ports.add(c_port)
        self.used_ports.add(m_port)
        print(f"User registered: name={name}, c_port={c_port}, m_port={m_port}")
        # Send success response
        send_message(self.s, addr, ok_response("register-user", {}, id=id))

    def handle_deregister_user(self, message, addr):
        data = message.get("data")
        name = data.get("name")
        id = message.get("id")

        print("handling deregister user")

        # Check if user exists
        if name not in self.user_data:
            print("User doesnt exists:", name)
            send_message(
                self.s,
                addr,
                error_response("deregister-user", "User doesnt exist", id=id),
            )
            return

        # Deregister the user
        user = self.user_data.pop(name)
        self.used_ports.remove(user.get("c_port"))
        self.used_ports.remove(user.get("m_port"))
        send_message(self.s, addr, ok_response("deregister-user", {}, id=id))
        print(f"User {name} deregistered successfully")


def main():
    ip, port = manager_command_line_args()
    manager = ManagerProcess(ip, port)
    manager.start()


if __name__ == "__main__":
    main()
