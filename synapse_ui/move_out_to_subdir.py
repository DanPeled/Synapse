# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import shutil

source = "out"
destination = os.path.join(source, "synapse_ui")

# Ensure destination exists
os.makedirs(destination, exist_ok=True)

moved_items = []

# Move all items except the destination folder itself
for item in os.listdir(source):
    src_path = os.path.join(source, item)
    dst_path = os.path.join(destination, item)

    if os.path.abspath(src_path) == os.path.abspath(destination):
        continue

    shutil.move(src_path, dst_path)
    moved_items.append(item)
try:
    print("✅ Moved files to 'out/synapse_ui/'")
except UnicodeEncodeError:
    print("[OK] Moved files to 'out/synapse_ui/'")

# Create __init__.py
init_path = os.path.join(destination, "__init__.py")
with open(init_path, "w"):
    pass

try:
    print("✅ Created __init__.py in 'out/synapse_ui/'")
except UnicodeEncodeError:
    print("[OK] Created __init__.py in 'out/synapse_ui/'")
