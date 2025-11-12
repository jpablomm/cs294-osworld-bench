# Tool Description Format Specification

**Version:** 1.0
**Date:** November 11, 2025
**Status:** Draft

---

## Overview

This document defines the formal specification for tool descriptions in the Green Agent A2A protocol implementation. Following AgentBeats guidelines, tools are described within task messages (Approach II) to enable self-explanatory assessments.

**Key Principles:**
1. **Self-Explanatory:** Tool descriptions must not expose infrastructure details (VM IPs, ports, internal endpoints)
2. **Standardized Format:** All tools follow consistent JSON Schema structure
3. **Validation-Ready:** Include metadata for parameter validation
4. **Example-Driven:** Provide usage examples in descriptions
5. **Error-Aware:** Define clear error response formats

---

## Tool Description Schema

### Top-Level Structure

```json
{
  "name": "string",
  "description": "string",
  "parameters": {
    "type": "object",
    "properties": { /* ... */ },
    "required": ["array of strings"]
  },
  "returns": {
    "content_type": "string",
    "schema": { /* ... */ },
    "description": "string"
  },
  "examples": [
    { /* ... */ }
  ],
  "validation": {
    "parameter_rules": { /* ... */ }
  },
  "metadata": {
    "category": "string",
    "tags": ["array of strings"]
  }
}
```

### Field Definitions

#### `name` (required)
- **Type:** `string`
- **Pattern:** `^[a-z][a-z0-9_]*$` (snake_case)
- **Description:** Unique identifier for the tool
- **Examples:** `"screenshot"`, `"click"`, `"type_text"`

#### `description` (required)
- **Type:** `string`
- **Min Length:** 10 characters
- **Max Length:** 500 characters
- **Description:** Human-readable explanation of what the tool does
- **Guidelines:**
  - Start with a verb (e.g., "Capture", "Execute", "Type")
  - Describe purpose, not implementation
  - Avoid infrastructure details (no IPs, ports, endpoints)
  - Include use case hints

**Good Example:**
```
"Capture a screenshot of the current desktop state. Use this to observe what's visible on the screen before and after actions."
```

**Bad Example:**
```
"Calls http://10.128.0.10:5000/screenshot endpoint to get PNG image via OSWorld REST API"
```

#### `parameters` (required)
- **Type:** `object` (JSON Schema draft-07)
- **Required Fields:**
  - `type`: Must be `"object"`
  - `properties`: Object mapping parameter names to schemas
  - `required`: Array of required parameter names
- **Description:** Defines the input parameters for the tool

**Parameter Property Schema:**
```json
{
  "type": "string|number|integer|boolean|array|object",
  "description": "string",
  "default": "any (optional)",
  "enum": ["array of allowed values (optional)"],
  "minimum": "number (for numeric types)",
  "maximum": "number (for numeric types)",
  "minLength": "integer (for strings)",
  "maxLength": "integer (for strings)",
  "pattern": "string (regex for strings)",
  "items": { /* schema for array items */ }
}
```

#### `returns` (required)
- **Type:** `object`
- **Description:** Specifies the return value format

**Return Value Schema:**
```json
{
  "content_type": "application/json|image/png|text/plain",
  "schema": {
    "type": "object|string|array|...",
    "properties": { /* ... for objects */ }
  },
  "description": "Human-readable description of return value",
  "status_codes": {
    "200": "Success description",
    "400": "Bad request description",
    "500": "Server error description"
  }
}
```

#### `examples` (recommended)
- **Type:** `array` of example objects
- **Description:** Demonstrates proper tool usage

**Example Object Schema:**
```json
{
  "description": "Brief description of what this example does",
  "input": {
    /* parameter values */
  },
  "output": {
    /* expected return value */
  }
}
```

#### `validation` (optional)
- **Type:** `object`
- **Description:** Additional validation rules beyond JSON Schema

**Validation Rules Schema:**
```json
{
  "parameter_rules": {
    "<param_name>": {
      "validator": "coordinate|text|key|number|custom",
      "bounds": {
        "min": "number",
        "max": "number"
      },
      "allowed_values": ["array"],
      "custom_validator": "function name"
    }
  }
}
```

#### `metadata` (optional)
- **Type:** `object`
- **Description:** Classification and discovery metadata

```json
{
  "category": "observation|action|control|utility",
  "tags": ["mouse", "keyboard", "screen", "etc"],
  "complexity": "simple|moderate|complex",
  "safety_level": "safe|caution|requires_validation"
}
```

---

## Complete Tool Examples

### Example 1: Screenshot (Observation Tool)

```json
{
  "name": "screenshot",
  "description": "Capture a screenshot of the current desktop state. Use this to observe what's visible on the screen before deciding on actions.",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": []
  },
  "returns": {
    "content_type": "image/png",
    "schema": {
      "type": "string",
      "format": "binary"
    },
    "description": "PNG image of the desktop (base64-encoded in JSON responses)",
    "status_codes": {
      "200": "Screenshot captured successfully",
      "500": "Failed to capture screenshot (display not available)"
    }
  },
  "examples": [
    {
      "description": "Capture current screen state",
      "input": {},
      "output": {
        "status": "success",
        "image": "<base64-encoded PNG data>",
        "timestamp": "2025-11-11T10:30:00Z"
      }
    }
  ],
  "validation": {
    "parameter_rules": {}
  },
  "metadata": {
    "category": "observation",
    "tags": ["screen", "vision", "observation"],
    "complexity": "simple",
    "safety_level": "safe"
  }
}
```

### Example 2: Click (Action Tool)

```json
{
  "name": "click",
  "description": "Perform a mouse click at specific screen coordinates. Typical screen resolution is 1920x1080 pixels, with (0,0) at the top-left corner.",
  "parameters": {
    "type": "object",
    "properties": {
      "x": {
        "type": "integer",
        "description": "Horizontal position in pixels from left edge (0-1920)",
        "minimum": 0,
        "maximum": 1920
      },
      "y": {
        "type": "integer",
        "description": "Vertical position in pixels from top edge (0-1080)",
        "minimum": 0,
        "maximum": 1080
      },
      "button": {
        "type": "string",
        "description": "Mouse button to click",
        "enum": ["left", "right", "middle"],
        "default": "left"
      },
      "clicks": {
        "type": "integer",
        "description": "Number of clicks (1 for single, 2 for double)",
        "minimum": 1,
        "maximum": 3,
        "default": 1
      }
    },
    "required": ["x", "y"]
  },
  "returns": {
    "content_type": "application/json",
    "schema": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "enum": ["success", "error"]
        },
        "message": {
          "type": "string"
        }
      }
    },
    "description": "Confirmation of click execution",
    "status_codes": {
      "200": "Click executed successfully",
      "400": "Invalid coordinates or parameters",
      "500": "Failed to execute click (desktop environment error)"
    }
  },
  "examples": [
    {
      "description": "Single left-click at center of 1920x1080 screen",
      "input": {
        "x": 960,
        "y": 540,
        "button": "left"
      },
      "output": {
        "status": "success",
        "message": "Clicked left button at (960, 540)"
      }
    },
    {
      "description": "Double-click on a file icon",
      "input": {
        "x": 150,
        "y": 200,
        "button": "left",
        "clicks": 2
      },
      "output": {
        "status": "success",
        "message": "Double-clicked left button at (150, 200)"
      }
    }
  ],
  "validation": {
    "parameter_rules": {
      "x": {
        "validator": "coordinate",
        "bounds": {"min": 0, "max": 1920}
      },
      "y": {
        "validator": "coordinate",
        "bounds": {"min": 0, "max": 1080}
      },
      "button": {
        "validator": "enum",
        "allowed_values": ["left", "right", "middle"]
      },
      "clicks": {
        "validator": "number",
        "bounds": {"min": 1, "max": 3}
      }
    }
  },
  "metadata": {
    "category": "action",
    "tags": ["mouse", "click", "interaction"],
    "complexity": "simple",
    "safety_level": "safe"
  }
}
```

### Example 3: Type Text (Action Tool)

```json
{
  "name": "type_text",
  "description": "Type text using keyboard input. The text will be entered at the current cursor position. Use this for filling forms, entering search queries, or writing text.",
  "parameters": {
    "type": "object",
    "properties": {
      "text": {
        "type": "string",
        "description": "Text to type (supports alphanumeric, spaces, and common punctuation)",
        "minLength": 1,
        "maxLength": 10000
      },
      "delay": {
        "type": "number",
        "description": "Delay in seconds between keystrokes (0 for instant typing)",
        "minimum": 0,
        "maximum": 1.0,
        "default": 0.05
      }
    },
    "required": ["text"]
  },
  "returns": {
    "content_type": "application/json",
    "schema": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "enum": ["success", "error"]
        },
        "characters_typed": {
          "type": "integer"
        },
        "message": {
          "type": "string"
        }
      }
    },
    "description": "Confirmation of text entry",
    "status_codes": {
      "200": "Text typed successfully",
      "400": "Invalid text parameter (empty, too long, or unsupported characters)",
      "500": "Failed to type text (keyboard input error)"
    }
  },
  "examples": [
    {
      "description": "Type a search query",
      "input": {
        "text": "machine learning papers"
      },
      "output": {
        "status": "success",
        "characters_typed": 24,
        "message": "Successfully typed 24 characters"
      }
    },
    {
      "description": "Fill a form field with email",
      "input": {
        "text": "user@example.com",
        "delay": 0.1
      },
      "output": {
        "status": "success",
        "characters_typed": 16,
        "message": "Successfully typed 16 characters with 0.1s delay"
      }
    }
  ],
  "validation": {
    "parameter_rules": {
      "text": {
        "validator": "text",
        "bounds": {"min": 1, "max": 10000}
      },
      "delay": {
        "validator": "number",
        "bounds": {"min": 0, "max": 1.0}
      }
    }
  },
  "metadata": {
    "category": "action",
    "tags": ["keyboard", "text", "input"],
    "complexity": "simple",
    "safety_level": "safe"
  }
}
```

### Example 4: Hotkey (Action Tool)

```json
{
  "name": "hotkey",
  "description": "Press a keyboard hotkey combination (e.g., Ctrl+C for copy, Alt+Tab to switch windows). Common modifiers: ctrl, alt, shift, cmd/win.",
  "parameters": {
    "type": "object",
    "properties": {
      "keys": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "description": "List of keys to press together. First keys are modifiers (ctrl, alt, shift), last key is the action key (c, v, tab, etc.)",
        "minItems": 1,
        "maxItems": 4
      }
    },
    "required": ["keys"]
  },
  "returns": {
    "content_type": "application/json",
    "schema": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "enum": ["success", "error"]
        },
        "keys_pressed": {
          "type": "array",
          "items": {"type": "string"}
        },
        "message": {
          "type": "string"
        }
      }
    },
    "description": "Confirmation of hotkey execution",
    "status_codes": {
      "200": "Hotkey pressed successfully",
      "400": "Invalid key combination or unrecognized keys",
      "500": "Failed to press hotkey (keyboard error)"
    }
  },
  "examples": [
    {
      "description": "Copy text (Ctrl+C)",
      "input": {
        "keys": ["ctrl", "c"]
      },
      "output": {
        "status": "success",
        "keys_pressed": ["ctrl", "c"],
        "message": "Successfully pressed ctrl+c"
      }
    },
    {
      "description": "Switch window (Alt+Tab)",
      "input": {
        "keys": ["alt", "tab"]
      },
      "output": {
        "status": "success",
        "keys_pressed": ["alt", "tab"],
        "message": "Successfully pressed alt+tab"
      }
    },
    {
      "description": "Save file (Ctrl+Shift+S)",
      "input": {
        "keys": ["ctrl", "shift", "s"]
      },
      "output": {
        "status": "success",
        "keys_pressed": ["ctrl", "shift", "s"],
        "message": "Successfully pressed ctrl+shift+s"
      }
    }
  ],
  "validation": {
    "parameter_rules": {
      "keys": {
        "validator": "keys",
        "allowed_values": [
          "ctrl", "alt", "shift", "cmd", "win",
          "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
          "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
          "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
          "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
          "enter", "tab", "space", "backspace", "delete", "escape",
          "up", "down", "left", "right",
          "home", "end", "pageup", "pagedown"
        ]
      }
    }
  },
  "metadata": {
    "category": "action",
    "tags": ["keyboard", "hotkey", "shortcut"],
    "complexity": "moderate",
    "safety_level": "safe"
  }
}
```

### Example 5: Execute Python (Complex Tool)

```json
{
  "name": "execute_python",
  "description": "Execute Python code in the desktop environment. Use for complex automation tasks that require logic, loops, or API calls. The code runs with desktop automation libraries available (pyautogui, subprocess, etc.).",
  "parameters": {
    "type": "object",
    "properties": {
      "code": {
        "type": "string",
        "description": "Python code to execute. Must be valid Python 3 syntax.",
        "minLength": 1,
        "maxLength": 50000
      },
      "timeout": {
        "type": "number",
        "description": "Maximum execution time in seconds",
        "minimum": 1,
        "maximum": 300,
        "default": 30
      }
    },
    "required": ["code"]
  },
  "returns": {
    "content_type": "application/json",
    "schema": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "enum": ["success", "error", "timeout"]
        },
        "stdout": {
          "type": "string",
          "description": "Standard output from the code"
        },
        "stderr": {
          "type": "string",
          "description": "Standard error output (if any)"
        },
        "exit_code": {
          "type": "integer"
        },
        "execution_time": {
          "type": "number",
          "description": "Time taken in seconds"
        },
        "message": {
          "type": "string"
        }
      }
    },
    "description": "Execution result with stdout, stderr, and status",
    "status_codes": {
      "200": "Code executed (check exit_code for success)",
      "400": "Invalid Python code or parameters",
      "408": "Execution timeout exceeded",
      "500": "Execution environment error"
    }
  },
  "examples": [
    {
      "description": "Print hello world",
      "input": {
        "code": "print('Hello, World!')"
      },
      "output": {
        "status": "success",
        "stdout": "Hello, World!\n",
        "stderr": "",
        "exit_code": 0,
        "execution_time": 0.05,
        "message": "Code executed successfully"
      }
    },
    {
      "description": "Click multiple buttons in sequence",
      "input": {
        "code": "import pyautogui\nimport time\n\nfor i in range(3):\n    pyautogui.click(100 + i*50, 200)\n    time.sleep(0.5)\n\nprint('Clicked 3 buttons')"
      },
      "output": {
        "status": "success",
        "stdout": "Clicked 3 buttons\n",
        "stderr": "",
        "exit_code": 0,
        "execution_time": 1.52,
        "message": "Code executed successfully"
      }
    }
  ],
  "validation": {
    "parameter_rules": {
      "code": {
        "validator": "text",
        "bounds": {"min": 1, "max": 50000}
      },
      "timeout": {
        "validator": "number",
        "bounds": {"min": 1, "max": 300}
      }
    }
  },
  "metadata": {
    "category": "action",
    "tags": ["python", "automation", "advanced"],
    "complexity": "complex",
    "safety_level": "requires_validation"
  }
}
```

---

## Error Response Format

All tools should return errors in a consistent format:

```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR|EXECUTION_ERROR|TIMEOUT|INTERNAL_ERROR",
  "message": "Human-readable error description",
  "details": {
    "parameter": "name of problematic parameter (if applicable)",
    "value": "problematic value (if applicable)",
    "constraint": "violated constraint (if applicable)"
  },
  "timestamp": "2025-11-11T10:30:00Z"
}
```

### Standard Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid parameter value or type |
| `MISSING_PARAMETER` | 400 | Required parameter not provided |
| `EXECUTION_ERROR` | 500 | Tool execution failed |
| `TIMEOUT` | 408 | Execution exceeded time limit |
| `INTERNAL_ERROR` | 500 | Unexpected system error |
| `RESOURCE_UNAVAILABLE` | 503 | Required resource not available (e.g., display) |

### Error Examples

**Validation Error:**
```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "X coordinate out of bounds",
  "details": {
    "parameter": "x",
    "value": 2500,
    "constraint": "Must be between 0 and 1920"
  },
  "timestamp": "2025-11-11T10:30:00Z"
}
```

**Execution Error:**
```json
{
  "status": "error",
  "error_code": "EXECUTION_ERROR",
  "message": "Failed to execute click action",
  "details": {
    "reason": "Desktop environment not responding",
    "attempted_action": "click(960, 540)"
  },
  "timestamp": "2025-11-11T10:30:00Z"
}
```

---

## Tool Message Format

When embedding tools in A2A task messages, use this format:

```markdown
# Available Tools

You have access to the following tools for completing this task:

## tool_name_1

<Brief description>

**Parameters:**
- `param1` (type, required): Description
- `param2` (type, optional): Description. Default: value

**Returns:** <Return description>

**Example:**
```json
{
  "tool": "tool_name_1",
  "parameters": {
    "param1": "value"
  }
}
```

## tool_name_2

...

# Task

<Task instruction>

**Format:** Return your actions in JSON format with `tool` and `parameters` fields.
```

### Complete Message Example

```markdown
# Available Tools

You have access to the following tools for desktop automation:

## screenshot

Capture a screenshot of the current desktop state. Use this to observe what's visible on the screen before deciding on actions.

**Parameters:** None

**Returns:** PNG image of the desktop

**Example:**
```json
{"tool": "screenshot", "parameters": {}}
```

## click

Perform a mouse click at specific screen coordinates. Typical screen resolution is 1920x1080 pixels.

**Parameters:**
- `x` (integer, required): Horizontal position in pixels (0-1920)
- `y` (integer, required): Vertical position in pixels (0-1080)
- `button` (string, optional): Mouse button. Default: "left"

**Returns:** Confirmation of click execution

**Example:**
```json
{"tool": "click", "parameters": {"x": 960, "y": 540, "button": "left"}}
```

## type_text

Type text using keyboard input at the current cursor position.

**Parameters:**
- `text` (string, required): Text to type

**Returns:** Confirmation with character count

**Example:**
```json
{"tool": "type_text", "parameters": {"text": "Hello World"}}
```

# Task

Open the Chrome browser and navigate to google.com

**Format:** Return your actions in JSON format with `tool` and `parameters` fields as shown in the examples above.
```

---

## Validation Rules

### Parameter Validation

Each tool parameter must be validated before execution:

1. **Type Validation:** Ensure parameter matches declared type
2. **Required Validation:** All required parameters must be present
3. **Bounds Validation:** Numeric values within min/max ranges
4. **Enum Validation:** String values in allowed enum list
5. **Pattern Validation:** String values match regex pattern
6. **Custom Validation:** Additional domain-specific checks

### Implementation Example

```python
def validate_tool_call(tool_spec: dict, parameters: dict) -> tuple[bool, Optional[str]]:
    """
    Validate tool call parameters against tool specification

    Returns: (is_valid, error_message)
    """
    # Check required parameters
    required = tool_spec['parameters'].get('required', [])
    for param in required:
        if param not in parameters:
            return False, f"Missing required parameter: {param}"

    # Validate each parameter
    properties = tool_spec['parameters'].get('properties', {})
    for param_name, param_value in parameters.items():
        if param_name not in properties:
            return False, f"Unknown parameter: {param_name}"

        spec = properties[param_name]

        # Type validation
        expected_type = spec['type']
        if not _check_type(param_value, expected_type):
            return False, f"Parameter {param_name} must be {expected_type}"

        # Bounds validation
        if expected_type in ['number', 'integer']:
            if 'minimum' in spec and param_value < spec['minimum']:
                return False, f"Parameter {param_name} below minimum {spec['minimum']}"
            if 'maximum' in spec and param_value > spec['maximum']:
                return False, f"Parameter {param_name} above maximum {spec['maximum']}"

        # Enum validation
        if 'enum' in spec and param_value not in spec['enum']:
            return False, f"Parameter {param_name} must be one of {spec['enum']}"

    return True, None
```

---

## Best Practices

### DO:
- ✅ Use descriptive, verb-based tool names
- ✅ Provide clear, concise descriptions without infrastructure details
- ✅ Include practical examples for each tool
- ✅ Define comprehensive parameter schemas with bounds
- ✅ Specify return value formats and status codes
- ✅ Add validation metadata for all parameters
- ✅ Use consistent error response format
- ✅ Tag tools by category and complexity
- ✅ Document default values for optional parameters

### DON'T:
- ❌ Expose VM IPs, ports, or internal endpoints
- ❌ Reference implementation details (OSWorld, REST APIs)
- ❌ Use vague descriptions ("do something", "run action")
- ❌ Omit parameter validation rules
- ❌ Return inconsistent error formats
- ❌ Forget examples for complex tools
- ❌ Use overly technical jargon
- ❌ Create tools without clear use cases

---

## Migration Guide

To update existing tool descriptions to this specification:

1. **Remove Infrastructure Details:**
   ```python
   # BEFORE:
   "endpoint": f"http://{vm_ip}:5000/screenshot"

   # AFTER:
   # Remove endpoint field entirely (internal implementation detail)
   ```

2. **Add Return Value Specification:**
   ```python
   # BEFORE:
   "returns": "PNG image (binary)"

   # AFTER:
   "returns": {
       "content_type": "image/png",
       "schema": {"type": "string", "format": "binary"},
       "description": "PNG image of the desktop",
       "status_codes": {
           "200": "Screenshot captured successfully",
           "500": "Failed to capture screenshot"
       }
   }
   ```

3. **Add Examples:**
   ```python
   "examples": [
       {
           "description": "Basic screenshot",
           "input": {},
           "output": {"status": "success", "image": "<base64>"}
       }
   ]
   ```

4. **Add Validation Metadata:**
   ```python
   "validation": {
       "parameter_rules": {
           "x": {
               "validator": "coordinate",
               "bounds": {"min": 0, "max": 1920}
           }
       }
   }
   ```

5. **Add Metadata:**
   ```python
   "metadata": {
       "category": "observation",
       "tags": ["screen", "vision"],
       "complexity": "simple",
       "safety_level": "safe"
   }
   ```

---

## Compliance Checklist

- [ ] All tools follow JSON Schema structure
- [ ] No infrastructure details (IPs, ports) in descriptions
- [ ] Return value formats specified with content types
- [ ] Examples provided for all tools
- [ ] Validation metadata added for parameters
- [ ] Error responses follow standard format
- [ ] Tools tagged by category and complexity
- [ ] Parameter bounds clearly defined
- [ ] Required vs optional parameters marked
- [ ] Default values documented

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-11 | Initial specification created |

---

## References

- [AgentBeats Guidelines](https://agentbeats.org)
- [JSON Schema Draft-07](https://json-schema.org/draft-07/schema)
- [A2A Protocol Specification](../README.md)
- [OSWorld Documentation](https://github.com/xlang-ai/OSWorld)
