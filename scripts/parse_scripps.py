"""
parse_scripps.py
Reads all AWN CSV files from the Scripps zip and outputs:
  - data/awn_events.json  (all rows, daytime only, solar > 50 W/m²)
  - data/demo_replay.json (held-out Aug 14-15 window for live demo)

Column indices in the AWN CSVs (0-based):
  0  Date (ISO timestamp with TZ)
  2  Outdoor Temperature (°F)
  4  Wind Speed (mph)
  7  Wind Direction (°)
  15 Humidity (%)
  16 UV Index
  17 Solar Radiation (W/m²)
"""

import zipfile
import json
import csv
import io
from pathlib import Path
from datetime import datetime, timezone
import pytz

ZIP_PATH   = r"C:\Users\ethan\Downloads\UCSD_Heat_Mapping-20260418T203718Z-3-001.zip"
OUT_DIR    = Path(r"C:\Users\ethan\solarsentinel\data")
OUT_DIR.mkdir(exist_ok=True)

# The AWN station is at UCSD — Pacific time
PT = pytz.timezone("America/Los_Angeles")

# Held-out file for demo replay (Aug 14-15 has max solar 874.5 W/m²)
DEMO_FILE = "UCSD_Heat_Mapping/AWN/AWN-84F3EB5450ED-20250814-20250815.csv"

# Only keep readings with solar > 50 W/m² (daytime)
SOLAR_FLOOR = 50.0

def parse_awn_csv(content_bytes: bytes, filename: str) -> list[dict]:
    """Parse one AWN CSV file and return list of event dicts."""
    events = []
    text = content_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header = next(reader)  # skip header row

    for row in reader:
        if len(row) < 18:
            continue
        try:
            solar = float(row[17])
        except ValueError:
            continue

        if solar < SOLAR_FLOOR:
            continue  # nighttime or near-zero — skip

        try:
            ts_raw = row[0].strip().strip('"')
            # ISO format: 2025-08-14T14:50:00-07:00
            ts = datetime.fromisoformat(ts_raw)
            ts_utc = ts.astimezone(timezone.utc)
            ts_str = ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            hour_local = ts.hour
            month      = ts.month
        except Exception:
            continue

        try:
            event = {
                "timestamp":           ts_str,
                "hour_local":          hour_local,
                "month":               month,
                "solar_radiation_wm2": solar,
                "outdoor_temp_f":      float(row[2]),
                "humidity_pct":        float(row[15]),
                "uv_index":            float(row[16]),
                "wind_speed_mph":      float(row[4]),
                "source_file":         filename.split("/")[-1],
            }
            events.append(event)
        except (ValueError, IndexError):
            continue

    return events


def main():
    all_events   = []
    demo_events  = []

    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        awn_files = [n for n in zf.namelist()
                     if "AWN/" in n and n.endswith(".csv")]

        for fname in sorted(awn_files):
            with zf.open(fname) as f:
                raw = f.read()

            events = parse_awn_csv(raw, fname)
            print(f"  {fname.split('/')[-1]:45s}  {len(events):>4d} daytime rows")

            if fname == DEMO_FILE:
                demo_events = events   # held out — not used for training
            else:
                all_events.extend(events)

    # Sort by timestamp ascending (oldest first for training)
    all_events.sort(key=lambda e: e["timestamp"])

    # Save training set
    train_path = OUT_DIR / "awn_events.json"
    with open(train_path, "w") as f:
        json.dump(all_events, f, indent=2)
    print(f"\nTraining events saved  -> {train_path}  ({len(all_events)} rows)")

    # Save demo replay set (Aug 14-15, reversed -> chronological for replay)
    demo_events.sort(key=lambda e: e["timestamp"])
    demo_path = OUT_DIR / "demo_replay.json"
    with open(demo_path, "w") as f:
        json.dump(demo_events, f, indent=2)
    print(f"Demo replay events     -> {demo_path}  ({len(demo_events)} rows)")


if __name__ == "__main__":
    main()
