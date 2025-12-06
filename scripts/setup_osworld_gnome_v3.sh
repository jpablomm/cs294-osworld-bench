#!/bin/bash
#
# OSWorld Native Setup - GNOME Desktop (v3 - With Scrot Patch)
# Sets up a production-ready OSWorld environment with full GNOME desktop
#

set -e

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "========================================"
log "OSWorld Native Setup - GNOME Desktop v3"
log "========================================"

# Update system
log "Updating system packages..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Install GNOME Desktop (minimal)
log "Installing GNOME Desktop..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ubuntu-desktop-minimal \
    gdm3 \
    gnome-shell \
    nautilus \
    gnome-terminal \
    gnome-system-monitor

# Install required software
log "Installing required software..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python3-tk \
    python3-dev \
    curl \
    wget \
    vim \
    htop \
    x11vnc \
    novnc \
    scrot \
    xdotool \
    wmctrl \
    at-spi2-core \
    python3-pyatspi \
    xserver-xorg-video-dummy \
    dbus-x11

# Install Chrome
log "Installing Google Chrome..."
if [ ! -f /usr/bin/google-chrome ]; then
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb
    DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/chrome.deb || true
    rm /tmp/chrome.deb
fi

# Install LibreOffice
log "Installing LibreOffice..."
DEBIAN_FRONTEND=noninteractive apt-get install -y libreoffice

# Install GIMP
log "Installing GIMP..."
DEBIAN_FRONTEND=noninteractive apt-get install -y gimp

# Create user 'user' with password 'password'
log "Creating user 'user'..."
if ! id user &>/dev/null; then
    # Try to create with UID 1000, fallback to auto-assign if taken
    if ! id 1000 &>/dev/null; then
        useradd -m -s /bin/bash -u 1000 user
    else
        log "UID 1000 already taken, creating user with auto-assigned UID"
        useradd -m -s /bin/bash user
    fi
    echo "user:password" | chpasswd
    usermod -aG sudo user
    log "✓ User 'user' created"
else
    log "✓ User 'user' already exists"
fi

USER_UID=$(id -u user)
USER_GID=$(id -g user)
log "User 'user' has UID=$USER_UID, GID=$USER_GID"

# Clone OSWorld repository
log "Cloning OSWorld repository..."
if [ ! -d /home/user/osworld ]; then
    sudo -u user git clone https://github.com/xlang-ai/OSWorld.git /home/user/osworld
    log "✓ OSWorld repository cloned"
else
    log "✓ OSWorld repository already exists"
fi

# Apply scrot patch to main.py
log "Applying scrot patch to OSWorld screenshot function..."
cat > /tmp/patch_screenshot.py << 'PATCHEOF'
import sys

# Read the file
with open('/home/user/osworld/desktop_env/server/main.py', 'r') as f:
    content = f.read()

# Patch 1: Replace Linux screenshot code with scrot
old_linux_code = '''    elif user_platform == "Linux":
        cursor_obj = Xcursor()
        imgarray = cursor_obj.getCursorImageArrayFast()
        cursor_img = Image.fromarray(imgarray)
        screenshot = pyautogui.screenshot()
        cursor_x, cursor_y = pyautogui.position()
        screenshot.paste(cursor_img, (cursor_x, cursor_y), cursor_img)
        screenshot.save(file_path)'''

new_linux_code = '''    elif user_platform == "Linux":
        # Use scrot instead of pyautogui since PIL ImageGrab doesn't work with GNOME/GDM
        temp_screenshot = "/tmp/osworld_screenshot.png"
        subprocess.run(["scrot", temp_screenshot], check=True)
        screenshot = Image.open(temp_screenshot)

        # Try to add cursor overlay (may fail in some X server configurations)
        try:
            cursor_obj = Xcursor()
            imgarray = cursor_obj.getCursorImageArrayFast()
            cursor_img = Image.fromarray(imgarray)
            cursor_x, cursor_y = pyautogui.position()
            screenshot.paste(cursor_img, (cursor_x, cursor_y), cursor_img)
        except Exception as e:
            logger.warning("Failed to add cursor to screenshot: %s", e)

        screenshot.save(file_path)
        try:
            os.remove(temp_screenshot)
        except:
            pass'''

content = content.replace(old_linux_code, new_linux_code)

# Patch 2: Disable Flask debug mode
content = content.replace('app.run(debug=True, host="0.0.0.0")', 'app.run(debug=False, host="0.0.0.0")')

# Write back
with open('/home/user/osworld/desktop_env/server/main.py', 'w') as f:
    f.write(content)

print("✓ Scrot patch applied successfully")
PATCHEOF

python3 /tmp/patch_screenshot.py
rm /tmp/patch_screenshot.py

# Install Python dependencies
log "Installing Python dependencies..."
sudo -u user pip3 install --user flask pillow pyautogui python-xlib psutil requests

# Install OSWorld dependencies from requirements.txt
log "Installing OSWorld dependencies..."
if [ -f /home/user/osworld/requirements.txt ]; then
    sudo -u user pip3 install --user -r /home/user/osworld/requirements.txt
else
    log "Warning: requirements.txt not found, skipping"
fi

# Note: We don't use 'pip install -e .' because:
# 1. It has permission issues with --user flag
# 2. We use PYTHONPATH in the systemd service instead
# 3. The server runs via: python3 -m desktop_env.server.main

# Add .local/bin to PATH for user
log "Configuring PATH for user..."
if ! grep -q '.local/bin' /home/user/.bashrc; then
    echo 'export PATH=$HOME/.local/bin:$PATH' >> /home/user/.bashrc
    chown user:user /home/user/.bashrc
fi

# Create directories
log "Creating required directories..."
sudo -u user mkdir -p /home/user/osworld/logs
sudo -u user mkdir -p /home/user/osworld/desktop_env/server/screenshots

# Configure X.Org to use dummy driver
log "Configuring X.Org dummy video driver..."
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/10-dummy.conf << 'EOF'
Section "Device"
    Identifier "DummyDevice"
    Driver "dummy"
    VideoRam 32768
EndSection

Section "Monitor"
    Identifier "DummyMonitor"
    HorizSync 28.0-80.0
    VertRefresh 48.0-75.0
    Modeline "1920x1080" 172.80 1920 2048 2248 2576 1080 1083 1088 1120
EndSection

Section "Screen"
    Identifier "DummyScreen"
    Device "DummyDevice"
    Monitor "DummyMonitor"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Modes "1920x1080"
    EndSubSection
EndSection
EOF

# Configure GDM3 for auto-login
log "Configuring GDM3 auto-login..."
cat > /etc/gdm3/custom.conf << EOF
[daemon]
AutomaticLoginEnable = true
AutomaticLogin = user
WaylandEnable = false

[security]

[xdmcp]

[chooser]

[debug]
EOF

# Disable screen locking using dconf system-wide defaults
log "Configuring dconf to disable screen locking..."
mkdir -p /etc/dconf/db/local.d
cat > /etc/dconf/db/local.d/00-disable-screen-lock << 'EOF'
[org/gnome/desktop/session]
idle-delay=uint32 0

[org/gnome/desktop/screensaver]
lock-enabled=false
idle-activation-enabled=false
EOF

# Update dconf database
dconf update

# Also create a user autostart script as backup (runs when user session starts)
log "Creating autostart script for screen lock settings..."
sudo -u user mkdir -p /home/user/.config/autostart
cat > /home/user/.config/autostart/disable-screen-lock.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Disable Screen Lock
Exec=bash -c "gsettings set org.gnome.desktop.session idle-delay 0; gsettings set org.gnome.desktop.screensaver lock-enabled false; gsettings set org.gnome.desktop.screensaver idle-activation-enabled false"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

chown user:user /home/user/.config/autostart/disable-screen-lock.desktop

# Create systemd service for OSWorld server
log "Creating OSWorld systemd service..."
cat > /etc/systemd/system/osworld-server.service << EOF
[Unit]
Description=OSWorld Desktop Environment Server
After=graphical.target gdm.service

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/osworld
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$USER_UID/bus
Environment=PYTHONPATH=/home/user/osworld:/home/user/osworld/desktop_env/server
Environment=XAUTHORITY=/run/user/$USER_UID/gdm/Xauthority
ExecStartPre=/bin/bash -c 'for i in {1..30}; do [ -S /tmp/.X11-unix/X0 ] && exit 0; sleep 1; done; exit 1'
ExecStart=/usr/bin/python3 -m desktop_env.server.main --port 5000
Restart=always
RestartSec=10
StandardOutput=append:/home/user/osworld/logs/server.log
StandardError=append:/home/user/osworld/logs/server-error.log

[Install]
WantedBy=graphical.target
EOF

# Enable and start service
log "Enabling OSWorld service..."
systemctl daemon-reload
systemctl enable osworld-server.service

# Create test script
log "Creating test script..."
cat > /home/user/test_osworld.sh << 'TESTEOF'
#!/bin/bash
echo "========================================"
echo "Testing OSWorld GNOME Installation"
echo "========================================"
echo ""

echo "1. Checking GNOME desktop..."
if pgrep -x gnome-shell > /dev/null; then
    echo "   ✓ GNOME Shell is running"
else
    echo "   ✗ GNOME Shell is NOT running"
fi

if pgrep -x nautilus > /dev/null; then
    echo "   ✓ Nautilus (file manager) is running"
else
    echo "   ⚠ Nautilus is not running (will start on demand)"
fi

echo ""
echo "2. Checking display..."
if xdpyinfo -display :0 &>/dev/null; then
    echo "   ✓ Display :0 is available"
    echo "   Resolution: $(xdpyinfo -display :0 | grep dimensions | awk '{print $2}')"
else
    echo "   ✗ Display :0 is NOT available"
fi

echo ""
echo "3. Checking session type..."
SESSION_TYPE=$(loginctl show-session $(loginctl | grep user | awk '{print $1}') -p Type --value 2>/dev/null || echo "unknown")
echo "   Session type: $SESSION_TYPE"
if [ "$SESSION_TYPE" = "x11" ]; then
    echo "   ✓ Using Xorg (correct)"
else
    echo "   ⚠ Session type: $SESSION_TYPE"
fi

echo ""
echo "4. Testing Chrome..."
if command -v google-chrome &>/dev/null; then
    CHROME_VERSION=$(google-chrome --version)
    echo "   ✓ Chrome is installed: $CHROME_VERSION"
else
    echo "   ✗ Chrome is NOT installed"
fi

echo ""
echo "5. Testing OSWorld server..."
if curl -s http://localhost:5000/platform &>/dev/null; then
    PLATFORM=$(curl -s http://localhost:5000/platform)
    echo "   ✓ OSWorld server is responding"
    echo "   Platform: $PLATFORM"

    curl -s http://localhost:5000/screenshot -o /tmp/test_screenshot.png
    SIZE=$(stat -f%z /tmp/test_screenshot.png 2>/dev/null || stat -c%s /tmp/test_screenshot.png)
    echo "   ✓ Screenshot endpoint working ($SIZE bytes)"

    if [ $SIZE -gt 10000 ]; then
        echo "   ✓ Screenshot size looks good (>10KB)"
    else
        echo "   ✗ Screenshot is too small (<10KB) - may be black screen"
    fi
else
    echo "   ✗ OSWorld server is NOT responding"
fi

echo ""
echo "6. System resources..."
FREE_MEM=$(free -h | grep Mem | awk '{print $3"/"$2}')
echo "   Memory: $FREE_MEM"
CPU_CORES=$(nproc)
echo "   CPU cores: $CPU_CORES"
LOAD=$(uptime | awk -F'load average:' '{print $2}')
echo "   Load:$LOAD"

echo ""
echo "========================================"
echo "Test complete!"
echo "========================================"
TESTEOF

chmod +x /home/user/test_osworld.sh
chown user:user /home/user/test_osworld.sh

log "========================================"
log "Installation Complete!"
log "========================================"
log ""
log "IMPORTANT: You must REBOOT for changes to take effect"
log ""
log "After reboot:"
log "  1. SSH back in: gcloud compute ssh <VM-NAME> --zone=us-central1-a"
log "  2. Run test: bash ~/test_osworld.sh"
log "  3. Check screenshot works and is >1MB (showing actual GNOME desktop)"
log ""
log "Configuration notes:"
log "  - GNOME runs on Display :0 with dummy video driver"
log "  - Service uses scrot for screenshots (pyautogui doesn't work with GDM)"
log "  - Dummy driver configured in /etc/X11/xorg.conf.d/10-dummy.conf"
log "  - Virtual framebuffer provides 1920x1080 display without GPU"
log "  - Screen locking disabled via dconf system-wide defaults + autostart script"
log "  - python3-tk and python3-dev required for mouseinfo (pyautogui dependency)"
log ""
log "Next steps:"
log "  - Test with Chrome task"
log "  - Test with OS task"
log "  - Create golden image if all tests pass"
log "========================================"
