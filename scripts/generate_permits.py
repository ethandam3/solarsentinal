"""
generate_permits.py
Creates a realistic synthetic ZenPower Solar Permit CSV for San Diego.
When the real ZenPower dataset is released at the hackathon portal,
replace data/zenpower_permits.csv with the real file — everything
downstream reads from that path and will Just Work.

Fields match the ZenPower permit schema:
  permit_id, address, city, zip_code, install_date,
  system_size_dc_kw, system_size_ac_kw,
  panel_model, panel_count, inverter_model,
  tilt_deg, azimuth_deg, annual_kwh_est, status

NOTE: tilt/azimuth values reflect real San Diego solar installs.
  - Optimal tilt for SD (32.87°N) ≈ 22-28°
  - Most roofs face S (180°) ± 30° for azimuth
"""

import csv
import random
from pathlib import Path
from datetime import date, timedelta

random.seed(42)   # reproducible

OUT_PATH = Path(r"C:\Users\ethan\solarsentinel\data\zenpower_permits.csv")
OUT_PATH.parent.mkdir(exist_ok=True)

# San Diego neighbourhood zips for realism
SD_ZIPS = ["92037", "92093", "92122", "92121", "92130",
           "92131", "92123", "92103", "92108", "92115"]

PANEL_MODELS = [
    "SunPower SPR-MAX3-400", "LG NeON R 380W",
    "REC Alpha 405W",        "Canadian Solar CS6R-390",
    "Hanwha Q.PEAK DUO 395W"
]

INVERTER_MODELS = [
    "Enphase IQ8A Microinverter",
    "SolarEdge SE7600H-US",
    "SMA Sunny Boy 7.7-US",
    "Fronius Symo 10.0-3-208",
]

def random_date(start_year=2018, end_year=2024):
    start = date(start_year, 1, 1)
    end   = date(end_year, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def make_permit(idx: int) -> dict:
    size_dc  = round(random.uniform(5.5, 13.0), 2)
    size_ac  = round(size_dc * random.uniform(0.94, 0.98), 2)
    tilt     = random.randint(18, 30)          # 18–30° typical for SD roofs
    azimuth  = random.randint(155, 205)        # south-ish ± 25°
    # Rough annual estimate: size_dc × 1600 sun-hours (SD average)
    annual   = round(size_dc * random.uniform(1500, 1750))
    panel_ct = round(size_dc * 1000 / 390)    # ≈ watts per panel

    return {
        "permit_id":        f"ZP-{idx:04d}",
        "address":          f"{random.randint(1000, 9999)} {random.choice(['Torrey Pines Rd', 'La Jolla Shores Dr', 'Genesee Ave', 'Miramar Rd', 'Carmel Valley Rd', 'Sorrento Valley Blvd'])}",
        "city":             "San Diego",
        "zip_code":         random.choice(SD_ZIPS),
        "install_date":     random_date().isoformat(),
        "system_size_dc_kw": size_dc,
        "system_size_ac_kw": size_ac,
        "panel_model":      random.choice(PANEL_MODELS),
        "panel_count":      panel_ct,
        "inverter_model":   random.choice(INVERTER_MODELS),
        "tilt_deg":         tilt,
        "azimuth_deg":      azimuth,
        "annual_kwh_est":   annual,
        "status":           "Approved & Installed",
    }


def main():
    permits = [make_permit(i) for i in range(1, 51)]   # 50 installs

    fields = list(permits[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(permits)

    print(f"Generated {len(permits)} permits -> {OUT_PATH}")
    print("\nSample permits:")
    for p in permits[:3]:
        print(f"  {p['permit_id']}  {p['system_size_dc_kw']} kW DC  "
              f"tilt={p['tilt_deg']}°  az={p['azimuth_deg']}°  "
              f"zip={p['zip_code']}")


if __name__ == "__main__":
    main()
