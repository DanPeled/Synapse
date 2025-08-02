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
print("✅ Moved files to 'out/synapse_ui/':")

# Create __init__.py
init_path = os.path.join(destination, "__init__.py")
with open(init_path, "w"):
    pass

print("✅ Created __init__.py in 'out/synapse_ui/'")
