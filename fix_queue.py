import os
import re

matched_files = []
for root, _, files in os.walk("."):
    if any(p in root for p in [".git", "venv", ".venv", "__pycache__", "env"]):
        continue
    for file in files:
        if file.endswith(".py") and file != "fix_queue.py":
            matched_files.append(os.path.join(root, file))

modified_count = 0

for file_path in matched_files:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = content

    # Fix 1: range(patients_waiting + 1) -> range(1, patients_waiting + 1)
    new_content = re.sub(
        r'range\(\s*([a-zA-Z0-9_]*patients_waiting[a-zA-Z0-9_]*)\s*\+\s*1\s*\)',
        r'range(1, \1 + 1)',
        new_content
    )

    # Fix 2: range(0, patients_waiting + 1) -> range(1, patients_waiting + 1)
    new_content = re.sub(
        r'range\(\s*0\s*,\s*([a-zA-Z0-9_]*patients_waiting[a-zA-Z0-9_]*)\s*\+\s*1\s*\)',
        r'range(1, \1 + 1)',
        new_content
    )

    # Fix 3: range(0, patients_waiting) -> range(1, patients_waiting + 1)
    new_content = re.sub(
        r'range\(\s*0\s*,\s*([a-zA-Z0-9_]*patients_waiting[a-zA-Z0-9_]*)\s*\)',
        r'range(1, \1 + 1)',
        new_content
    )

    # Fix 4: range(patients_waiting) -> range(1, patients_waiting + 1)
    new_content = re.sub(
        r'range\(\s*([a-zA-Z0-9_]*patients_waiting[a-zA-Z0-9_]*)\s*\)',
        r'range(1, \1 + 1)',
        new_content
    )

    # Fix 5: Replace queue position index assignment
    new_content = re.sub(
        r'\[[\'"]Queue Position[\'"]\]\s*=\s*([a-zA-Z0-9_]+)\.index\b',
        r'[\'Queue Position\'] = range(1, len(\1) + 1)',
        new_content
    )

    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Patched queue indexing in: {file_path}")
        modified_count += 1

if modified_count == 0:
    print("No automated pattern match. Checking manual files next.")
else:
    print(f"Successfully updated {modified_count} file(s)!")

if os.path.exists("fix_queue.py"):
    os.remove("fix_queue.py")
