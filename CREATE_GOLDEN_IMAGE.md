# Creating the OSWorld Golden Image

This guide walks through creating a golden GCE image for OSWorld. There are two versions available:

- **v3 (GNOME-based)** - Latest, recommended for production use
- **v1 (Xvfb-based)** - Legacy, lightweight but may have limitations with OS tasks

---

## Image Versions

### osworld-golden-v3-gnome (Recommended)

**Full GNOME Desktop Environment**

- ✅ Works with Chrome AND OS tasks
- ✅ Full desktop with file manager, launcher, etc.
- ✅ Screenshots show actual desktop (>1MB)
- ✅ Python dependencies included (python3-tk, python3-dev)
- ✅ Screen locking disabled via dconf + autostart
- ✅ Uses scrot for screenshots (patched for GNOME/GDM)
- ✅ 60-second boot time
- ✅ Fully automated setup via `setup_osworld_gnome_v3.sh`

**Setup script:** `setup_osworld_gnome_v3.sh`
**Image family:** `osworld-gnome`

### osworld-golden-v1 (Legacy)

**Xvfb + Openbox (Lightweight)**

- ✅ Works well with Chrome tasks
- ⚠️ May have issues with OS tasks requiring full desktop
- ✅ Smaller footprint
- ✅ 60-second boot time

**Setup script:** `setup_native_osworld.sh`
**Image family:** `osworld`

---

## Creating v3 GNOME Image (Recommended)

This is the production-ready approach with all fixes included.

---

### Step 1: Create VM with Setup Script

```bash
# 1. Create a new VM
gcloud compute instances create osworld-gnome-v7 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --machine-type=n1-standard-4 \
  --boot-disk-size=50GB \
  --zone=us-central1-a

# 2. Copy the setup script
gcloud compute scp setup_osworld_gnome_v3.sh osworld-gnome-v7:~/ --zone=us-central1-a

# 3. SSH and run setup
gcloud compute ssh osworld-gnome-v7 --zone=us-central1-a

# On the VM:
sudo bash setup_osworld_gnome_v3.sh

# This takes about 20 minutes and installs:
# - GNOME Desktop with GDM3
# - OSWorld with scrot patch
# - python3-tk and python3-dev (critical!)
# - dconf screen lock prevention
# - All required applications

# 4. Reboot for changes to take effect
sudo reboot
```

### Step 2: Verify Setup

After reboot (wait 60 seconds), SSH back in and test:

```bash
gcloud compute ssh osworld-gnome-v7 --zone=us-central1-a

# Run the built-in test
bash ~/test_osworld.sh
```

**Expected output:**
```
========================================
Testing OSWorld GNOME Installation
========================================

1. Checking GNOME desktop...
   ✓ GNOME Shell is running

2. Checking display...
   ✓ Display :0 is available
   Resolution: 1920x1080

3. Checking session type...
   ✓ Using Xorg (correct)

4. Testing Chrome...
   ✓ Chrome is installed

5. Testing OSWorld server...
   ✓ OSWorld server is responding
   Platform: Linux
   ✓ Screenshot endpoint working (1143930 bytes)
   ✓ Screenshot size looks good (>10KB)

========================================
Test complete!
========================================
```

**Key validation points:**
- Screenshot size >1MB (indicates actual desktop, not black screen)
- OSWorld server responds immediately (python3-tk is working)
- No manual unlock needed (screen lock disabled)

### Step 3: Prepare for Imaging

**Run this ON THE VM**:

```bash
# Clean up temporary files
sudo rm -rf /tmp/*
sudo rm -rf /var/tmp/*
sudo rm -f /home/user/osworld/logs/*.log

# Clean package cache
sudo apt-get clean
sudo apt-get autoclean
sudo apt-get autoremove -y

# Clean system logs
sudo journalctl --vacuum-time=1d

# Clear bash history
history -c
cat /dev/null > ~/.bash_history

# Clean SSH host keys (regenerated on first boot)
sudo rm -f /etc/ssh/ssh_host_*

# Verify services
sudo systemctl status gdm osworld-server --no-pager | head -20

# Test API one last time
curl -s http://localhost:5000/platform

# Shutdown
sudo shutdown -h now
```

---

### Step 4: Create the Golden Image

**Run this ON YOUR LOCAL MACHINE** (after VM is shut down):

```bash
# Create the v3 golden image
gcloud compute images create osworld-golden-v3-gnome \
  --source-disk=osworld-gnome-v7 \
  --source-disk-zone=us-central1-a \
  --family=osworld-gnome \
  --description="OSWorld GNOME v3 - Full desktop with python3-tk + dconf screen lock fixes - Validated 2025-10-20" \
  --labels=version=v3,type=osworld-gnome,status=production
```

**This will take 5-10 minutes.**

**Expected output:**
```
Created [https://www.googleapis.com/compute/v1/projects/YOUR-PROJECT/global/images/osworld-golden-v3-gnome].
NAME                     PROJECT       FAMILY         DEPRECATED  STATUS
osworld-golden-v3-gnome  YOUR-PROJECT  osworld-gnome              READY
```

---

### Step 5: Verify the Image

```bash
# Check image details
gcloud compute images describe osworld-golden-v3-gnome

# Should show:
# - creationTimestamp
# - diskSizeGb: 50
# - family: osworld-gnome
# - status: READY
```

---

### Step 6: Test the Golden Image

Create a new VM from the golden image:

```bash
# Create test VM from v3 image
gcloud compute instances create osworld-test-v3-image \
  --image=osworld-golden-v3-gnome \
  --machine-type=n1-standard-4 \
  --zone=us-central1-a \
  --boot-disk-size=50GB

# Wait 60 seconds for GNOME to fully start
echo "Waiting for VM to boot and GNOME to start..."
sleep 60
```

---

### Step 7: Verify the New VM Works

Test the new VM with the built-in test script:

```bash
# Run the comprehensive test
gcloud compute ssh osworld-test-v3-image --zone=us-central1-a \
  --command="bash ~/test_osworld.sh"
```

**Expected output:**
```
========================================
Testing OSWorld GNOME Installation
========================================

1. Checking GNOME desktop...
   ✓ GNOME Shell is running

2. Checking display...
   ✓ Display :0 is available
   Resolution: 1920x1080

3. Checking session type...
   ✓ Using Xorg (correct)

4. Testing Chrome...
   ✓ Chrome is installed: Google Chrome 141.0.7390.107

5. Testing OSWorld server...
   ✓ OSWorld server is responding
   Platform: Linux
   ✓ Screenshot endpoint working (1125885 bytes)
   ✓ Screenshot size looks good (>10KB)

========================================
Test complete!
========================================
```

**Critical validation points:**
- ✅ Screenshot size >1MB (proves desktop is rendering)
- ✅ Server responds immediately (python3-tk fix working)
- ✅ No manual intervention needed (screen lock fix working)

**If all tests pass:** 🎉 **Golden image v3 is production-ready!**

---

### Step 8: Clean Up Test VM

After verifying it works, delete the test VM:

```bash
gcloud compute instances delete osworld-test-v3-image --zone=us-central1-a --quiet
```

---

## Critical Fixes in v3

The v3 image includes two essential fixes that were discovered through extensive testing:

### Fix #1: Python Dependencies (python3-tk)

**Problem:**
- OSWorld server would fail to start with cryptic error: `env: '-m': No such file or directory`
- Root cause: `mouseinfo` (dependency of `pyautogui`) requires `python3-tk` package
- Import fails at module load time, before server can even start

**Solution:**
```bash
# In setup_osworld_gnome_v3.sh (lines 39-40)
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-tk \
    python3-dev
```

**Validation:**
```bash
# Server should respond immediately after boot
curl http://localhost:5000/platform
# Expected: Linux
```

### Fix #2: Screen Lock Prevention (dconf + autostart)

**Problem:**
- Screen locks after 5 minutes of idle (default GNOME behavior)
- Screenshots show lock screen (65-110KB) instead of desktop (>1MB)
- Previous fix (systemd service) ran too early, before dbus session existed

**Solution:**
Dual approach for reliability:

1. **System-wide dconf defaults** (applied before any session):
```bash
# In setup_osworld_gnome_v3.sh (lines 234-242)
mkdir -p /etc/dconf/db/local.d
cat > /etc/dconf/db/local.d/00-disable-screen-lock << 'EOF'
[org/gnome/desktop/session]
idle-delay=uint32 0

[org/gnome/desktop/screensaver]
lock-enabled=false
idle-activation-enabled=false
EOF
dconf update
```

2. **User autostart script** (runs when session starts):
```bash
# In setup_osworld_gnome_v3.sh (lines 248-258)
mkdir -p /home/user/.config/autostart
cat > /home/user/.config/autostart/disable-screen-lock.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Disable Screen Lock
Exec=bash -c "gsettings set org.gnome.desktop.session idle-delay 0; gsettings set org.gnome.desktop.screensaver lock-enabled false; gsettings set org.gnome.desktop.screensaver idle-activation-enabled false"
X-GNOME-Autostart-enabled=true
EOF
```

**Validation:**
```bash
# Check settings are applied
sudo -u user bash -c 'export DISPLAY=:0 && export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1002/bus && gsettings get org.gnome.desktop.session idle-delay'
# Expected: uint32 0

# Screenshot should be >1MB showing desktop
curl -s http://localhost:5000/screenshot -o /tmp/test.png && ls -lh /tmp/test.png
# Expected: >1MB (e.g., 1.1M)
```

---

## Using the Golden Image v3

### Create a New VM

```bash
gcloud compute instances create my-osworld-vm \
  --image-family=osworld-gnome \
  --machine-type=n1-standard-4 \
  --zone=us-central1-a
```

**Boot time:** ~60 seconds (vs 20 minutes with setup script!)

### Create Multiple VMs

```bash
# Create 5 GNOME VMs in parallel
for i in {1..5}; do
  gcloud compute instances create osworld-vm-$i \
    --image-family=osworld-gnome \
    --machine-type=n1-standard-4 \
    --zone=us-central1-a \
    --async
done
```

### Use in Terraform

```hcl
resource "google_compute_instance" "osworld" {
  name         = "osworld-${var.instance_id}"
  machine_type = "n1-standard-4"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      # Use latest from osworld-gnome family (auto-updates to v3, v4, etc.)
      image = "osworld-gnome"
      size  = 50
    }
  }

  network_interface {
    network = "default"
  }

  tags = ["osworld-vm"]
}
```

---

## Golden Image Specifications

### v3 GNOME (osworld-golden-v3-gnome) - Latest

**What's Included:**
- **OS:** Ubuntu 22.04 LTS
- **Desktop:** GNOME Shell 42 with GDM3
- **Display:** X.Org with dummy video driver (Display :0, 1920x1080)
- **Screenshot:** scrot (patched for GNOME/GDM compatibility)
- **Screen Lock:** Disabled via dconf + autostart (prevents idle timeout)
- **Python:** python3-tk and python3-dev installed (required for pyautogui)
- **OSWorld Server:** Flask REST API on port 5000
- **Chrome:** 141.0.7390.107
- **Firefox:** Latest
- **LibreOffice:** Calc, Writer, Impress
- **Other Apps:** GIMP, gedit, Nautilus (file manager)

**Auto-Start Services:**
All services start automatically on boot:
- `gdm.service` - GNOME Display Manager (starts GNOME Shell)
- `osworld-server.service` - REST API
- Screen lock disabler (autostart desktop entry)

### v1 Xvfb (osworld-golden-v1) - Legacy

**What's Included:**
- **OS:** Ubuntu 22.04 LTS
- **Display:** Xvfb (virtual display :99, 1920x1080x24)
- **Window Manager:** Openbox
- **OSWorld Server:** Flask REST API on port 5000
- **Chrome:** 141.0.7390.107
- **Firefox:** Latest
- **LibreOffice:** Calc, Writer
- **Other Apps:** GIMP, gedit, nano, vim, pcmanfm

**Auto-Start Services:**
- `xvfb.service` - Virtual display
- `openbox.service` - Window manager
- `osworld-server.service` - REST API

### Disk Size

- **50GB** total
- ~35GB used
- ~15GB free

### Network

- Port 5000: OSWorld REST API (internal only)
- Standard GCE networking

---

## Image Management

### List All Images

```bash
gcloud compute images list --filter="family=osworld"
```

### Create New Version

When you make improvements to `green-agent-vm`:

```bash
# Create v2
gcloud compute images create osworld-golden-v2 \
  --source-disk=green-agent-vm \
  --source-disk-zone=us-central1-a \
  --family=osworld \
  --description="Native OSWorld v2 - Chrome 142, bug fixes"
```

**Note:** The `family=osworld` tag means new VMs will automatically use the latest version.

### Delete Old Images

```bash
# Delete v1 when v2 is stable
gcloud compute images delete osworld-golden-v1 --quiet
```

### Share Image (Optional)

To share with other projects:

```bash
# Make image public (use with caution!)
gcloud compute images add-iam-policy-binding osworld-golden-v1 \
  --member='allAuthenticatedUsers' \
  --role='roles/compute.imageUser'

# Or share with specific project
gcloud compute images add-iam-policy-binding osworld-golden-v1 \
  --member='serviceAccount:SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com' \
  --role='roles/compute.imageUser'
```

---

## Cost

### Storage Cost

- **$0.05/GB/month** for custom images
- 50GB image = **$2.50/month**

### Optimization

After creating multiple versions, you can delete old images to save costs.

---

## Troubleshooting

### Image Creation Fails

```bash
# Check disk status
gcloud compute disks describe green-agent-vm --zone=us-central1-a

# Ensure VM is running (imaging works better with running VMs)
gcloud compute instances list --filter="name=green-agent-vm"
```

### New VM Doesn't Work

```bash
# Check serial console output
gcloud compute instances get-serial-port-output osworld-test-2 --zone=us-central1-a

# SSH and check services
gcloud compute ssh osworld-test-2 --zone=us-central1-a
sudo systemctl status xvfb openbox osworld-server
```

### Services Not Starting

SSH into the new VM and restart:

```bash
sudo systemctl restart xvfb
sleep 2
sudo systemctl restart openbox
sleep 2
sudo systemctl restart osworld-server
sleep 3
curl http://localhost:5000/platform
```

---

## Best Practices

1. **Test Before Production**
   - Always create a test VM and verify it works
   - Run the full test suite
   - Test with actual OSWorld tasks

2. **Version Your Images**
   - Use descriptive names: `osworld-golden-v1`, `osworld-golden-v2`
   - Document changes in the description
   - Keep at least one previous version as backup

3. **Regular Updates**
   - Update Chrome/Firefox monthly
   - Update system packages for security
   - Rebuild image after significant changes

4. **Monitor Costs**
   - Delete unused images
   - Use lifecycle policies to auto-delete old images
   - Consider image storage costs ($2.50/month per image)

5. **Security**
   - Don't include secrets in images
   - Rotate SSH keys on first boot
   - Keep images in same project (don't share publicly)

---

## Next Steps

After creating the golden image:

1. ✅ **Test thoroughly** - Verify new VMs work perfectly
2. 🔨 **Build orchestrator** - Cloud Run service to manage VMs
3. 🔗 **Integrate with Green Agent** - Add OSWorld client
4. 📊 **Add monitoring** - Track VM health and costs
5. ⚡ **Optimize** - Preemptible VMs, auto-scaling, etc.

---

## Validation Results

### v3 Golden Image - Validated 2025-10-19

**Test VM:** `osworld-test-v3-image` (created from `osworld-golden-v3-gnome`)

**System Tests:**
```
✓ GNOME Shell is running
✓ Display :0 is available (1920x1080)
✓ Using Xorg (correct)
✓ Chrome is installed: Google Chrome 141.0.7390.107
✓ OSWorld server is responding
  Platform: Linux
✓ Screenshot endpoint working (1,125,885 bytes)
✓ Screenshot size looks good (>10KB)
```

**Benchmark Tests:**

1. **Chrome Task** (Task ID: 0aad6bbe-6b0f-4c32-b0fa-f21b3a1ff06d)
   - Status: Infrastructure validated ✓
   - Server responded correctly
   - Chrome launched successfully
   - GPT-4o vision saw desktop clearly
   - Note: Task got stuck on Chrome keyring dialog (expected Chrome security behavior, not infrastructure bug)

2. **OS Task** (Task ID: 5ea617a3-0e86-4ba6-aab2-dac9aa2e8d57)
   - Status: **SUCCESS** ✓
   - Task: Recover deleted poster from Trash
   - Steps: 3 (completed in 3 steps)
   - Result: File successfully restored
   - GPT-4o performance: Excellent - navigated Nautilus file manager, located Trash, restored file
   - Screenshot quality: Full GNOME desktop visible, >1MB screenshots

**Critical Fixes Validated:**
- ✅ python3-tk: Server starts immediately without errors
- ✅ dconf + autostart: No screen locking, screenshots show desktop
- ✅ scrot: Screenshots >1MB showing actual GNOME desktop (not black screens)

**Performance:**
- Boot time: ~60 seconds (GNOME + GDM + OSWorld server)
- API response: Immediate (no delays)
- Screenshot quality: 1.1-1.2 MB (full desktop rendering)

---

## Success Criteria

✅ Golden image created successfully
✅ New VMs boot in ~60 seconds
✅ All OSWorld endpoints work immediately
✅ Chrome launches and renders correctly
✅ No manual setup required
✅ **OS tasks complete successfully**
✅ **GPT-4o vision can see and interact with desktop**

**Status:** Production ready! 🚀
