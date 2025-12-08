# Week 1: New OSWorld Task Implementation Plan

## Overview

This plan outlines the implementation of 5 new OSWorld tasks, prioritizing low-hanging fruit that reuse existing evaluators and follow established patterns.

| # | Task | Domain | Evaluator | Effort | Priority |
|---|------|--------|-----------|--------|----------|
| 1 | Save Webpage as PDF | chrome | `compare_pdfs` | 4h | High |
| 2 | Create Pie Chart | libreoffice_calc | `compare_table` | 3h | High |
| 3 | Insert Page Break | libreoffice_writer | `compare_docx_files` | 2h | Medium |
| 4 | Enable Desktop Notifications | thunderbird | `check_thunderbird_prefs` | 2h | Medium |
| 5 | Change Default Search Engine | chrome | `check_direct_json_object` | 2h | Medium |

**Total Estimated Effort: ~13 hours**

---

## Task 1: Chrome - Save Webpage as PDF

### Description
Save the current webpage as a PDF file using Chrome's print dialog.

### Task Specification

```json
{
  "id": "NEW-UUID-1",
  "snapshot": "chrome",
  "instruction": "Save this webpage as a PDF file named 'saved_page.pdf' in the Downloads folder.",
  "source": "authors",
  "config": [
    {
      "type": "launch",
      "parameters": {
        "command": ["google-chrome", "--remote-debugging-port=1337"]
      }
    },
    {
      "type": "launch",
      "parameters": {
        "command": ["socat", "tcp-listen:9222,fork", "tcp:localhost:1337"]
      }
    },
    {
      "type": "chrome_open_tabs",
      "parameters": {
        "urls_to_open": ["https://example.com"]
      }
    },
    {
      "type": "activate_window",
      "parameters": {
        "window_name": "Google Chrome"
      }
    }
  ],
  "trajectory": "trajectories/",
  "related_apps": ["chrome"],
  "evaluator": {
    "postconfig": [
      {
        "type": "sleep",
        "parameters": { "seconds": 2 }
      }
    ],
    "func": "compare_pdfs",
    "result": {
      "type": "vm_file",
      "path": "/home/user/Downloads/saved_page.pdf",
      "dest": "saved_page.pdf"
    },
    "expected": {
      "type": "cloud_file",
      "path": "https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/chrome/NEW-UUID-1/example_page_gold.pdf",
      "dest": "example_page_gold.pdf"
    }
  },
  "proxy": false,
  "fixed_ip": false,
  "possibility_of_env_change": "low"
}
```

### Implementation Steps

1. **Create gold standard PDF**
   - Navigate to example.com manually
   - Use Ctrl+P -> Save as PDF with default settings
   - Save as `example_page_gold.pdf`

2. **Upload gold standard to HuggingFace**
   - Upload to `xlangai/ubuntu_osworld_file_cache` dataset
   - Path: `chrome/NEW-UUID-1/example_page_gold.pdf`

3. **Create task JSON file**
   - Generate UUID: `uuidgen`
   - Create file: `green_agent/tasks_config/chrome/{uuid}.json`
   - Use the specification above

4. **Test task**
   - Load task via TaskExecutor
   - Run on VM and verify evaluation works

### Dependencies
- `compare_pdfs` evaluator (exists in `vendor/OSWorld/desktop_env/evaluators/metrics/`)
- HuggingFace dataset access for gold standard upload

---

## Task 2: LibreOffice Calc - Create Pie Chart

### Description
Create a pie chart from spreadsheet data with legend.

### Task Specification

```json
{
  "id": "NEW-UUID-2",
  "snapshot": "libreoffice_calc",
  "instruction": "Create a pie chart from the data in cells A1:B5 showing the sales distribution by category. Include a legend on the right side of the chart.",
  "source": "authors",
  "config": [
    {
      "type": "download",
      "parameters": {
        "files": [
          {
            "url": "https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/libreoffice_calc/NEW-UUID-2/SalesData.xlsx",
            "path": "/home/user/SalesData.xlsx"
          }
        ]
      }
    },
    {
      "type": "open",
      "parameters": {
        "path": "/home/user/SalesData.xlsx"
      }
    }
  ],
  "trajectory": "trajectories/NEW-UUID-2",
  "related_apps": ["libreoffice_calc"],
  "evaluator": {
    "postconfig": [
      {
        "type": "activate_window",
        "parameters": {
          "window_name": "SalesData.xlsx - LibreOffice Calc",
          "strict": true
        }
      },
      {
        "type": "sleep",
        "parameters": { "seconds": 0.5 }
      },
      {
        "type": "execute",
        "parameters": {
          "command": ["python", "-c", "import pyautogui; pyautogui.hotkey('ctrl', 's');"]
        }
      },
      {
        "type": "sleep",
        "parameters": { "seconds": 0.5 }
      }
    ],
    "func": "compare_table",
    "expected": {
      "type": "cloud_file",
      "path": "https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/libreoffice_calc/NEW-UUID-2/SalesData_gold.xlsx",
      "dest": "SalesData_gold.xlsx"
    },
    "result": {
      "type": "vm_file",
      "path": "/home/user/SalesData.xlsx",
      "dest": "SalesData.xlsx"
    },
    "options": {
      "rules": [
        {
          "type": "chart",
          "sheet_idx0": 0,
          "sheet_idx1": "EI0",
          "chart_props": ["type"]
        }
      ]
    }
  },
  "proxy": false,
  "fixed_ip": false,
  "possibility_of_env_change": "low"
}
```

### Implementation Steps

1. **Create source spreadsheet (SalesData.xlsx)**
   ```
   A         B
   Category  Sales
   Food      1500
   Drinks    800
   Snacks    450
   Desserts  350
   ```

2. **Create gold standard with pie chart**
   - Open SalesData.xlsx in LibreOffice Calc
   - Select A1:B5, Insert -> Chart -> Pie Chart
   - Add legend on right
   - Save as SalesData_gold.xlsx

3. **Upload files to HuggingFace**
   - `libreoffice_calc/NEW-UUID-2/SalesData.xlsx` (source)
   - `libreoffice_calc/NEW-UUID-2/SalesData_gold.xlsx` (gold)

4. **Create task JSON file**
   - Generate UUID
   - Create file in `green_agent/tasks_config/libreoffice_calc/`

### Dependencies
- `compare_table` evaluator with chart comparison (exists, used in 6 existing tasks)
- LibreOffice Calc for creating test files

---

## Task 3: LibreOffice Writer - Insert Page Break

### Description
Insert a manual page break between paragraphs in a document.

### Task Specification

```json
{
  "id": "NEW-UUID-3",
  "snapshot": "libreoffice_writer",
  "instruction": "Insert a page break after the first paragraph so that the second paragraph starts on a new page.",
  "source": "authors",
  "config": [
    {
      "type": "download",
      "parameters": {
        "files": [
          {
            "url": "https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/libreoffice_writer/NEW-UUID-3/TwoParagraphs.docx",
            "path": "/home/user/Desktop/TwoParagraphs.docx"
          }
        ]
      }
    },
    {
      "type": "open",
      "parameters": {
        "path": "/home/user/Desktop/TwoParagraphs.docx"
      }
    }
  ],
  "trajectory": "trajectories/NEW-UUID-3",
  "related_apps": ["libreoffice_writer"],
  "evaluator": {
    "postconfig": [
      {
        "type": "activate_window",
        "parameters": {
          "window_name": "TwoParagraphs.docx - LibreOffice Writer",
          "strict": true
        }
      },
      {
        "type": "sleep",
        "parameters": { "seconds": 0.5 }
      },
      {
        "type": "execute",
        "parameters": {
          "command": ["python", "-c", "import pyautogui; import time; pyautogui.hotkey('ctrl', 's'); time.sleep(0.5);"]
        }
      }
    ],
    "func": "compare_docx_files",
    "expected": {
      "type": "cloud_file",
      "path": "https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/libreoffice_writer/NEW-UUID-3/TwoParagraphs_gold.docx",
      "dest": "TwoParagraphs_gold.docx"
    },
    "result": {
      "type": "vm_file",
      "path": "/home/user/Desktop/TwoParagraphs.docx",
      "dest": "TwoParagraphs.docx"
    },
    "options": {
      "check_page_breaks": true
    }
  },
  "proxy": false,
  "fixed_ip": false,
  "possibility_of_env_change": "low"
}
```

### Implementation Steps

1. **Create source document (TwoParagraphs.docx)**
   - Two paragraphs of lorem ipsum text
   - No page breaks

2. **Create gold standard**
   - Open document, place cursor at end of first paragraph
   - Insert -> More Breaks -> Manual Break -> Page Break
   - Save as TwoParagraphs_gold.docx

3. **Upload to HuggingFace**
   - `libreoffice_writer/NEW-UUID-3/TwoParagraphs.docx`
   - `libreoffice_writer/NEW-UUID-3/TwoParagraphs_gold.docx`

4. **Create task JSON**

### Dependencies
- `compare_docx_files` evaluator (exists, heavily used in Writer tasks)
- Need to verify `check_page_breaks` option or use alternative comparison

---

## Task 4: Thunderbird - Enable Desktop Notifications

### Description
Enable desktop notifications for new email arrival in Thunderbird.

### Task Specification

```json
{
  "id": "NEW-UUID-4",
  "snapshot": "thunderbird",
  "instruction": "Enable desktop notifications in Thunderbird so that I receive a notification when new emails arrive.",
  "source": "authors",
  "config": [
    {
      "type": "download",
      "parameters": {
        "files": [
          {
            "url": "https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/thunderbird/dd84e895-72fd-4023-a336-97689ded257c/thunderbird-profile.tar.gz",
            "path": "/home/user/thunderbird-profile.tar.gz"
          }
        ]
      }
    },
    {
      "type": "execute",
      "parameters": {
        "command": [
          "tar", "-xzv", "--recursive-unlink",
          "-f", "/home/user/thunderbird-profile.tar.gz",
          "-C", "/home/user/"
        ]
      }
    },
    {
      "type": "execute",
      "parameters": {
        "command": [
          "bash", "-c",
          "sed -i 's/\"mail.biff.show_alert\", true/\"mail.biff.show_alert\", false/' /home/user/.thunderbird/t5q2a5hp.default-release/prefs.js || echo 'user_pref(\"mail.biff.show_alert\", false);' >> /home/user/.thunderbird/t5q2a5hp.default-release/prefs.js"
        ]
      }
    },
    {
      "type": "launch",
      "parameters": {
        "command": ["/usr/bin/thunderbird"]
      }
    }
  ],
  "trajectory": "trajectories/NEW-UUID-4",
  "related_apps": ["thunderbird"],
  "evaluator": {
    "postconfig": [
      {
        "type": "close_window",
        "parameters": {
          "window_name": "Mail.thunderbird",
          "strict": true,
          "by_class": true
        }
      },
      {
        "type": "sleep",
        "parameters": { "seconds": 0.5 }
      }
    ],
    "func": "check_thunderbird_prefs",
    "result": {
      "type": "vm_file",
      "path": "/home/user/.thunderbird/t5q2a5hp.default-release/prefs.js",
      "dest": "thunder-prefs.js"
    },
    "expected": {
      "type": "rule",
      "rules": {
        "expect": {
          "mail.biff.show_alert": {
            "method": "eq",
            "ref": true
          }
        }
      }
    }
  },
  "proxy": false,
  "fixed_ip": false,
  "possibility_of_env_change": "low"
}
```

### Implementation Steps

1. **Identify notification preference key**
   - `mail.biff.show_alert` = true/false
   - Research other related keys: `mail.biff.play_sound`, `mail.biff.show_tray_icon`

2. **Modify existing profile setup**
   - Reuse existing thunderbird-profile.tar.gz
   - Add command to disable notifications initially (so agent must enable them)

3. **Create task JSON**
   - Use `check_thunderbird_prefs` evaluator
   - Check for `mail.biff.show_alert` = true

### Dependencies
- `check_thunderbird_prefs` evaluator (exists, used in signature task)
- Existing Thunderbird profile can be reused

---

## Task 5: Chrome - Change Default Search Engine

### Description
Change Chrome's default search engine to DuckDuckGo.

### Task Specification

```json
{
  "id": "NEW-UUID-5",
  "snapshot": "chrome",
  "instruction": "Change Chrome's default search engine to DuckDuckGo.",
  "source": "authors",
  "config": [
    {
      "type": "launch",
      "parameters": {
        "command": ["google-chrome", "--remote-debugging-port=1337"]
      }
    },
    {
      "type": "launch",
      "parameters": {
        "command": ["socat", "tcp-listen:9222,fork", "tcp:localhost:1337"]
      }
    },
    {
      "type": "chrome_open_tabs",
      "parameters": {
        "urls_to_open": ["chrome://settings/search"]
      }
    },
    {
      "type": "activate_window",
      "parameters": {
        "window_name": "Google Chrome"
      }
    }
  ],
  "trajectory": "trajectories/NEW-UUID-5",
  "related_apps": ["chrome"],
  "evaluator": {
    "func": "check_chrome_search_engine",
    "result": {
      "type": "chrome_preference",
      "preference_path": "default_search_provider_data.template_url_data.keyword"
    },
    "expected": {
      "type": "rule",
      "rules": {
        "expected": "duckduckgo.com"
      }
    }
  },
  "proxy": false,
  "fixed_ip": false,
  "possibility_of_env_change": "low"
}
```

### Implementation Steps

1. **Research Chrome preference structure**
   - Check `~/.config/google-chrome/Default/Preferences` JSON structure
   - Find exact key for default search engine

2. **Determine evaluator approach**
   - Option A: Use existing `check_direct_json_object` with Chrome prefs file
   - Option B: Create new getter for Chrome preferences
   - Option C: Use URL-based verification (search from address bar)

3. **Create task JSON**
   - May need to adjust evaluator based on Chrome preference investigation

### Dependencies
- Need to verify Chrome preference file location on Ubuntu VM
- May need new getter function or adjust existing evaluator

---

## File Creation Checklist

### Files to Create

| File | Location | Status |
|------|----------|--------|
| Task 1 JSON | `green_agent/tasks_config/chrome/{uuid}.json` | Pending |
| Task 1 Gold PDF | HuggingFace upload | Pending |
| Task 2 JSON | `green_agent/tasks_config/libreoffice_calc/{uuid}.json` | Pending |
| Task 2 Source XLSX | HuggingFace upload | Pending |
| Task 2 Gold XLSX | HuggingFace upload | Pending |
| Task 3 JSON | `green_agent/tasks_config/libreoffice_writer/{uuid}.json` | Pending |
| Task 3 Source DOCX | HuggingFace upload | Pending |
| Task 3 Gold DOCX | HuggingFace upload | Pending |
| Task 4 JSON | `green_agent/tasks_config/thunderbird/{uuid}.json` | Pending |
| Task 5 JSON | `green_agent/tasks_config/chrome/{uuid}.json` | Pending |

### Database Sync
After creating all task files, run:
```bash
python scripts/load_tasks_to_supabase.py
```

---

## Testing Plan

### Per-Task Testing

1. **Load Test**: Verify task loads without errors
   ```python
   from green_agent.a2a.task_executor import TaskExecutor
   executor = TaskExecutor()
   task = executor.load_task('{uuid}')
   print(task)
   ```

2. **Config Test**: Run config steps on VM, verify setup
   ```bash
   curl -X POST http://localhost:5000/setup \
     -H "Content-Type: application/json" \
     -d '{"config": [...]}'
   ```

3. **Evaluation Test**: Run full task with known solution
   - Manually complete task on VM
   - Run evaluator
   - Verify score = 1.0

### Integration Testing

1. Run all 5 tasks through full pipeline
2. Verify database entries created correctly
3. Check WebUI displays new tasks

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| `compare_pdfs` evaluator inconsistent with Chrome versions | Medium | Test on exact VM Chrome version |
| Thunderbird profile version mismatch | Low | Reuse existing working profile |
| Chrome preferences path differs on VM | Medium | SSH to VM and verify path |
| Chart comparison too strict | Medium | Test with flexible options |
| Page break detection not supported | Medium | Research docx structure, may need custom evaluator |

---

## Success Criteria

- [ ] All 5 tasks created and validated
- [ ] All tasks load without errors
- [ ] All tasks pass evaluation when completed correctly
- [ ] Tasks synced to Supabase database
- [ ] Tasks visible in WebUI
- [ ] At least 3/5 tasks achievable by agent within 15 steps

---

## Next Steps (Week 2)

After completing Week 1 tasks:
1. VLC: Load External Subtitles
2. Writer: Set Paragraph Indentation
3. OS: Create Symbolic Links
4. GIMP: Resize Image to Dimensions
5. Impress: Change Text Size

