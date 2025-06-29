
import os
import json
from collections import Counter

def generate_configs(pred_label_dir, output_dir="tower_configs"):
    os.makedirs(output_dir, exist_ok=True)

    for fname in os.listdir(pred_label_dir):
        if not fname.endswith(".txt"):
            continue

        antenna_counts = Counter({"A": 0, "B": 0, "C": 0})
        with open(os.path.join(pred_label_dir, fname), 'r') as f:
            for line in f:
                cls_id = int(line.strip().split()[0])
                if cls_id == 0:
                    antenna_counts["A"] += 1
                elif cls_id == 1:
                    antenna_counts["B"] += 1
                elif cls_id == 2:
                    antenna_counts["C"] += 1

        config = {
            "pole_height": 20,
            "pole_radius": 0.1,
            "antenna_height": 0.2,
            "antenna_distance_from_pole": 1.4,
            "antennas": dict(antenna_counts)
        }

        json_name = os.path.join(output_dir, f"TOWER_CONFIG_{fname.replace('.txt', '.json')}")
        with open(json_name, "w") as out:
            json.dump(config, out, indent=2)
        print(f"Generated {json_name}")

if __name__ == "__main__":
    generate_configs("runs/detect/predict/labels")
