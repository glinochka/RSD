import os
import re
from collections import defaultdict

versions_dir = "app/alembic/migration/versions"
files_by_id = defaultdict(list)
children = defaultdict(list)

for fn in os.listdir(versions_dir):
    if not fn.endswith(".py") or fn.startswith("__"):
        continue
    path = os.path.join(versions_dir, fn)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r'revision(?:\s*:\s*str)?\s*=\s*["\']([^"\']+)["\']', text)
    if not m:
        continue
    rid = m.group(1)
    files_by_id[rid].append(fn)

    dm = re.search(
        r'down_revision[^=]*=\s*(?:Union\[[^\]]+\]\s*=\s*)?'
        r'(?:\(([^)]+)\)|["\']([^"\']+)["\']|None)',
        text,
    )
    if not dm:
        continue
    if dm.group(2):
        children[dm.group(2)].append(rid)
    elif dm.group(1):
        for part in dm.group(1).split(","):
            children[part.strip().strip('"').strip("'")].append(rid)

print("DUPLICATE REVISION IDS:")
for rid, fns in sorted(files_by_id.items()):
    if len(fns) > 1:
        print(f"  {rid}: {fns}")

all_ids = set(files_by_id.keys())
heads = sorted(rid for rid in all_ids if rid not in children)
print("HEADS:")
for h in heads:
    print(f"  {h} -> {files_by_id[h]}")
