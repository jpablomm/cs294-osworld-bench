#!/bin/bash
#
# OSWorld Golden Image Builder v4
# Builds a complete OSWorld VM image with all dependencies
#
# Usage:
#   1. Create VM from base Ubuntu 22.04 GNOME
#   2. SSH into VM and run this script
#   3. Create image from the VM
#

set -e  # Exit on error
set -x  # Print commands

echo "======================================"
echo "OSWorld Golden Image Builder v4"
echo "======================================"

# Determine the user (should be 'user' for OSWorld)
OSWORLD_USER="${OSWORLD_USER:-user}"
OSWORLD_USER_ID=$(id -u "$OSWORLD_USER" 2>/dev/null || echo "1002")

echo "Building for user: $OSWORLD_USER (UID: $OSWORLD_USER_ID)"

#
# PHASE 1: System Packages
#
echo ""
echo "=== PHASE 1: Installing System Packages ==="
sudo apt update

# Core OSWorld dependencies (from OSWorld docs)
sudo apt install -y \
  python3 \
  python3-pip \
  python3-tk \
  python3-dev \
  gnome-screenshot \
  wmctrl \
  ffmpeg \
  socat \
  xclip \
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
# PHASE 2: Applications
#
echo ""
echo "=== PHASE 2: Installing Applications ==="

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
# PHASE 3: Python Packages (User-level)
#
echo ""
echo "=== PHASE 3: Installing Python Packages ==="

# Install for the OSWorld user, not root
sudo -u "$OSWORLD_USER" bash << 'PYTHON_INSTALL'
pip3 install --user --upgrade pip

pip3 install --user \
  pyautogui>=0.9.54 \
  playwright \
  pillow \
  opencv-python-headless \
  numpy \
  requests \
  flask \
  psutil

# Install Playwright browsers
~/.local/bin/playwright install chromium
PYTHON_INSTALL

echo "✓ Python packages installed for user $OSWORLD_USER"

#
# PHASE 4: OSWorld Server (if not installed)
#
echo ""
echo "=== PHASE 4: Installing OSWorld Server ==="

OSWORLD_DIR="/home/$OSWORLD_USER/osworld"

if [ ! -d "$OSWORLD_DIR" ]; then
    echo "Cloning OSWorld repository..."
    sudo -u "$OSWORLD_USER" bash << OSWORLD_INSTALL
cd /home/$OSWORLD_USER
git clone https://github.com/xlang-ai/OSWorld.git osworld
cd osworld
pip3 install --user -r desktop_env/server/requirements.txt
pip3 install --user -e .
OSWORLD_INSTALL
else
    echo "OSWorld already installed at $OSWORLD_DIR"
fi

echo "✓ OSWorld server installed"

#
# PHASE 5: Systemd Service
#
echo ""
echo "=== PHASE 5: Creating Systemd Service ==="

sudo tee /etc/systemd/system/osworld-server.service << EOF
[Unit]
Description=OSWorld Desktop Environment Server
After=graphical.target

[Service]
Type=simple
User=$OSWORLD_USER
Environment="DISPLAY=:0"
Environment="DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$OSWORLD_USER_ID/bus"
Environment="XAUTHORITY=/run/user/$OSWORLD_USER_ID/gdm/Xauthority"
Environment="PYTHONPATH=$OSWORLD_DIR:$OSWORLD_DIR/desktop_env/server"
WorkingDirectory=$OSWORLD_DIR
ExecStart=/usr/bin/python3 -m desktop_env.server.main --port 5000
Restart=always
RestartSec=3

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable osworld-server

echo "✓ Systemd service created and enabled"

#
# PHASE 6: GNOME Configuration
#
echo ""
echo "=== PHASE 6: Configuring GNOME Desktop ==="

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

# Create the setup script
sudo -u "$OSWORLD_USER" tee "/home/$OSWORLD_USER/.local/bin/osworld-gnome-setup.sh" << 'SETUP_SCRIPT'
#!/bin/bash
# OSWorld GNOME Configuration
export DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1002/bus'

# Disable screen lock and power management
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 0

# Set favorite apps
gsettings set org.gnome.shell favorite-apps "['google-chrome.desktop', 'thunderbird.desktop', 'org.gnome.Nautilus.desktop']"
SETUP_SCRIPT

sudo chmod +x "/home/$OSWORLD_USER/.local/bin/osworld-gnome-setup.sh"

echo "✓ GNOME configuration created"

#
# PHASE 7: Create log directories
#
echo ""
echo "=== PHASE 7: Creating Log Directories ==="

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

echo "System Packages:"
which socat && echo "  ✓ socat" || echo "  ✗ socat MISSING"
which wmctrl && echo "  ✓ wmctrl" || echo "  ✗ wmctrl MISSING"
which xclip && echo "  ✓ xclip" || echo "  ✗ xclip MISSING"
which ffmpeg && echo "  ✓ ffmpeg" || echo "  ✗ ffmpeg MISSING"
which python && echo "  ✓ python symlink" || echo "  ✗ python symlink MISSING"

echo ""
echo "Applications:"
which google-chrome && echo "  ✓ Chrome" || echo "  ✗ Chrome MISSING"
which gimp && echo "  ✓ GIMP" || echo "  ✗ GIMP MISSING"
which thunderbird && echo "  ✓ Thunderbird" || echo "  ✗ Thunderbird MISSING"
which libreoffice && echo "  ✓ LibreOffice" || echo "  ✗ LibreOffice MISSING"
which vlc && echo "  ✓ VLC" || echo "  ✗ VLC MISSING"
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
systemctl is-enabled osworld-server &>/dev/null && echo "  ✓ Systemd service enabled" || echo "  ✗ Systemd service NOT enabled"

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
echo "     gcloud compute images create osworld-golden-v4-gnome \\"
echo "       --source-disk=<this-vm-name> \\"
echo "       --source-disk-zone=us-central1-a \\"
echo "       --family=osworld-gnome \\"
echo "       --project=cs294-475401"
echo ""
