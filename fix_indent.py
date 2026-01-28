import os

path = r"d:\Yt_bot\story_shorts_mgr.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
concat_found = False

for i, line in enumerate(lines):
    # Stop processing at main block
    if line.startswith('if __name__ == "__main__":'):
        concat_found = False
        new_lines.append(line)
        continue
        
    # Detect start of Concatenation block
    if "# 3. Concatenate All" in line:
        concat_found = True
        
    if concat_found:
        stripped = line.strip()
        
        # Check for orphan except block (lines 1138-1142 in Read output)
        if stripped.startswith("except Exception as e:") and line.startswith("    except"):
             skip = True
             continue
        
        if skip:
             if stripped == "return None":
                 skip = False
             continue
             
        if stripped == "finally:" and line.startswith("    finally:"):
             continue # Skip finally line
             
        # Dedent by 4 spaces if it starts with 8 spaces
        if line.startswith("        "):
            new_lines.append(line[4:])
        else:
             # Empty lines or lines with less indentation (shouldn't happen for body)
             new_lines.append(line)
    else:
        new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Fix applied.")
