"""Fix the INSERT statement in snapshot_dao.py to have correct number of placeholders."""

import re

with open('dao/snapshot_dao.py', 'r') as f:
    content = f.read()

# Find the INSERT VALUES line and fix the question mark count
# Current: 31 question marks, need 33 for 33 columns
old_pattern = r"VALUES \((\?,\s*){30}\?\)"
new_values = "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"

content = re.sub(old_pattern, new_values, content)

with open('dao/snapshot_dao.py', 'w') as f:
    f.write(content)

print("Fixed INSERT statement in snapshot_dao.py")
