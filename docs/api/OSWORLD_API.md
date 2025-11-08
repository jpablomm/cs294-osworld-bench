# OSWorld Server API Reference

The OSWorld server provides a REST API for controlling a Linux desktop environment remotely.

## Base URL
```
http://localhost:5000
```

## Available Endpoints

### 1. **Screenshot** - Capture screen with cursor
```bash
GET /screenshot
```

**Response:** PNG image

**Example:**
```bash
curl http://localhost:5000/screenshot -o screenshot.png
```

---

### 2. **Execute Command** - Run shell commands
```bash
POST /execute
POST /setup/execute  # Alias
```

**Request Body:**
```json
{
  "command": ["ls", "-la"],  // Array of command + args
  "shell": false             // Optional: use shell execution
}
```

OR for shell commands:
```json
{
  "command": "ls -la | grep test",
  "shell": true
}
```

**Response:**
```json
{
  "status": "success",
  "output": "...",
  "error": "...",
  "returncode": 0
}
```

**Examples:**
```bash
# Run a simple command
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command": ["whoami"]}'

# Open Chrome
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command": ["google-chrome", "--new-window", "https://google.com"]}'

# Shell command
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "echo Hello World", "shell": true}'
```

---

### 3. **Execute with Verification** - Run command and wait for result
```bash
POST /execute_with_verification
POST /setup/execute_with_verification  # Alias
```

**Request Body:**
```json
{
  "command": ["ls", "-la"],
  "shell": false,
  "verification": {
    "type": "output_contains",
    "value": "expected_text"
  },
  "max_wait_time": 10,
  "check_interval": 1
}
```

---

### 4. **Launch Application**
```bash
POST /setup/launch
```

**Request Body:**
```json
{
  "app": "chrome",  // or "firefox", "gedit", etc.
  "args": ["--new-window", "https://google.com"]
}
```

---

### 5. **Accessibility Tree** - Get UI element hierarchy
```bash
GET /accessibility
```

**Response:** JSON tree of all UI elements (windows, buttons, text fields, etc.)

**Example:**
```bash
curl http://localhost:5000/accessibility > ui_tree.json
```

**Use cases:**
- Find open windows/applications
- Locate UI elements (buttons, text fields)
- Verify app state

---

### 6. **Platform Info**
```bash
GET /platform
```

**Response:** Platform name (e.g., "Linux")

---

### 7. **Cursor Position**
```bash
GET /cursor_position
```

**Response:**
```json
{
  "x": 100,
  "y": 200
}
```

---

### 8. **Screen Size**
```bash
POST /screen_size
```

**Response:**
```json
{
  "width": 1920,
  "height": 1080
}
```

---

### 9. **Terminal Output** - Get terminal text
```bash
GET /terminal
```

**Response:** Current terminal output (if terminal is open)

---

### 10. **Window Management**

#### Get Window Size
```bash
POST /window_size
```
**Body:** `{"window_title": "Chrome"}`

#### Activate Window
```bash
POST /setup/activate_window
```
**Body:** `{"window_title": "Chrome"}`

#### Close Window
```bash
POST /setup/close_window
```
**Body:** `{"window_title": "Chrome"}`

---

### 11. **File Operations**

#### List Directory
```bash
POST /list_directory
```
**Body:** `{"path": "/home/osworld"}`

#### Get File Contents
```bash
POST /file
```
**Body:** `{"path": "/home/osworld/test.txt"}`

#### Upload File
```bash
POST /setup/upload
```
**Body:** Form data with file

#### Download File
```bash
POST /setup/download_file
```
**Body:** `{"url": "https://example.com/file.txt", "path": "/tmp/file.txt"}`

#### Open File
```bash
POST /setup/open_file
```
**Body:** `{"path": "/home/osworld/document.pdf"}`

---

### 12. **Desktop Customization**

#### Get Desktop Path
```bash
POST /desktop_path
```

#### Get Wallpaper
```bash
POST /wallpaper
```

#### Change Wallpaper
```bash
POST /setup/change_wallpaper
```
**Body:** `{"path": "/path/to/image.jpg"}`

---

### 13. **Recording**

#### Start Recording
```bash
POST /start_recording
```

#### End Recording
```bash
POST /end_recording
```

**Returns:** Video file of the session

---

### 14. **Code Execution**

#### Run Python Code
```bash
POST /run_python
```
**Body:** `{"code": "print('Hello World')"}`

#### Run Bash Script
```bash
POST /run_bash_script
```
**Body:** `{"script": "#!/bin/bash\necho Hello"}`

---

## Common Use Cases

### 1. Open Chrome and Navigate
```bash
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": ["google-chrome", "--new-window", "https://google.com"]
  }'
```

### 2. Take Screenshot Every Second
```bash
for i in {1..10}; do
  curl http://localhost:5000/screenshot -o "screenshot_$i.png"
  sleep 1
done
```

### 3. Find All Open Windows
```bash
curl -s http://localhost:5000/accessibility | \
  python3 -c "
import sys, json
tree = json.load(sys.stdin)
for child in tree.get('children', []):
    if child.get('role') == 'frame':
        print(child.get('name', 'Unnamed window'))
"
```

### 4. Run a Task and Verify
```bash
curl -X POST http://localhost:5000/execute_with_verification \
  -H "Content-Type: application/json" \
  -d '{
    "command": ["touch", "/tmp/testfile"],
    "verification": {
      "type": "file_exists",
      "path": "/tmp/testfile"
    },
    "max_wait_time": 5
  }'
```

---

## Integration with Green Agent

The Green Agent will use these endpoints to:

1. **Launch applications** needed for tasks
2. **Execute actions** (click, type, navigate)
3. **Capture screenshots** for vision-based reasoning
4. **Verify results** using accessibility tree
5. **Record sessions** for debugging

Example workflow:
```python
# 1. Open Chrome
requests.post("http://osworld:5000/execute", json={
    "command": ["google-chrome", "--new-window"]
})

# 2. Take screenshot
img = requests.get("http://osworld:5000/screenshot").content

# 3. Use Claude to analyze screenshot
# 4. Execute next action based on Claude's response

# 5. Verify result
tree = requests.get("http://osworld:5000/accessibility").json()
```

---

## Next Steps

1. **Test all endpoints** - Run `./test_osworld_api.sh`
2. **Create Golden Image** - Snapshot the working VM
3. **Build Orchestrator** - Cloud Run service to manage VMs
4. **Integrate with Green Agent** - Add OSWorld client

---

## Security Notes

⚠️ **Important:**
- This server has NO authentication
- It can execute arbitrary commands
- Only expose on private networks
- Use GCP firewall rules to restrict access
- Consider adding API keys in production

---

## Performance

| Operation | Latency |
|-----------|---------|
| Screenshot | ~100ms |
| Execute command | ~50-500ms |
| Accessibility tree | ~200-500ms |
| Launch app | ~1-3 seconds |

---

## Troubleshooting

### Server not responding
```bash
sudo systemctl status osworld-server
sudo journalctl -u osworld-server -n 50
```

### Display issues
```bash
# Check Xvfb
sudo systemctl status xvfb

# Check display
export DISPLAY=:99
xdpyinfo
```

### Chrome not launching
```bash
# Test Chrome manually
DISPLAY=:99 google-chrome --version
```
