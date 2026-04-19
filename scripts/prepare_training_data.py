"""
prepare_training_data.py
Joins Scripps AWN weather events with ZenPower permit specs to produce
a training CSV for the SageMaker XGBoost model.

Physics model for expected kWh per 5-minute interval:
  power_kw = (solar_wm2 / 1000) * system_size_dc_kw
             * panel_efficiency(temp_f)
             * tilt_correction(tilt_deg, azimuth_deg, hour, month)
  kwh_5min = power_kw * (5/60)

Then we add ±4% Gaussian noise to simulate real-world variance (clouds,
dust, wiring losses) so the model learns to predict the noisy reality.

For the held-out demo replay (demo_replay.json) we ALSO write
data/demo_events_with_fault.json where install ZP-0014 has its
actual_kwh degraded by 24% during hours 12–16 (simulating a soiled panel
or shading event). This is the fault the WebSocket alert will catch live.

Output files:
  data/training.csv           — for SageMaker training job
  data/demo_events_with_fault.json — for demo_replayer Lambda
"""

import json
import csv
import math
import random
from pathlib import Path

random.seed(7)

DATA_DIR = Path(r"C:\Users\ethan\solarsentinel\data")

AWN_EVENTS   = DATA_DIR / "awn_events.json"
DEMO_EVENTS  = DATA_DIR / "demo_replay.json"
PERMITS_CSV  = DATA_DIR / "zenpower_permits.csv"
TRAIN_OUT    = DATA_DIR / "training.csv"
DEMO_OUT     = DATA_DIR / "demo_events_with_fault.json"

# Permit that will "fail" during demo
FAULT_PERMIT  = "ZP-0014"
FAULT_HOURS   = range(12, 17)   # noon–5 pm local
FAULT_FACTOR  = 0.76            # 24% degradation

PANEL_EFF_BASE = 0.198          # 19.8% at STC (25°C / 77°F)
TEMP_COEFF     = -0.0035        # -0.35%/°C power loss above STC
STC_TEMP_F     = 77.0

def panel_efficiency(temp_f: float) -> float:
    """Temperature-corrected panel efficiency."""
    delta_c = (temp_f - STC_TEMP_F) * (5/9)
    eff = PANEL_EFF_BASE * (1 + TEMP_COEFF * delta_c)
    return max(0.10, min(0.22, eff))


def tilt_correction(tilt_deg: int, azimuth_deg: int,
                    hour: int, month: int) -> float:
    """
    Simplified tilt/azimuth correction factor (0.75–1.05).
    Peak around solar noon (12-14h), south-facing (180°).
    """
    # Hour angle: 0 at noon
    hour_angle = abs(hour - 13)
    time_factor = max(0.0, 1.0 - hour_angle * 0.08)

    # Azimuth penalty: cos(azimuth - 180) / 1
    az_rad = math.radians(azimuth_deg - 180)
    az_factor = max(0.7, math.cos(az_rad))

    # Tilt factor: optimal ~25° for SD
    tilt_rad = math.radians(tilt_deg - 25)
    tilt_factor = max(0.85, 1.0 - abs(tilt_rad) * 0.05)

    return time_factor * az_factor * tilt_factor


def compute_kwh(solar_wm2: float, temp_f: float, system_size_dc_kw: float,
                tilt_deg: int, azimuth_deg: int,
                hour: int, month: int,
                noise_pct: float = 0.04) -> float:
    """Expected kWh over a 5-minute interval."""
    eff  = panel_efficiency(temp_f)
    corr = tilt_correction(tilt_deg, azimuth_deg, hour, month)
    power_kw = (solar_wm2 / 1000.0) * system_size_dc_kw * eff * corr
    kwh_5min = power_kw * (5 / 60)
    # Add realistic noise
    noise = random.gauss(0, noise_pct) * kwh_5min
    return round(max(0.0, kwh_5min + noise), 5)


def load_permits() -> list[dict]:
    permits = []
    with open(PERMITS_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["system_size_dc_kw"] = float(row["system_size_dc_kw"])
            row["tilt_deg"]          = int(row["tilt_deg"])
            row["azimuth_deg"]       = int(row["azimuth_deg"])
            permits.append(row)
    return permits


def build_training_rows(awn_events: list, permits: list) -> list[dict]:
    """
    Cross each AWN weather reading with every permit to get training rows.
    Each row = one (weather snapshot × install spec) pair.
    """
    rows = []
    for ev in awn_events:
        for permit in permits:
            kwh = compute_kwh(
                ev["solar_radiation_wm2"],
                ev["outdoor_temp_f"],
                permit["system_size_dc_kw"],
                permit["tilt_deg"],
                permit["azimuth_deg"],
                ev["hour_local"],
                ev["month"],
            )
            rows.append({
                "solar_radiation_wm2": ev["solar_radiation_wm2"],
                "outdoor_temp_f":      ev["outdoor_temp_f"],
                "humidity_pct":        ev["humidity_pct"],
                "uv_index":            ev["uv_index"],
                "system_size_dc_kw":   permit["system_size_dc_kw"],
                "tilt_deg":            permit["tilt_deg"],
                "azimuth_deg":         permit["azimuth_deg"],
                "hour_local":          ev["hour_local"],
                "month":               ev["month"],
                "expected_kwh":        kwh,         # TARGET variable
            })
    return rows


def build_demo_events(demo_awn: list, permits: list) -> list[dict]:
    """
    For each demo AWN reading, attach ALL permits as separate events.
    Insert fault degradation for FAULT_PERMIT during FAULT_HOURS.
    """
    events = []
    fault_permit = next(p for p in permits if p["permit_id"] == FAULT_PERMIT)

    for ev in demo_awn:
        for permit in permits:
            expected = compute_kwh(
                ev["solar_radiation_wm2"],
                ev["outdoor_temp_f"],
                permit["system_size_dc_kw"],
                permit["tilt_deg"],
                permit["azimuth_deg"],
                ev["hour_local"],
                ev["month"],
                noise_pct=0.01,   # tighter noise for demo
            )

            # Inject fault for the demo install
            is_fault = (permit["permit_id"] == FAULT_PERMIT
                        and ev["hour_local"] in FAULT_HOURS)
            actual_kwh = round(expected * (FAULT_FACTOR if is_fault else
                                           random.uniform(0.97, 1.03)), 5)

            events.append({
                **ev,
                "permit_id":           permit["permit_id"],
                "address":             permit["address"],
                "zip_code":            permit["zip_code"],
                "system_size_dc_kw":   permit["system_size_dc_kw"],
                "tilt_deg":            permit["tilt_deg"],
                "azimuth_deg":         permit["azimuth_deg"],
                "expected_kwh":        expected,
                "actual_kwh":          actual_kwh,
                "fault_injected":      is_fault,
            })

    return events


def main():
    print("Loading data…")
    with open(AWN_EVENTS)  as f: awn_train = json.load(f)
    with open(DEMO_EVENTS) as f: awn_demo  = json.load(f)
    permits = load_permits()

    print(f"  Training AWN events : {len(awn_train)}")
    print(f"  Demo AWN events     : {len(awn_demo)}")
    print(f"  Permits             : {len(permits)}")

    # Build training CSV
    print("\nBuilding training rows (AWN events × permits)…")
    rows = build_training_rows(awn_train, permits)
    print(f"  Total training rows : {len(rows)}")

    fields = list(rows[0].keys())
    with open(TRAIN_OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved -> {TRAIN_OUT}")

    # Build demo events with fault injected
    print("\nBuilding demo events with fault injection…")
    demo_events = build_demo_events(awn_demo, permits)
    fault_count = sum(1 for e in demo_events if e.get("fault_injected"))
    print(f"  Total demo events   : {len(demo_events)}")
    print(f"  Fault-injected rows : {fault_count}  (permit={FAULT_PERMIT}, hours={list(FAULT_HOURS)})")

    with open(DEMO_OUT, "w") as f:
        json.dump(demo_events, f, indent=2)
    print(f"  Saved -> {DEMO_OUT}")

    # Print a few sample training rows
    print("\nSample training rows:")
    for r in rows[:3]:
        print(f"  solar={r['solar_radiation_wm2']} W/m²  "
              f"size={r['system_size_dc_kw']} kW  "
              f"->  expected_kwh={r['expected_kwh']}")


if __name__ == "__main__":
    main()
