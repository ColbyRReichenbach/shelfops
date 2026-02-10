#!/usr/bin/env python3
"""
OnSuccess Hook: Log successful solutions for future reference

This hook triggers after successful task completion to build a solutions catalog.
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def log_solution(success_data: dict):
    """
    Log successful solution to catalog
    
    Args:
        success_data: Dict with task description, solution, metrics
    """
    project_root = Path(__file__).parent.parent.parent
    solutions_log = project_root / ".claude" / "docs" / "solutions.md"
    
    # Create docs directory if it doesn't exist
    solutions_log.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize file if it doesn't exist
    if not solutions_log.exists():
        solutions_log.write_text("""# Solutions Catalog

Successful patterns and solutions for reuse across sessions.

**Format**:
- Problem: What was trying to be solved
- Solution: How it was solved
- Performance: Metrics if applicable
- When to reuse: Conditions for applying this solution

---

""")
    
    # Extract success details
    task = success_data.get("task", "Unknown task")
    solution_type = success_data.get("type", "General")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if this is worth logging (filter trivial successes)
    trivial_tasks = ["read file", "list directory", "simple query"]
    if any(trivial in task.lower() for trivial in trivial_tasks):
        return {"feedback": "Task too trivial to log", "block": False}
    
    # Format solution entry
    solution_entry = f"""
## Solution: {solution_type}
**Timestamp**: {timestamp}  
**Task**: {task}

**Approach**:
<!-- TODO: Claude should fill this in manually if solution is significant -->

**Performance Metrics**:
<!-- Add metrics if applicable (query time, cost savings, etc.) -->

**Reusability**:
- Conditions: When this pattern applies
- Prerequisites: What's needed to reuse
- Variations: How to adapt for different scenarios

**Status**: ✅ VALIDATED

---

"""
    
    # Append to solutions log
    with open(solutions_log, "a") as f:
        f.write(solution_entry)
    
    return {
        "feedback": "Consider documenting this solution in .claude/docs/solutions.md if reusable",
        "block": False
    }


def main():
    """
    Main hook execution
    """
    try:
        # Read hook input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract success information
        success_info = {
            "task": input_data.get("task", "Unknown task"),
            "type": input_data.get("type", "General")
        }
        
        # Log the solution
        response = log_solution(success_info)
        
        # Return response to Claude
        print(json.dumps(response))
        return 0
        
    except Exception as e:
        # If hook itself fails, return error but don't block
        print(json.dumps({
            "feedback": f"Success logging hook failed: {str(e)}",
            "block": False
        }))
        return 1


if __name__ == "__main__":
    sys.exit(main())
