#!/bin/bash
#
# OSWorld Golden Image Builder v5
# Builds a complete OSWorld VM image with all dependencies
#
# Changes from v4:
#   - Added GNOME Desktop installation (Phase 1)
#   - Added vim-gtk3 (gvim) for GUI vim support
#   - Vim.desktop file now provided by vim-gtk3 package (not symlinked)
#   - Added Phase 0 to create 'user' account with UID 1002 if it doesn't exist
#   - Fixed all DBUS paths to use $OSWORLD_USER_ID variable
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
if ! id "$OSWORLD_USER" &>/dev/null; then
    echo "Creating user account '$OSWORLD_USER' with UID 1002..."
    sudo useradd -m -s /bin/bash -u 1002 "$OSWORLD_USER"
    echo "$OSWORLD_USER:$OSWORLD_USER" | sudo chpasswd
    sudo usermod -aG sudo "$OSWORLD_USER"
    echo "✓ User account created"
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
pip3 install --user pyautogui>=0.9.54 playwright pillow opencv-python-headless numpy requests flask psutil
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
# PHASE 6: Systemd Service
#
echo ""
echo "=== PHASE 6: Creating Systemd Service ==="

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

# Set favorite apps
gsettings set org.gnome.shell favorite-apps "['google-chrome.desktop', 'thunderbird.desktop', 'org.gnome.Nautilus.desktop']"
EOF

sudo chmod +x "/home/$OSWORLD_USER/.local/bin/osworld-gnome-setup.sh"

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
echo "     gcloud compute images create osworld-golden-v5-gnome \\"
echo "       --source-disk=<this-vm-name> \\"
echo "       --source-disk-zone=us-central1-a \\"
echo "       --family=osworld-gnome \\"
echo "       --project=cs294-475401"
echo ""
