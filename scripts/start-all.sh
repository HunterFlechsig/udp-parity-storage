
#!/usr/bin/env bash
# Clean tmux-based launcher for your Sockets Project

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="sockets_project"

echo "🧹 Cleaning up previous runs..."
pkill -f "python3.*disk.py" 2>/dev/null
pkill -f "python3.*manager.py" 2>/dev/null
pkill -f "python3.*main.py" 2>/dev/null
pkill -f "python3.*user.py" 2>/dev/null
tmux kill-session -t "$SESSION" 2>/dev/null || true

echo "🚀 Starting new tmux session: $SESSION"

# --- Manager window first
tmux new-session -d -s "$SESSION" -n manager -c "$SCRIPT_DIR" \
	"echo 'Running manager.py'; python3 -u manager.py"

# give manager time to bind before other processes
sleep 2

# --- Disks window (pane layout)
tmux new-window -t "$SESSION" -n disks -c "$SCRIPT_DIR" \
	"python3 disk.py -n disk1 -m 31501 -c 31502 -M 127.0.0.1 -P 31500"
tmux split-window -v -t "$SESSION:disks" -c "$SCRIPT_DIR" \
	"python3 disk.py -n disk2 -m 31503 -c 31504 -M 127.0.0.1 -P 31500"
tmux split-window -v -t "$SESSION:disks" -c "$SCRIPT_DIR" \
	"python3 disk.py -n disk3 -m 31505 -c 31506 -M 127.0.0.1 -P 31500"
tmux select-layout -t "$SESSION:disks" tiled

# --- More disks in another window
tmux new-window -t "$SESSION" -n disks2 -c "$SCRIPT_DIR" \
	"python3 disk.py -n disk4 -m 31507 -c 31508 -M 127.0.0.1 -P 31500"
tmux split-window -v -t "$SESSION:disks2" -c "$SCRIPT_DIR" \
	"python3 disk.py -n disk5 -m 31509 -c 31510 -M 127.0.0.1 -P 31500"
tmux split-window -v -t "$SESSION:disks2" -c "$SCRIPT_DIR" \
	"python3 disk.py -n disk6 -m 31511 -c 31512 -M 127.0.0.1 -P 31500"
tmux select-layout -t "$SESSION:disks2" tiled

# --- main.py
tmux new-window -t "$SESSION" -n main -c "$SCRIPT_DIR" \
	"python3 main.py"

# --- user window
tmux new-window -t "$SESSION" -n user -c "$SCRIPT_DIR" \
	"python3 user.py -n user1 -m 31513 -c 31514 -M 127.0.0.1 -P 31500"

# --- attach at the end
tmux select-window -t "$SESSION:manager"
tmux attach -t "$SESSION"
