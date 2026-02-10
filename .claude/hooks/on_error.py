#!/usr/bin/env python3
"""
OnError Hook: Automatically log errors for iterative learning

This hook is triggered whenever Claude encounters an error during tool execution.
It automatically appends the error to .claude/docs/errors.md for future reference.
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def log_error(error_data: dict):
    """
    Log error to persistent error catalog
    
    Args:
        error_data: Dict with error, context, tool_name, etc.
    """
    project_root = Path(__file__).parent.parent.parent
    error_log = project_root / ".claude" / "docs" / "errors.md"
    
    # Create docs directory if it doesn't exist
    error_log.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize file if it doesn't exist
    if not error_log.exists():
        error_log.write_text("# Error Log\n\nAutomatically generated error catalog for iterative learning.\n\n---\n\n")
    
    # Extract error details
    error_msg = error_data.get("error", "Unknown error")
    tool_name = error_data.get("tool", "Unknown tool")
    context = error_data.get("context", "No context provided")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format error entry
    error_entry = f"""
## Error: {tool_name} Failed
**Timestamp**: {timestamp}  
**Tool**: {tool_name}  
**Context**: {context}

**Error Message**:
```
{error_msg}
```

**Initial Analysis**:
- Review this error to determine root cause
- Add solution once identified
- Update prevention strategy

**Status**: 🔴 UNRESOLVED

---

"""
    
    # Append to error log
    with open(error_log, "a") as f:
        f.write(error_entry)
    
    return {
        "feedback": f"Error logged to .claude/docs/errors.md for future reference",
        "block": False
    }


def main():
    """
    Main hook execution
    
    Reads error data from stdin, logs it, returns response
    """
    try:
        # Read hook input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract error information
        error_info = {
            "error": input_data.get("error", "Unknown error"),
            "tool": input_data.get("tool", {}).get("tool", "Unknown tool"),
            "context": input_data.get("context", "No context provided")
        }
        
        # Log the error
        response = log_error(error_info)
        
        # Return response to Claude
        print(json.dumps(response))
        return 0
        
    except Exception as e:
        # If hook itself fails, return error but don't block
        print(json.dumps({
            "feedback": f"Error logging hook failed: {str(e)}",
            "block": False
        }))
        return 1


if __name__ == "__main__":
    sys.exit(main())
