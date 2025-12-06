#!/bin/bash
# Prepare VM for golden image creation
# This script cleans up temporary files and optimizes the VM
set -euo pipefail

log() {
    echo -e "\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')]\033[0m $1"
}

echo "=========================================="
echo "Preparing VM for Golden Image Creation"
echo "=========================================="
echo ""

log "Checking current disk usage..."
df -h /
echo ""

# 1. Clean up temporary files
log "Cleaning up temporary files..."
sudo rm -rf /tmp/*
sudo rm -rf /var/tmp/*
sudo rm -f /tmp/test*.png
sudo rm -f /tmp/test_screenshot.png
sudo rm -f /opt/osworld/logs/*.log
echo "✓ Temporary files cleaned"

# 2. Clean up package manager cache
log "Cleaning apt cache..."
sudo apt-get clean
sudo apt-get autoclean
sudo apt-get autoremove -y
echo "✓ Package cache cleaned"

# 3. Clean up logs
log "Cleaning system logs..."
sudo journalctl --vacuum-time=1d
echo "✓ System logs cleaned"

# 4. Clean up bash history (optional - remove sensitive commands)
log "Clearing bash history..."
history -c
cat /dev/null > ~/.bash_history
echo "✓ Bash history cleared"

# 5. Clean up SSH keys (will be regenerated on first boot)
log "Cleaning SSH host keys (will be regenerated)..."
sudo rm -f /etc/ssh/ssh_host_*
echo "✓ SSH host keys cleaned"

# 6. Verify services are running
log "Verifying OSWorld services..."
if sudo systemctl is-active --quiet xvfb && \
   sudo systemctl is-active --quiet openbox && \
   sudo systemctl is-active --quiet osworld-server; then
    echo "✓ All OSWorld services are running"
else
    echo "⚠ Warning: Some services are not running"
    sudo systemctl status xvfb openbox osworld-server --no-pager
fi

# 7. Test OSWorld API one last time
log "Testing OSWorld API..."
if curl -s http://localhost:5000/platform > /dev/null 2>&1; then
    echo "✓ OSWorld API is responding"
else
    echo "✗ OSWorld API is not responding"
    exit 1
fi

# 8. Show final disk usage
echo ""
log "Final disk usage:"
df -h /
echo ""

# 9. Show what will be in the image
log "Image will contain:"
echo "  - Ubuntu 22.04 LTS"
echo "  - Xvfb + Openbox (auto-start)"
echo "  - OSWorld server (auto-start)"
echo "  - Google Chrome $(google-chrome --version 2>/dev/null | cut -d' ' -f3)"
echo "  - Firefox $(firefox --version 2>/dev/null | cut -d' ' -f3)"
echo "  - LibreOffice, GIMP, gedit"
echo "  - All Python dependencies"
echo ""

echo "=========================================="
echo "VM is ready for imaging!"
echo "=========================================="
echo ""
echo "Next steps (run on your LOCAL machine):"
echo ""
echo "1. Create the golden image:"
echo "   gcloud compute images create osworld-golden-v1 \\"
echo "     --source-disk=green-agent-vm \\"
echo "     --source-disk-zone=us-central1-a \\"
echo "     --family=osworld \\"
echo "     --description=\"Native OSWorld - Chrome 141, Ubuntu 22.04, fully tested\""
echo ""
echo "2. Verify the image:"
echo "   gcloud compute images describe osworld-golden-v1"
echo ""
echo "3. Test by creating a new VM:"
echo "   gcloud compute instances create osworld-test-2 \\"
echo "     --image=osworld-golden-v1 \\"
echo "     --machine-type=n1-standard-4 \\"
echo "     --zone=us-central1-a"
echo ""
