# BLINDSPOT

**Astronaut Health and Mission Monitoring**

BLINDSPOT is a NASA Space Apps prototype that brings astronaut health observations, habitat conditions, spacewalk checks, radiation monitoring, and nutrition records into one simple dashboard.

## The problem

During a space mission, useful information is spread across many measurements and records. Missing or unreliable readings can make it difficult for crew members to know what needs attention. BLINDSPOT brings these observations together and makes data gaps visible instead of treating them as normal.

## What BLINDSPOT does

- **Crew dashboard:** Follow simulated heart rate, oxygen level, breathing rate, and temperature for three crew members.
- **Habitat conditions:** Review readings and trends for two simulated habitats.
- **Spacewalk check:** Compare observations before and after an EVA, including experimental movement and camera-based tests.
- **Crew attention:** See which of the three crew profiles has measurements needing review.
- **Radiation monitoring:** View simulated exposure and warnings when data is missing or abnormal in a demo scenario.
- **Food management:** Record meal times and nutrients, find food by barcode number, and use optional three-photo face enrollment to select crew profiles.
- **Demo controls:** Trigger simulated sensor and radiation events and download review reports.

## How it works

Simulated sensor feeds provide readings to BLINDSPOT. The dashboard checks the values and whether the evidence is usable, then displays trends, warnings, and follow-up information. The spacewalk and nutrition tools add user-created records. Crew members can review and export information for investigation.

## Run locally

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

For webcam functions, also install `requirements-camera.txt`, `zxing-cpp` and `Pillow`. The two optional remote sensor simulators use `remote_sensor_api.py` with separate local ports and bearer tokens. See `REMOTE-SENSOR-SETUP.md` and `MULTI-FEED-SETUP.md` when those are present in your deployment.

## Research and sources

- [NASA Space Radiation](https://www.nasa.gov/directorates/esdmd/hhp/space-radiation/)
- [NASA RadLab](https://visualization.osdr.nasa.gov/radlab)
- [Canadian Space Agency: Monitoring radiation for astronaut health](https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp)
- [Canadian Space Agency: Radi-N2](https://www.asc-csa.gc.ca/eng/sciences/radi-n2.asp)
- [Open Food Facts](https://world.openfoodfacts.org/)

The current dashboard uses **simulated sensor and radiation readings**, not live NASA or CANS measurements. The application is an educational research demonstration, not a medical device. Face matching and barcode lookup may be inaccurate; review records before using them for crew follow-up.

**Privacy:** Do not commit saved face profiles, health/meal databases, tokens, or `.env` files.
