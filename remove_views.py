import os

filepath = r"templates\index.html"
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Remove lines containing the old creator views
# They start around line 180 "<!-- ========== TALLER DE ESCENAS ========== -->"
# and end before "<audio id="menu-music""

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if "<!-- ========== TALLER DE ESCENAS ========== -->" in line:
        start_idx = i
    if "<audio id=\"menu-music\"" in line:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    new_lines = lines[:start_idx] + lines[end_idx:]
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Old creator views removed successfully.")
else:
    print("Could not find bounds for old creator views.")
