import json
from pathlib import Path
data_file = f"test.json"
data = {}
if Path(data_file).exists():
    import json
    with open(data_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
print(data)
print(data["1"])