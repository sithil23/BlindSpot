# BLINDSPOT

Astronaut health, habitat, spacewalk, radiation and nutrition-monitoring prototype for NASA Space Apps.

The application uses **Python and Streamlit**. Crew and habitat telemetry are **simulated** and are not suitable for medical decisions.

## Features

- Demo Three-crew dashboard with health readings and alerts
- Two simulated habitat feeds, environmental warnings and sensor trends
- Spacewalk before/after observations and experimental camera assessments
- Radiation dose monitoring demonstrations with data-quality checks
- Ranked crew follow-up and downloadable reports
- Nutrition records, food barcode lookup and optional local face recognition
- Manual camera capture in Food Management (no autonomous meal logging)
- Simple, flat interface

## Local startup

Use a Python virtual environment and install the requirements listed in `requirements.txt`. Run:

```powershell
python -m streamlit run app.py
```

The optional camera features require `requirements-camera.txt`, `zxing-cpp` and `Pillow`. The simulated sensor APIs can be started separately using `remote_sensor_api.py` after configuring the sensor URL and token environment variables.

## Source status

The original repository contains `BLINDSPOT.zip`, an **earlier project archive**. The v31 source is prepared separately and must be added to the repository before treating this GitHub branch as the final v31 release.

Do not upload local SQLite databases, personal face enrollment data, tokens or `.env` files. This project does not provide clinical diagnosis or verified astronaut radiation exposure.

## Scientific context

- [NASA Space Radiation](https://www.nasa.gov/directorates/esdmd/hhp/space-radiation/)
- [Canadian Space Agency radiation research](https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp)
- [Open Food Facts](https://world.openfoodfacts.org/)
