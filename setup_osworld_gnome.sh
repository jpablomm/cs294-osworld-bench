#!/bin/bash
# OSWorld Native Setup - Full GNOME Desktop (Official Spec)
# Based on: vendor/OSWorld/desktop_env/server/README.md
#
# This script sets up a complete OSWorld environment following official specifications:
# - Ubuntu Desktop 22.04 with GNOME
# - User account: user:password (UID 1000)
# - Xorg display server with dummy video driver
# - All required software and configurations
# - OSWorld server with auto-start

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

check_ubuntu_version() {
    if ! grep -q "22.04" /etc/os-release; then
        error "This script requires Ubuntu 22.04 LTS"
    fi
}

# ============================================================================
# STEP 1: Install Ubuntu Desktop with GNOME
# ============================================================================

install_ubuntu_desktop() {
    log "Installing Ubuntu Desktop with GNOME (this will take 10-15 minutes)..."

    export DEBIAN_FRONTEND=noninteractive

    # Update package lists
    apt-get update -qq

    # Install ubuntu-desktop (includes GNOME, GDM3, Nautilus, etc.)
    info "Installing ubuntu-desktop package (~1.5GB download)..."
    apt-get install -y -qq ubuntu-desktop > /dev/null 2>&1 || {
        warn "ubuntu-desktop installation had warnings, checking if successful..."
        if ! command -v gnome-shell &> /dev/null; then
            error "GNOME Shell not installed"
        fi
    }

    # Set graphical target as default
    systemctl set-default graphical.target

    log "✓ Ubuntu Desktop with GNOME installed"
}

# ============================================================================
# STEP 2: Create User Account (user:password with UID 1000)
# ============================================================================

create_user_account() {
    log "Creating user account (user:password)..."

    # Check if UID 1000 is already taken
    if id -u 1000 &>/dev/null; then
        EXISTING_USER=$(id -un 1000)
        if [ "$EXISTING_USER" != "user" ]; then
            warn "UID 1000 is already taken by user: $EXISTING_USER"
            info "This is likely the first user created during OS installation"
            info "We'll create a new user 'user' with a different UID and update configs"

            # Create user without specific UID
            if ! id "user" &>/dev/null; then
                useradd -m -s /bin/bash user
                echo "user:password" | chpasswd
                usermod -aG sudo user
            fi
        else
            info "User 'user' already exists with UID 1000"
        fi
    else
        # Create user with UID 1000
        useradd -m -s /bin/bash -u 1000 user
        echo "user:password" | chpasswd
        usermod -aG sudo user
    fi

    # Verify user exists
    if ! id "user" &>/dev/null; then
        error "Failed to create user 'user'"
    fi

    log "✓ User account created: user:password"
}

# ============================================================================
# STEP 3: Configure GDM3 Auto-Login
# ============================================================================

configure_autologin() {
    log "Configuring GDM3 auto-login for user 'user'..."

    # Edit GDM3 custom.conf
    if [ -f /etc/gdm3/custom.conf ]; then
        # Backup original
        cp /etc/gdm3/custom.conf /etc/gdm3/custom.conf.backup

        # Enable auto-login
        sed -i '/\[daemon\]/a AutomaticLoginEnable=true\nAutomaticLogin=user' /etc/gdm3/custom.conf

        log "✓ Auto-login configured for user 'user'"
    else
        warn "GDM3 config not found, will configure manually later"
    fi
}

# ============================================================================
# STEP 4: Switch to Xorg (from Wayland)
# ============================================================================

configure_xorg() {
    log "Configuring Xorg display server (disabling Wayland)..."

    # Disable Wayland in GDM3
    if [ -f /etc/gdm3/custom.conf ]; then
        sed -i 's/#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/custom.conf
    fi

    # Install dummy video driver for headless operation
    log "Installing xserver-xorg-video-dummy..."
    apt-get install -y -qq xserver-xorg-video-dummy > /dev/null

    # Create xorg.conf for dummy driver
    log "Creating /etc/X11/xorg.conf..."
    cat > /etc/X11/xorg.conf <<'EOF'
Section "ServerLayout"
    Identifier "X.org Configured"
    Screen 0 "Screen0" 0 0
    InputDevice "Mouse0" "CorePointer"
    InputDevice "Keyboard0" "CoreKeyboard"
EndSection

Section "Files"
    ModulePath "/usr/lib/xorg/modules"
    FontPath "/usr/share/fonts/X11/misc"
    FontPath "/usr/share/fonts/X11/cyrillic"
    FontPath "/usr/share/fonts/X11/100dpi/:unscaled"
    FontPath "/usr/share/fonts/X11/75dpi/:unscaled"
    FontPath "/usr/share/fonts/X11/Type1"
    FontPath "/usr/share/fonts/X11/100dpi"
    FontPath "/usr/share/fonts/X11/75dpi"
    FontPath "built-ins"
EndSection

Section "Module"
    Load "glx"
EndSection

Section "InputDevice"
    Identifier "Keyboard0"
    Driver "kbd"
EndSection

Section "InputDevice"
    Identifier "Mouse0"
    Driver "mouse"
    Option "Protocol" "auto"
    Option "Device" "/dev/input/mice"
    Option "ZAxisMapping" "4 5 6 7"
EndSection

Section "Monitor"
    Identifier "Monitor0"
    VendorName "Monitor Vendor"
    ModelName "Monitor Model"
    HorizSync 28.0-80.0
    VertRefresh 48.0-75.0
EndSection

Section "Device"
    Identifier "Card0"
    Driver "modesetting"
    BusID "PCI:0:30:0"
    VideoRam 256000
EndSection

Section "Screen"
    Identifier "Screen0"
    Device "Device0"
    Monitor "Monitor0"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Modes "1920x1080"
    EndSubSection
EndSection
EOF

    # Create dummy driver config in xorg.conf.d
    mkdir -p /etc/X11/xorg.conf.d
    cat > /etc/X11/xorg.conf.d/10-dummy.conf <<'EOF'
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

    log "✓ Xorg configured with dummy video driver"
}

# ============================================================================
# STEP 5: Install Required Software
# ============================================================================

install_required_software() {
    log "Installing required software packages..."

    export DEBIAN_FRONTEND=noninteractive

    # Python and development tools
    log "Installing Python and development tools..."
    apt-get install -y -qq \
        python3 \
        python3-pip \
        python3-venv \
        python3-tk \
        python3-dev \
        build-essential \
        git \
        curl \
        wget \
        unzip \
        > /dev/null

    # OSWorld required packages
    log "Installing OSWorld dependencies..."
    apt-get install -y -qq \
        gnome-screenshot \
        wmctrl \
        ffmpeg \
        socat \
        xclip \
        at-spi2-core \
        python3-pyatspi \
        > /dev/null

    # Install Google Chrome
    log "Installing Google Chrome..."
    if [ ! -f /tmp/google-chrome-stable_current_amd64.deb ]; then
        wget -q -O /tmp/google-chrome-stable_current_amd64.deb \
            https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    fi
    apt-get install -y -qq /tmp/google-chrome-stable_current_amd64.deb || true
    apt-get install -f -y -qq > /dev/null

    # Install Firefox
    log "Installing Firefox..."
    apt-get install -y -qq firefox > /dev/null

    # Install LibreOffice 7.3.7.2 (specific version required)
    log "Installing LibreOffice..."
    apt-get install -y -qq libreoffice > /dev/null

    # Install GIMP 2.10.30
    log "Installing GIMP..."
    apt-get install -y -qq gimp > /dev/null

    # Install VLC 3.0.16
    log "Installing VLC..."
    apt-get install -y -qq vlc > /dev/null

    # Install VSCode
    log "Installing VSCode..."
    wget -q -O /tmp/vscode.deb "https://code.visualstudio.com/sha/download?build=stable&os=linux-deb-x64"
    apt-get install -y -qq /tmp/vscode.deb || true
    apt-get install -f -y -qq > /dev/null

    log "✓ All required software installed"
}

# ============================================================================
# STEP 6: Install VNC Support
# ============================================================================

install_vnc() {
    log "Installing VNC support (x11vnc + noVNC)..."

    # Install x11vnc
    apt-get install -y -qq x11vnc > /dev/null

    # Install noVNC
    snap install novnc 2>/dev/null || warn "noVNC snap installation failed"

    log "✓ VNC support installed"
}

# ============================================================================
# STEP 7: Setup OSWorld Server
# ============================================================================

setup_osworld_server() {
    log "Setting up OSWorld server..."

    OSWORLD_DIR="/home/user/osworld"

    # Create OSWorld directory
    mkdir -p "$OSWORLD_DIR"

    # Try multiple sources for OSWorld code (in order of preference)
    OSWORLD_INSTALLED=false

    # Option 1: Check if uploaded to /tmp/OSWorld
    if [ -d "/tmp/OSWorld" ]; then
        log "Found OSWorld in /tmp/OSWorld, copying..."
        cp -r /tmp/OSWorld/* "$OSWORLD_DIR/" 2>/dev/null || {
            warn "Some files failed to copy, continuing..."
        }
        OSWORLD_INSTALLED=true
    fi

    # Option 2: Clone from GitHub if not already installed
    if [ "$OSWORLD_INSTALLED" = false ]; then
        log "Cloning OSWorld from GitHub (this may take 2-3 minutes)..."
        apt-get install -y -qq git > /dev/null 2>&1

        if git clone https://github.com/xlang-ai/OSWorld.git /tmp/OSWorld-clone 2>/dev/null; then
            log "Copying cloned OSWorld code..."
            cp -r /tmp/OSWorld-clone/* "$OSWORLD_DIR/" 2>/dev/null
            rm -rf /tmp/OSWorld-clone
            OSWORLD_INSTALLED=true
        else
            error "Failed to clone OSWorld from GitHub. Please check network connectivity."
        fi
    fi

    # Verify installation
    if [ ! -f "$OSWORLD_DIR/desktop_env/server/main.py" ]; then
        error "OSWorld installation failed - main.py not found"
    fi

    log "✓ OSWorld code installed"

    # Install Python dependencies
    log "Installing OSWorld Python dependencies..."

    # First, try server requirements.txt if it exists
    if [ -f "$OSWORLD_DIR/desktop_env/server/requirements.txt" ]; then
        log "Found server requirements.txt, installing..."
        sudo -u user pip3 install -r "$OSWORLD_DIR/desktop_env/server/requirements.txt" 2>&1 | tee /tmp/pip_install.log || {
            warn "Some dependencies from requirements.txt failed, will install manually"
        }
    else
        warn "requirements.txt not found at $OSWORLD_DIR/desktop_env/server/requirements.txt"
    fi

    # Install system Python packages (via apt - these aren't available on PyPI)
    log "Installing system Python packages..."
    apt-get install -y -qq \
        python3-pyatspi \
        python3-gi \
        python3-opencv \
        > /dev/null || {
        warn "Some system packages failed to install"
    }

    # Install critical pip dependencies (in case requirements.txt is missing or incomplete)
    log "Installing critical pip dependencies..."
    sudo -u user pip3 install -q \
        python-xlib \
        "Pillow>=9.2.0" \
        pyautogui \
        opencv-python \
        flask \
        flask-cors \
        requests \
        lxml \
        numpy \
        psutil \
        || {
        warn "Some pip packages failed, checking if critical ones installed..."
    }

    # Verify critical imports work (skip pyautogui - it requires DISPLAY to be set)
    log "Verifying Python imports..."
    sudo -u user python3 -c "import Xlib; import pyatspi; import PIL; import flask" || {
        error "Python import verification failed. Missing critical dependencies."
    }

    # Note: pyautogui import will be verified after reboot when DISPLAY is available
    log "✓ Core Python dependencies verified (pyautogui will be verified after reboot)"

    # Set ownership
    chown -R user:user "$OSWORLD_DIR"

    log "✓ OSWorld server setup complete"
}

# ============================================================================
# STEP 8: Create SystemD Services
# ============================================================================

create_systemd_services() {
    log "Creating systemd services..."

    # Get the actual UID of user 'user' (may not be 1000)
    USER_UID=$(id -u user)
    log "Detected user UID: $USER_UID"

    # OSWorld server service
    cat > /etc/systemd/system/osworld-server.service <<EOF
[Unit]
Description=OSWorld Desktop Environment Server
After=graphical.target
Wants=graphical.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/osworld
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${USER_UID}/bus
Environment=PYTHONPATH=/home/user/osworld:/home/user/osworld/desktop_env/server
Environment=XAUTHORITY=/home/user/.Xauthority
ExecStart=/usr/bin/python3 -m desktop_env.server.main --port 5000
Restart=always
RestartSec=10
StandardOutput=append:/home/user/osworld/logs/server.log
StandardError=append:/home/user/osworld/logs/server-error.log

[Install]
WantedBy=multi-user.target
EOF

    # x11vnc service (user service)
    mkdir -p /etc/systemd/user
    cat > /etc/systemd/user/x11vnc.service <<'EOF'
[Unit]
Description=X11 VNC Server
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/x11vnc -display :0 -rfbport 5900 -forever
Restart=on-failure
RestartSec=3
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/user/.Xauthority

[Install]
WantedBy=default.target
EOF

    # noVNC service (user service)
    cat > /etc/systemd/user/novnc.service <<'EOF'
[Unit]
Description=noVNC Service
After=x11vnc.service network.target
Wants=x11vnc.service

[Service]
Type=simple
ExecStart=/snap/bin/novnc --vnc localhost:5900 --listen 5910
Restart=on-failure
RestartSec=3
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/user/.Xauthority

[Install]
WantedBy=default.target
EOF

    # Create logs directory
    mkdir -p /home/user/osworld/logs
    chown -R user:user /home/user/osworld/logs

    # Reload systemd
    systemctl daemon-reload

    # Enable OSWorld server (system service)
    systemctl enable osworld-server.service

    log "✓ Systemd services created"
    info "User services (x11vnc, novnc) will be enabled after reboot"
}

# ============================================================================
# STEP 9: Configure Software Settings
# ============================================================================

configure_software() {
    log "Configuring software settings..."

    # Chrome keyring configuration
    log "Disabling Chrome keyring password prompt..."
    sudo -u user bash -c '
        mkdir -p ~/.local/share/keyrings
        touch ~/.local/share/keyrings/login.keyring
    '

    # Chrome remote debugging configuration
    log "Configuring Chrome remote debugging..."
    sudo -u user bash -c '
        mkdir -p ~/.local/share/applications
        if [ -f /usr/share/applications/google-chrome.desktop ]; then
            cp /usr/share/applications/google-chrome.desktop ~/.local/share/applications/
            sed -i "s|Exec=/usr/bin/google-chrome-stable|Exec=/usr/bin/google-chrome-stable --remote-debugging-port=1337 --remote-debugging-address=0.0.0.0|g" ~/.local/share/applications/google-chrome.desktop
        fi
    '

    # Enable accessibility for Firefox/Thunderbird
    log "Enabling GNOME accessibility..."
    sudo -u user bash -c '
        export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
        gsettings set org.gnome.desktop.interface toolkit-accessibility true
    '

    # Disable automatic suspend
    log "Disabling automatic suspend..."
    sudo -u user bash -c '
        export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
        gsettings set org.gnome.desktop.session idle-delay 0
        gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type "nothing"
    '

    log "✓ Software configured"
}

# ============================================================================
# STEP 10: Disable Interfering Services
# ============================================================================

disable_interfering_services() {
    log "Disabling interfering system services..."

    # Disable unattended upgrades
    systemctl disable unattended-upgrades 2>/dev/null || true
    systemctl stop unattended-upgrades 2>/dev/null || true

    log "✓ Interfering services disabled"
}

# ============================================================================
# STEP 11: Create Test Script
# ============================================================================

create_test_script() {
    log "Creating test script..."

    cat > /home/user/test_osworld.sh <<'EOF'
#!/bin/bash
# Test script for OSWorld installation with GNOME

echo "========================================"
echo "Testing OSWorld GNOME Installation"
echo "========================================"
echo ""

# Check GNOME is running
echo "1. Checking GNOME desktop..."
if pgrep -x gnome-shell > /dev/null; then
    echo "   ✓ GNOME Shell is running"
else
    echo "   ✗ GNOME Shell is not running"
fi

if pgrep -x nautilus > /dev/null; then
    echo "   ✓ Nautilus (file manager) is running"
else
    echo "   ? Nautilus not running (may start on demand)"
fi

# Check display
echo ""
echo "2. Checking display..."
export DISPLAY=:0
if xdpyinfo > /dev/null 2>&1; then
    echo "   ✓ Display :0 is available"
    echo "   Resolution: $(xdpyinfo | grep dimensions | awk '{print $2}')"
else
    echo "   ✗ Display :0 is not available"
fi

# Check session type
echo ""
echo "3. Checking session type..."
SESSION_TYPE=$(loginctl show-session $(loginctl | grep user | awk '{print $1}') -p Type --value 2>/dev/null || echo "unknown")
echo "   Session type: $SESSION_TYPE"

# Check Xorg vs Wayland
if [ "$XDG_SESSION_TYPE" = "x11" ]; then
    echo "   ✓ Using Xorg (correct)"
elif [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    echo "   ✗ Using Wayland (should be Xorg)"
else
    echo "   ? Session type: $XDG_SESSION_TYPE"
fi

# Test Chrome
echo ""
echo "4. Testing Chrome..."
if command -v google-chrome &> /dev/null; then
    echo "   ✓ Chrome is installed: $(google-chrome --version)"
else
    echo "   ✗ Chrome is not installed"
fi

# Test OSWorld server
echo ""
echo "5. Testing OSWorld server..."
if curl -s -f http://localhost:5000/platform > /dev/null 2>&1; then
    echo "   ✓ OSWorld server is responding"
    PLATFORM=$(curl -s http://localhost:5000/platform)
    echo "   Platform: $PLATFORM"

    # Test screenshot
    curl -s http://localhost:5000/screenshot -o /tmp/test_screenshot.png 2>/dev/null
    if [ -f /tmp/test_screenshot.png ]; then
        SIZE=$(stat -c%s /tmp/test_screenshot.png 2>/dev/null || echo "0")
        echo "   ✓ Screenshot endpoint working (${SIZE} bytes)"
        if [ "$SIZE" -gt "10000" ]; then
            echo "   ✓ Screenshot size looks good (>10KB)"
        else
            echo "   ✗ Screenshot too small, may be blank screen"
        fi
    fi
else
    echo "   ✗ OSWorld server is not responding"
    echo "   Check: sudo systemctl status osworld-server"
fi

# System resources
echo ""
echo "6. System resources..."
echo "   Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "   CPU cores: $(nproc)"
echo "   Load: $(uptime | awk -F'load average:' '{print $2}')"

echo ""
echo "========================================"
echo "Test complete!"
echo "========================================"
EOF

    chmod +x /home/user/test_osworld.sh
    chown user:user /home/user/test_osworld.sh

    log "✓ Test script created: /home/user/test_osworld.sh"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    log "========================================"
    log "OSWorld Native Setup - GNOME Desktop"
    log "========================================"
    log ""
    log "This will install:"
    log "  - Ubuntu Desktop 22.04 with GNOME"
    log "  - User account: user:password"
    log "  - Xorg with dummy video driver"
    log "  - All required OSWorld software"
    log "  - VNC support (optional)"
    log "  - OSWorld server (auto-start)"
    log ""
    log "Estimated time: 20-30 minutes"
    log "Disk space required: ~10GB additional"
    log ""

    check_root
    check_ubuntu_version

    # Installation steps
    install_ubuntu_desktop
    create_user_account
    configure_autologin
    configure_xorg
    install_required_software
    install_vnc
    setup_osworld_server
    create_systemd_services
    configure_software
    disable_interfering_services
    create_test_script

    log ""
    log "========================================"
    log "Installation Complete!"
    log "========================================"
    log ""
    log "✓ Ubuntu Desktop with GNOME installed"
    log "✓ User 'user:password' created with auto-login"
    log "✓ Xorg configured (not Wayland)"
    log "✓ All required software installed"
    log "✓ OSWorld server configured"
    log ""
    log "IMPORTANT: You must REBOOT for changes to take effect"
    log ""
    log "After reboot:"
    log "  1. System will auto-login as 'user'"
    log "  2. GNOME desktop will start automatically"
    log "  3. OSWorld server will start on boot"
    log "  4. Test with: bash ~/test_osworld.sh"
    log ""
    log "To reboot now:"
    log "  sudo reboot"
    log ""
}

main "$@"
