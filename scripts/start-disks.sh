#!/bin/bash
# Script to start multiple disk processes with automatic port assignment in tmux
# Usage: ./start-disks.sh <starting_port> <disk_name1> <disk_name2> ... [-i disk_ip] [-M manager_ip] [-P manager_port]
# Example: ./start-disks.sh 31501 disk1 disk2 disk3
# Example: ./start-disks.sh 31501 disk1 disk2 -i 192.168.1.100 -M 192.168.1.50 -P 31500

# Default values
DISK_IP="127.0.0.1"
MANAGER_IP="127.0.0.1"
MANAGER_PORT=31500

# Parse arguments
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <starting_port> <disk_name1> <disk_name2> ... [-i disk_ip] [-M manager_ip] [-P manager_port]"
    echo "Example: $0 31501 disk1 disk2 disk3"
    echo "Example: $0 31501 disk1 disk2 -i 192.168.1.100 -M 192.168.1.50 -P 31500"
    echo ""
    echo "Options:"
    echo "  -i    IP address for all disks (default: 127.0.0.1)"
    echo "  -M    Manager IP address (default: 127.0.0.1)"
    echo "  -P    Manager port (default: 31500)"
    exit 1
fi

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "Error: tmux is not installed. Please install it first."
    exit 1
fi

# Get the directory where the script is located and go to parent directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR" || exit 1

# Get starting port
STARTING_PORT=$1
shift  # Remove first argument

# Collect disk names and parse options
DISK_NAMES=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        -i)
            DISK_IP="$2"
            shift 2
            ;;
        -M)
            MANAGER_IP="$2"
            shift 2
            ;;
        -P)
            MANAGER_PORT="$2"
            shift 2
            ;;
        *)
            DISK_NAMES+=("$1")
            shift
            ;;
    esac
done

NUM_DISKS=${#DISK_NAMES[@]}

if [ "$NUM_DISKS" -lt 1 ]; then
    echo "Error: At least one disk name is required"
    exit 1
fi

# Validate port range (31500-31999)
if [ "$STARTING_PORT" -lt 31500 ] || [ "$STARTING_PORT" -gt 31999 ]; then
    echo "Error: Starting port must be between 31500 and 31999"
    exit 1
fi

if [ "$MANAGER_PORT" -lt 31500 ] || [ "$MANAGER_PORT" -gt 31999 ]; then
    echo "Error: Manager port must be between 31500 and 31999"
    exit 1
fi

# Session name
SESSION_NAME="disks-$(date +%s)"

echo "Starting $NUM_DISKS disks in tmux with base port $STARTING_PORT..."
echo "Disk IP: $DISK_IP"
echo "Manager: $MANAGER_IP:$MANAGER_PORT"
echo ""

# Create new tmux session with first disk
DISK_NAME="${DISK_NAMES[0]}"
M_PORT=$((STARTING_PORT))
C_PORT=$((STARTING_PORT + 1))

if [ "$C_PORT" -gt 31999 ]; then
    echo "Error: Port $C_PORT exceeds maximum (31999)"
    exit 1
fi

echo "Creating tmux session with disk: $DISK_NAME (M:$M_PORT, C:$C_PORT)"
tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_DIR" "python3 disk.py -n $DISK_NAME -i $DISK_IP -m $M_PORT -c $C_PORT -M $MANAGER_IP -P $MANAGER_PORT; read -p 'Press enter to close...'"

# Split horizontally for remaining disks
for ((i=1; i<NUM_DISKS; i++)); do
    DISK_NAME="${DISK_NAMES[$i]}"
    PORT_OFFSET=$((i * 2))
    M_PORT=$((STARTING_PORT + PORT_OFFSET))
    C_PORT=$((STARTING_PORT + PORT_OFFSET + 1))
    
    if [ "$C_PORT" -gt 31999 ]; then
        echo "Error: Port $C_PORT exceeds maximum (31999)"
        tmux kill-session -t "$SESSION_NAME"
        exit 1
    fi
    
    echo "Adding disk: $DISK_NAME (M:$M_PORT, C:$C_PORT)"
    tmux split-window -h -t "$SESSION_NAME" -c "$PROJECT_DIR" "python3 disk.py -n $DISK_NAME -i $DISK_IP -m $M_PORT -c $C_PORT -M $MANAGER_IP -P $MANAGER_PORT; read -p 'Press enter to close...'"
    tmux select-layout -t "$SESSION_NAME" even-horizontal
done

# Attach to the session
echo ""
echo "All disks started in tmux session: $SESSION_NAME"
echo "Attaching to tmux session..."
tmux attach-session -t "$SESSION_NAME"
