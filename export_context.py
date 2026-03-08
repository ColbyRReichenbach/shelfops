import os
import glob

# The vital files that prove ML logic and domain expertise
TARGET_FILES = [
    "backend/ml/train.py",
    "backend/ml/predict.py",
    "backend/ml/features.py",
    "backend/ml/ghost_stock.py",
    "backend/ml/backroom_trapped.py",
    "backend/alerts/engine.py",
    "README.md",
    "TECHNICAL_README.md",
]

OUTPUT_FILE = "shelfops-landing/codebase_snapshot.md"

def extract_codebase():
    num_files = 0
    total_lines = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        outfile.write("# ShelfOps Codebase Snapshot\n")
        outfile.write("This document contains the critical ML models, execution engines, and architectural readmes for the ShelfOps AI system. It is used as context for the Interactive Codebase Chatbot.\n\n")

        for filepath in TARGET_FILES:
            if not os.path.exists(filepath):
                print(f"Warning: Could not find {filepath}")
                continue
            
            num_files += 1
            outfile.write(f"## File: `{filepath}`\n")
            
            extension = filepath.split(".")[-1]
            if extension == "py":
                language = "python"
            elif extension == "ts":
                language = "typescript"
            elif extension == "tsx":
                language = "tsx"
            elif extension == "md":
                language = "markdown"
            else:
                language = ""

            outfile.write(f"```{language}\n")
            
            with open(filepath, "r", encoding="utf-8") as infile:
                lines = infile.readlines()
                total_lines += len(lines)
                for line in lines:
                    outfile.write(line)
            
            outfile.write("```\n\n---\n\n")

    print(f"✅ Success! Snapshot generated at: {OUTPUT_FILE}")
    print(f"Extracted {num_files} files containing {total_lines} lines of code.")

if __name__ == "__main__":
    print("Extracting AI context payload...")
    extract_codebase()
