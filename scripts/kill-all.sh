#!/bin/bash
# Kill all processes using ports in the range 31500-31999

echo "🔍 Finding processes using ports 31500-31999..."

# Loop through the port range and kill any processes using them
for port in {31500..31999}; do
    # Find PIDs using this port
    pids=$(lsof -ti :$port 2>/dev/null)
    
    if [ ! -z "$pids" ]; then
        echo "🔪 Killing process(es) on port $port: $pids"
        kill -9 $pids 2>/dev/null
    fi
done

echo "✅ All processes on ports 31500-31999 have been killed"
