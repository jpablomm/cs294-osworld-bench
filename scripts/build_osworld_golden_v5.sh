#!/bin/bash
#
# OSWorld Golden Image Builder v5
# Builds a complete OSWorld VM image with all dependencies
#
# Changes from v4:
#   - Added GNOME Desktop installation (Phase 1)
#   - Added vim-gtk3 (gvim) for GUI vim support
#   - Vim.desktop file now provided by vim-gtk3 package (not symlinked)
#   - Added Phase 0 to create 'user' account with UID 1000 (standard user UID)
#   - Fixed all DBUS paths to use $OSWORLD_USER_ID variable
#   - Changed UID from 1002 to 1000 to match OSWorld task expectations
#   - Removed DBUS symlink service (no longer needed)
#
# Usage:
#   1. Create VM from base Ubuntu 22.04 LTS (server image)
#   2. SSH into VM and run this script: sudo bash build_osworld_golden_v5.sh
#   3. Build takes ~30 minutes (GNOME install is the longest part)
#   4. Reboot and verify, then create image from the VM
#

set -e  # Exit on error
set -x  # Print commands

echo "======================================"
echo "OSWorld Golden Image Builder v5"
echo "======================================"

# Determine the user (should be 'user' for OSWorld)
OSWORLD_USER="${OSWORLD_USER:-user}"

#
# PHASE 0: Create OSWorld User Account
#
echo ""
echo "=== PHASE 0: Creating OSWorld User Account ==="

# Create the user account if it doesn't exist
# Note: Ubuntu Cloud Image creates 'ubuntu' user with UID 1000, we rename it to 'user'
if ! id "$OSWORLD_USER" &>/dev/null; then
    # Check if 'ubuntu' user exists with UID 1000
    if id -u ubuntu &>/dev/null && [ "$(id -u ubuntu)" = "1000" ]; then
        echo "Renaming 'ubuntu' user (UID 1000) to '$OSWORLD_USER'..."
        # Kill all processes owned by ubuntu user
        sudo pkill -u ubuntu || true
        # Rename the user and home directory
        sudo usermod -l "$OSWORLD_USER" ubuntu
        sudo usermod -d "/home/$OSWORLD_USER" -m "$OSWORLD_USER"
        sudo groupmod -n "$OSWORLD_USER" ubuntu
        # Set password
        echo "$OSWORLD_USER:$OSWORLD_USER" | sudo chpasswd
        echo "✓ User renamed from 'ubuntu' to '$OSWORLD_USER' (UID 1000)"
    else
        echo "Creating user account '$OSWORLD_USER' with UID 1000..."
        sudo useradd -m -s /bin/bash -u 1000 "$OSWORLD_USER"
        echo "$OSWORLD_USER:$OSWORLD_USER" | sudo chpasswd
        sudo usermod -aG sudo "$OSWORLD_USER"
        echo "✓ User account created"
    fi
else
    echo "✓ User '$OSWORLD_USER' already exists"
fi

OSWORLD_USER_ID=$(id -u "$OSWORLD_USER")
echo "Building for user: $OSWORLD_USER (UID: $OSWORLD_USER_ID)"

#
# PHASE 1: Install GNOME Desktop
#
echo ""
echo "=== PHASE 1: Installing GNOME Desktop ==="
sudo apt update

# Install GNOME Desktop (minimal without recommended packages for faster install)
echo "Installing GNOME Desktop and GDM3 (this may take 10-15 minutes)..."
sudo DEBIAN_FRONTEND=noninteractive apt install -y \
  ubuntu-desktop-minimal \
  gdm3

# Set GDM3 as default display manager
sudo systemctl set-default graphical.target

echo "✓ GNOME Desktop installed"

# Configure GDM for auto-login
echo "Configuring GDM auto-login for user '$OSWORLD_USER'..."
sudo tee /etc/gdm3/custom.conf << EOF
[daemon]
AutomaticLoginEnable = true
AutomaticLogin = $OSWORLD_USER
WaylandEnable = false

[security]

[xdmcp]

[chooser]

[debug]
EOF

echo "✓ GDM auto-login configured (X11 forced, auto-login enabled)"

# Configure Xorg dummy driver for virtual display
echo "Configuring Xorg dummy video driver..."
sudo mkdir -p /etc/X11/xorg.conf.d
sudo tee /etc/X11/xorg.conf.d/10-dummy.conf << EOF
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

echo "✓ Xorg dummy driver configured (1920x1080 virtual display)"

#
# PHASE 2: System Packages
#
echo ""
echo "=== PHASE 2: Installing System Packages ==="

# Core OSWorld dependencies (from OSWorld docs)
sudo apt install -y \
  python3 \
  python3-pip \
  python3-tk \
  python3-dev \
  gnome-screenshot \
  scrot \
  wmctrl \
  ffmpeg \
  socat \
  xclip \
  xserver-xorg-video-dummy \
  at-spi2-core \
  curl \
  wget \
  git \
  vim \
  gedit

# Python symlink (many tasks use 'python' not 'python3')
sudo ln -sf /usr/bin/python3 /usr/bin/python
sudo ln -sf /usr/bin/pip3 /usr/bin/pip

echo "✓ Core system packages installed"

#
# PHASE 3: Applications
#
echo ""
echo "=== PHASE 3: Installing Applications ==="

# Chrome (if not already installed)
if ! which google-chrome &>/dev/null; then
    echo "Installing Google Chrome..."
    wget -O- https://dl.google.com/linux/linux_signing_key.pub | \
      sudo gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | \
      sudo tee /etc/apt/sources.list.d/google-chrome.list
    sudo apt update
    sudo apt install -y google-chrome-stable
fi

# Office and multimedia apps
sudo apt install -y \
  gimp \
  thunderbird \
  libreoffice \
  vlc

# GUI Vim (gvim) for OSWorld vim tasks
# Note: vim-gtk3 package provides both gvim.desktop and vim.desktop
sudo apt install -y vim-gtk3
echo "✓ vim-gtk3 installed (provides vim.desktop for OSWorld tasks)"

# VS Code
if ! which code &>/dev/null; then
    echo "Installing VS Code..."
    wget -qO- https://packages.microsoft.com/keys/microsoft.asc | \
      sudo gpg --dearmor -o /usr/share/keyrings/microsoft-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-keyring.gpg] https://packages.microsoft.com/repos/vscode stable main" | \
      sudo tee /etc/apt/sources.list.d/vscode.list
    sudo apt update
    sudo apt install -y code
fi

echo "✓ Applications installed"

#
# PHASE 4: Python Packages (User-level)
#
echo ""
echo "=== PHASE 4: Installing Python Packages ==="

# Install for the OSWorld user, not root
sudo -u "$OSWORLD_USER" bash << 'PYTHON_INSTALL'
pip3 install --user --upgrade pip
pip3 install --user 'pyautogui>=0.9.54' playwright pillow opencv-python-headless numpy requests flask psutil
~/.local/bin/playwright install chromium
PYTHON_INSTALL

echo "✓ Python packages installed for user $OSWORLD_USER"

#
# PHASE 5: OSWorld Server (if not installed)
#
echo ""
echo "=== PHASE 5: Installing OSWorld Server ==="

OSWORLD_DIR="/home/$OSWORLD_USER/osworld"

if [ ! -d "$OSWORLD_DIR" ]; then
    echo "Cloning OSWorld repository (with cursor hotspot fix)..."
    sudo -u "$OSWORLD_USER" bash << OSWORLD_INSTALL
cd /home/$OSWORLD_USER
# Clone cs294-osworld-bench repo to get our fixed version of OSWorld
git clone https://github.com/jpablomm/cs294-osworld-bench.git green_agent_tmp
mv green_agent_tmp/vendor/OSWorld osworld
rm -rf green_agent_tmp
cd osworld
pip3 install --user -r desktop_env/server/requirements.txt
pip3 install --user -e .
OSWORLD_INSTALL
else
    echo "OSWorld already installed at $OSWORLD_DIR"
fi

echo "✓ OSWorld server installed (with cursor hotspot fix)"

#
# PHASE 6: Systemd Services (OSWorld Server)
#
echo ""
echo "=== PHASE 6: Creating Systemd Services ==="

# Create OSWorld server service (runs after GNOME session starts)
# Note: GDM provides the X server via X11 (Wayland disabled)
sudo tee /etc/systemd/system/osworld-server.service << EOF
[Unit]
Description=OSWorld Desktop Environment Server
After=graphical.target gdm.service

[Service]
Type=simple
User=$OSWORLD_USER
WorkingDirectory=$OSWORLD_DIR
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$OSWORLD_USER_ID/bus
Environment=PYTHONPATH=$OSWORLD_DIR:$OSWORLD_DIR/desktop_env/server
Environment=XAUTHORITY=/run/user/$OSWORLD_USER_ID/gdm/Xauthority
ExecStartPre=/bin/bash -c 'for i in {1..30}; do [ -S /tmp/.X11-unix/X0 ] && exit 0; sleep 1; done; exit 1'
ExecStart=/usr/bin/python3 -m desktop_env.server.main --port 5000
Restart=always
RestartSec=10
StandardOutput=append:$OSWORLD_DIR/logs/server.log
StandardError=append:$OSWORLD_DIR/logs/server-error.log

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable osworld-server

echo "✓ Systemd service created and enabled (OSWorld server)"

#
# PHASE 7: GNOME Configuration
#
echo ""
echo "=== PHASE 7: Configuring GNOME Desktop ==="

# Create startup script for GNOME settings
sudo -u "$OSWORLD_USER" mkdir -p "/home/$OSWORLD_USER/.config/autostart"

sudo -u "$OSWORLD_USER" tee "/home/$OSWORLD_USER/.config/autostart/osworld-setup.desktop" << EOF
[Desktop Entry]
Type=Application
Name=OSWorld GNOME Setup
Exec=/home/$OSWORLD_USER/.local/bin/osworld-gnome-setup.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

# Create the setup script (using variable substitution for UID)
sudo -u "$OSWORLD_USER" tee "/home/$OSWORLD_USER/.local/bin/osworld-gnome-setup.sh" << EOF
#!/bin/bash
# OSWorld GNOME Configuration
export DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/$OSWORLD_USER_ID/bus'

# Disable screen lock and power management
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 0

# Note: Favorite apps are NOT set here to allow OSWorld task setup to configure them.
# Default favorites are set once during image creation below.
EOF

sudo chmod +x "/home/$OSWORLD_USER/.local/bin/osworld-gnome-setup.sh"

# Set default favorite apps once (not in autostart script)
# This provides a reasonable default but allows OSWorld tasks to override it
sudo -u "$OSWORLD_USER" bash << EOF
export DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/$OSWORLD_USER_ID/bus'
gsettings set org.gnome.shell favorite-apps "['google-chrome.desktop', 'thunderbird.desktop', 'org.gnome.Nautilus.desktop']"
EOF

echo "✓ GNOME configuration created"

#
# PHASE 8: Create log directories
#
echo ""
echo "=== PHASE 8: Creating Log Directories ==="

sudo -u "$OSWORLD_USER" mkdir -p "$OSWORLD_DIR/logs"
sudo -u "$OSWORLD_USER" mkdir -p "$OSWORLD_DIR/desktop_env/server/screenshots"

echo "✓ Log directories created"

#
# VALIDATION
#
echo ""
echo "======================================"
echo "=== VALIDATION ==="
echo "======================================"

echo "User Account:"
id "$OSWORLD_USER" &>/dev/null && echo "  ✓ User '$OSWORLD_USER' exists (UID: $OSWORLD_USER_ID)" || echo "  ✗ User '$OSWORLD_USER' MISSING"

echo ""
echo "GNOME Desktop:"
which gdm3 && echo "  ✓ GDM3" || echo "  ✗ GDM3 MISSING"
which gnome-shell && echo "  ✓ GNOME Shell" || echo "  ✗ GNOME Shell MISSING"
systemctl is-enabled gdm &>/dev/null && echo "  ✓ GDM enabled" || echo "  ✗ GDM NOT enabled"

echo ""
echo "System Packages:"
which socat && echo "  ✓ socat" || echo "  ✗ socat MISSING"
which wmctrl && echo "  ✓ wmctrl" || echo "  ✗ wmctrl MISSING"
which xclip && echo "  ✓ xclip" || echo "  ✗ xclip MISSING"
which ffmpeg && echo "  ✓ ffmpeg" || echo "  ✗ ffmpeg MISSING"
which python && echo "  ✓ python symlink" || echo "  ✗ python symlink MISSING"
[ -f /usr/libexec/at-spi-bus-launcher ] && echo "  ✓ AT-SPI bus launcher" || echo "  ✗ AT-SPI bus launcher MISSING"

echo ""
echo "Applications:"
which google-chrome && echo "  ✓ Chrome" || echo "  ✗ Chrome MISSING"
which gimp && echo "  ✓ GIMP" || echo "  ✗ GIMP MISSING"
which thunderbird && echo "  ✓ Thunderbird" || echo "  ✗ Thunderbird MISSING"
which libreoffice && echo "  ✓ LibreOffice" || echo "  ✗ LibreOffice MISSING"
which vlc && echo "  ✓ VLC" || echo "  ✗ VLC MISSING"
which gvim && echo "  ✓ gvim (GUI Vim)" || echo "  ✗ gvim MISSING"
[ -f /usr/share/applications/vim.desktop ] && echo "  ✓ vim.desktop" || echo "  ✗ vim.desktop MISSING"
which code && echo "  ✓ VS Code" || echo "  ✗ VS Code MISSING"

echo ""
echo "Python Packages (for $OSWORLD_USER):"
sudo -u "$OSWORLD_USER" python3 -c "import pyautogui; print('  ✓ pyautogui')" 2>&1 || echo "  ✗ pyautogui MISSING"
sudo -u "$OSWORLD_USER" python3 -c "from playwright.sync_api import sync_playwright; print('  ✓ playwright')" 2>&1 || echo "  ✗ playwright MISSING"
sudo -u "$OSWORLD_USER" python3 -c "import PIL; print('  ✓ pillow')" 2>&1 || echo "  ✗ pillow MISSING"
sudo -u "$OSWORLD_USER" python3 -c "import flask; print('  ✓ flask')" 2>&1 || echo "  ✗ flask MISSING"

echo ""
echo "OSWorld Server:"
[ -d "$OSWORLD_DIR" ] && echo "  ✓ OSWorld code installed" || echo "  ✗ OSWorld code MISSING"
systemctl is-enabled osworld-server &>/dev/null && echo "  ✓ OSWorld server service enabled" || echo "  ✗ OSWorld server service NOT enabled"

echo ""
echo "======================================"
echo "=== BUILD COMPLETE ==="
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Reboot the VM to test autostart: sudo reboot"
echo "  2. After reboot, verify OSWorld server is running:"
echo "     systemctl status osworld-server"
echo "     curl http://localhost:5000/platform"
echo "  3. If everything works, create the golden image:"
echo "     gcloud compute images create osworld-golden-v12-gnome \\"
echo "       --source-disk=<this-vm-name> \\"
echo "       --source-disk-zone=us-central1-a \\"
echo "       --family=osworld-gnome \\"
echo "       --project=cs294-475401"
echo ""
