import subprocess;
import socket;
import json;
import time;
import threading;

HOST = '127.0.0.1';
PORT = 65432;

def start_manager():
    """Start the manager process in a separate thread"""
    print("Starting manager process...");
    subprocess.run(['python', 'manager.py']);

def register_disk(disk_name, ip, m_port, c_port):
    """Register a single disk with the manager"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            data = {
                "type": "register-disk",
                "data": {
                    "disk-name": disk_name,
                    "Ipv4": ip,
                    "m-port": m_port,
                    "c-port": c_port
                }
            }
            s.sendto(json.dumps(data).encode(), (HOST, PORT));
            response_data, addr = s.recvfrom(1024);
            response = json.loads(response_data.decode());
            
            print(f"Disk {disk_name}: {response['status']} - {response['message']}");
            return response['status'] == 'success';
    except Exception as e:
        print(f"Error registering disk {disk_name}: {e}");
        return False;

def main():
    print("=== Starting Distributed Storage System ===");
    
    # Start manager in a separate thread
    manager_thread = threading.Thread(target=start_manager, daemon=True);
    manager_thread.start();
    
    # Wait a moment for manager to start up
    print("Waiting for manager to start...");
    time.sleep(2);
    
    # Register 3 disks
    disks = [
        {"name": "disk1", "ip": "127.0.0.3", "m_port": 65457, "c_port": 65437},
        {"name": "disk2", "ip": "127.0.0.4", "m_port": 65458, "c_port": 65438},
        {"name": "disk3", "ip": "127.0.0.5", "m_port": 65459, "c_port": 65439}
    ];
    
    print("\n=== Registering Disks ===");
    successful_registrations = 0;
    
    for disk in disks:
        success = register_disk(disk["name"], disk["ip"], disk["m_port"], disk["c_port"]);
        if success:
            successful_registrations += 1;
        time.sleep(0.5);  # Small delay between registrations
    
    print(f"\n=== Registration Complete ===");
    print(f"Successfully registered {successful_registrations}/3 disks");
    
    if successful_registrations == 3:
        print("✓ All disks registered successfully!");
    else:
        print("✗ Some disk registrations failed");
    
    print("\nManager is running. Press Ctrl+C to stop.");
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1);
    except KeyboardInterrupt:
        print("\nShutting down...");

if __name__ == "__main__":
    main();
