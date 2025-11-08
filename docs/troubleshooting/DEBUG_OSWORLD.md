# OSWorld Debugging Guide

Quick reference for debugging OSWorld issues in the SSH session.

> **Status:** Legacy (Xvfb/Openbox) environment.  
> For GNOME-based native images (`setup_osworld_gnome_v3.sh`), replace `xvfb`/`openbox` with `gdm` and adjust commands accordingly (e.g., `sudo systemctl status gdm osworld-server`).

## Quick Health Check

```bash
# One-liner to check everything
sudo systemctl status xvfb openbox osworld-server && curl -s http://localhost:5000/platform && echo "✓ All systems operational"
```

---

## Service Status

### Check all services
```bash
sudo systemctl status xvfb
sudo systemctl status openbox
sudo systemctl status osworld-server
```

### View logs
```bash
# Recent logs
sudo journalctl -u osworld-server -n 50 --no-pager

# Follow logs in real-time
sudo journalctl -u osworld-server -f

# Logs for all OSWorld services
sudo journalctl -u xvfb -u openbox -u osworld-server -n 100 --no-pager
```

### Restart services
```bash
# Restart in order
sudo systemctl restart xvfb
sleep 2
sudo systemctl restart openbox
sleep 2
sudo systemctl restart osworld-server

# Check status after restart
sleep 3
sudo systemctl status osworld-server
```

---

## Network / Port Issues

### Check if port 5000 is listening
```bash
sudo lsof -i :5000
sudo netstat -tulpn | grep 5000
```

### Test connectivity
```bash
# Test from localhost
curl -v http://localhost:5000/platform

# Test from VM's IP (if accessing remotely)
curl -v http://$(hostname -I | awk '{print $1}'):5000/platform
```

### Check firewall rules (GCP)
```bash
# On local machine
gcloud compute firewall-rules list --filter="name~osworld"

# Create firewall rule if needed (WARNING: restricts to your IP only)
# gcloud compute firewall-rules create osworld-server \
#   --allow tcp:5000 \
#   --source-ranges=$(curl -s ifconfig.me)/32
```

---

## Process Debugging

### Check if processes are running
```bash
# Check Xvfb
ps aux | grep Xvfb

# Check Openbox
ps aux | grep openbox

# Check OSWorld server
ps aux | grep "desktop_env.server.main"

# All at once
pgrep -a "Xvfb|openbox|desktop_env"
```

### Kill stuck processes
```bash
# Kill OSWorld server (systemd will restart it)
sudo pkill -f "desktop_env.server.main"

# Kill all and restart
sudo pkill -f Xvfb
sudo pkill -f openbox
sudo pkill -f "desktop_env.server.main"
sleep 2
sudo systemctl restart xvfb openbox osworld-server
```

---

## Display (X11) Issues

### Check if display :99 is available
```bash
DISPLAY=:99 xdpyinfo | head -20
```

### Test screenshot manually
```bash
DISPLAY=:99 import -window root /tmp/manual_screenshot.png
ls -lh /tmp/manual_screenshot.png
```

### Check X11 permissions
```bash
ls -la /opt/osworld/.Xauthority
sudo -u osworld bash -c 'DISPLAY=:99 xdpyinfo' | head -5
```

---

## Python Environment

### Check Python packages
```bash
python3 -c "import flask; print('flask:', flask.__version__)"
python3 -c "import pyautogui; print('pyautogui:', pyautogui.__version__)"
python3 -c "import pyatspi; print('pyatspi: OK')"
python3 -c "from Xlib import display; print('Xlib: OK')"
```

### Check PYTHONPATH
```bash
sudo -u osworld bash -c 'echo $PYTHONPATH'
```

### Test OSWorld imports
```bash
sudo -u osworld bash -c '
cd /opt/osworld
export DISPLAY=:99
export PYTHONPATH=/opt/osworld:/opt/osworld/desktop_env/server
python3 -c "from desktop_env.server.main import app; print(\"OSWorld imports OK\")"
'
```

---

## Manual Server Start

### Run server manually (for debugging)
```bash
# Stop systemd service first
sudo systemctl stop osworld-server

# Run manually to see errors
sudo -u osworld bash -c '
cd /opt/osworld
export DISPLAY=:99
export PYTHONPATH=/opt/osworld:/opt/osworld/desktop_env/server
export XAUTHORITY=/opt/osworld/.Xauthority
python3 -m desktop_env.server.main --port 5000
'
```

Press Ctrl+C to stop, then restart the service:
```bash
sudo systemctl start osworld-server
```

---

## API Testing

### Test endpoints manually
```bash
# Screenshot
curl http://localhost:5000/screenshot -o /tmp/test.png && ls -lh /tmp/test.png

# Platform
curl http://localhost:5000/platform

# Execute command
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command": ["whoami"]}'

# Cursor position
curl http://localhost:5000/cursor_position

# Screen size
curl -X POST http://localhost:5000/screen_size \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Application Testing

### Test Chrome
```bash
# Check Chrome is installed
google-chrome --version

# Test Chrome with display
DISPLAY=:99 google-chrome --version

# Launch Chrome (will run in background)
DISPLAY=:99 google-chrome --new-window https://google.com &

# Check if Chrome is running
pgrep -a chrome
```

### Test other apps
```bash
DISPLAY=:99 firefox --version
DISPLAY=:99 gedit --version
```

---

## File Permissions

### Check OSWorld directory permissions
```bash
ls -la /opt/osworld/
ls -la /opt/osworld/desktop_env/
ls -la /opt/osworld/desktop_env/server/
```

### Fix permissions if needed
```bash
sudo chown -R osworld:osworld /opt/osworld
sudo chmod 755 /opt/osworld
```

---

## Disk Space

### Check available space
```bash
df -h
du -sh /opt/osworld
du -sh /var/log
```

### Clean up if needed
```bash
# Clean old logs
sudo journalctl --vacuum-time=1d

# Clean apt cache
sudo apt-get clean

# Check Docker (if still using)
docker system df
```

---

## Complete Reset

### Nuclear option - restart everything
```bash
# Stop all services
sudo systemctl stop osworld-server openbox xvfb

# Kill any stuck processes
sudo pkill -f Xvfb
sudo pkill -f openbox
sudo pkill -f chrome
sudo pkill -f "desktop_env"

# Clean temp files
sudo rm -f /tmp/.X99-lock
sudo rm -f /opt/osworld/logs/*

# Start services in order
sudo systemctl start xvfb
sleep 2
sudo systemctl start openbox
sleep 2
sudo systemctl start osworld-server
sleep 3

# Verify
sudo systemctl status osworld-server
curl http://localhost:5000/platform
```

---

## Common Error Messages

### "list index out of range"
This usually means wrong API parameters. Check your JSON request format.

### "Connection refused"
Server not running or wrong port. Check `sudo systemctl status osworld-server`

### "No module named 'X'"
Missing Python dependency. Run:
```bash
sudo bash fix_osworld_dependencies.sh
sudo bash fix_tkinter.sh
```

### "Cannot open display :99"
Xvfb not running or wrong DISPLAY variable.
```bash
sudo systemctl restart xvfb
DISPLAY=:99 xdpyinfo
```

### "Permission denied"
Wrong user or file permissions.
```bash
sudo chown -R osworld:osworld /opt/osworld
```

---

## Getting Help

### Collect debug info
```bash
# Save all relevant info to a file
{
  echo "=== Service Status ==="
  sudo systemctl status xvfb openbox osworld-server
  echo ""
  echo "=== Recent Logs ==="
  sudo journalctl -u osworld-server -n 50 --no-pager
  echo ""
  echo "=== Processes ==="
  ps aux | grep -E "Xvfb|openbox|desktop_env|chrome"
  echo ""
  echo "=== Network ==="
  sudo lsof -i :5000
  echo ""
  echo "=== Display ==="
  DISPLAY=:99 xdpyinfo | head -20
} > /tmp/osworld_debug.txt

cat /tmp/osworld_debug.txt
```

Share this output for diagnosis.

---

## Useful Aliases

Add these to `~/.bashrc` for quick debugging:

```bash
alias osw-status='sudo systemctl status xvfb openbox osworld-server'
alias osw-logs='sudo journalctl -u osworld-server -f'
alias osw-restart='sudo systemctl restart xvfb && sleep 2 && sudo systemctl restart openbox && sleep 2 && sudo systemctl restart osworld-server'
alias osw-test='curl http://localhost:5000/platform && curl -s http://localhost:5000/screenshot -o /tmp/test.png && ls -lh /tmp/test.png'
```

Then use:
```bash
osw-status   # Check status
osw-logs     # Watch logs
osw-restart  # Restart everything
osw-test     # Quick test
```
