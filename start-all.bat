@echo off
set SCRIPT_DIR=%~dp0

wt cmd /k "cd /d %SCRIPT_DIR% && python disk.py -n disk1 -m 31501 -c 31502 -M 127.0.0.1 -P 31500" ; ^
   split-pane -V --size 0.67 cmd /k "cd /d %SCRIPT_DIR% && python disk.py -n disk2 -m 31503 -c 31504 -M 127.0.0.1 -P 31500" ; ^
   split-pane -V --size 0.5 cmd /k "cd /d %SCRIPT_DIR% && python disk.py -n disk3 -m 31505 -c 31506 -M 127.0.0.1 -P 31500" ; ^
   new-tab cmd /k "cd /d %SCRIPT_DIR% && python disk.py -n disk4 -m 31507 -c 31508 -M 127.0.0.1 -P 31500" ; ^
   split-pane -V --size 0.67 cmd /k "cd /d %SCRIPT_DIR% && python disk.py -n disk5 -m 31509 -c 31510 -M 127.0.0.1 -P 31500" ; ^
   split-pane -V --size 0.5 cmd /k "cd /d %SCRIPT_DIR% && python disk.py -n disk6 -m 31511 -c 31512 -M 127.0.0.1 -P 31500" ; ^
   new-tab cmd /k "cd /d %SCRIPT_DIR% && python main.py" ; ^
   new-tab cmd /k "cd /d %SCRIPT_DIR% && python -u manager.py" ; ^
   split-pane -V --size 0.5 cmd /k "cd /d %SCRIPT_DIR% && python user.py -n user1 -m 31513 -c 31514 -M 127.0.0.1 -P 31500"

