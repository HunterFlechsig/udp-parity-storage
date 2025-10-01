#!/usr/bin/env python3
"""
main.py
Hunter Flechsig, 1225292005
Main script to start 3 disk processes
"""

import subprocess
import sys
import time
import signal
import os
from multiprocessing import Process

def start_disk(disk_name, m_port, c_port, manager_ip="127.0.0.1", manager_port=31500):
    """Start a single disk process"""
    try:
        print(f"🚀 Starting disk {disk_name} on ports {m_port} (manager) and {c_port} (client)")
        
        # Start the disk process
        process = subprocess.Popen([
            sys.executable, "disk.py",
            "-n", disk_name,
            "-i", "127.0.0.1",
            "-m", str(m_port),
            "-c", str(c_port),
            "-M", manager_ip,
            "-P", str(manager_port)
        ])
        
        return process
    except Exception as e:
        print(f"❌ Error starting disk {disk_name}: {e}")
        return None

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n⚠️  Ctrl+C pressed. Shutting down all disk processes...")
    sys.exit(0)

def main():
    """Main function to start 3 disk processes"""
    print("=" * 60)
    print("🖥️  Starting 3 Disk Processes")
    print("=" * 60)
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Configuration for 3 disks
    disks_config = [
        {"name": "disk1", "m_port": 31501, "c_port": 31502},
        {"name": "disk2", "m_port": 31503, "c_port": 31504},
        {"name": "disk3", "m_port": 31505, "c_port": 31506}
    ]
    
    manager_ip = "127.0.0.1"
    manager_port = 31500
    
    # Start all disk processes
    processes = []
    for disk_config in disks_config:
        process = start_disk(
            disk_config["name"],
            disk_config["m_port"],
            disk_config["c_port"],
            manager_ip,
            manager_port
        )
        if process:
            processes.append(process)
            time.sleep(0.5)  # Small delay between starting processes
    
    if not processes:
        print("❌ Failed to start any disk processes")
        sys.exit(1)
    
    print(f"\n✅ Successfully started {len(processes)} disk processes")
    print("=" * 60)
    print("Disk Configuration:")
    for i, disk_config in enumerate(disks_config, 1):
        print(f"  Disk {i}: {disk_config['name']} - Manager: {disk_config['m_port']}, Client: {disk_config['c_port']}")
    print(f"Manager: {manager_ip}:{manager_port}")
    print("=" * 60)
    print("Press Ctrl+C to stop all disk processes")
    print("=" * 60)
    
    try:
        # Wait for all processes to complete
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        print("\n⚠️  Shutting down all disk processes...")
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("✅ All disk processes stopped")

if __name__ == "__main__":
    main()
