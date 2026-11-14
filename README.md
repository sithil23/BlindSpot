# BLINDSPOT

**Astronaut Health and Mission Monitoring**

BLINDSPOT is a NASA Space Apps project exploring how astronauts and mission teams can keep track of crew well-being during space missions. It brings health observations, spacecraft conditions, spacewalk checks, radiation exposure, and meal records into one easy-to-read dashboard.

## The problem

During a mission, information about an astronaut's health and surroundings can come from several different systems. A single reading may not tell the full story, and missing or unreliable data can make it harder to know what needs attention.

BLINDSPOT explores a simple question: **How can a crew quickly spot possible concerns while also knowing whether the information can be trusted?**

## Our solution

The dashboard brings important mission information together, highlights unusual readings, and helps crew members decide what to review. Instead of treating missing sensor data as normal, BLINDSPOT clearly marks gaps and disconnected feeds.

The prototype supports:

- **Crew monitoring:** View simulated heart rate, blood oxygen, breathing rate, and body temperature for three crew members.
- **Habitat conditions:** Follow cabin oxygen, carbon dioxide, pressure, and sensor trends across two simulated habitats.
- **Spacewalk checks:** Compare observations before and after a spacewalk, including experimental camera-based movement assessments.
- **Crew attention:** Display a top-three follow-up list based on flagged or missing measurements, with visible alerts and review reports.
- **Radiation monitoring:** Explore simulated radiation readings, accumulated exposure, and cases where dosimeter data becomes unreliable.
- **Meal and nutrition records:** Log meals, suggest a next meal time, and flag overdue meal records. Food barcode numbers can be used to look up nutritional information.
- **Camera-based food management:** Register a crew member using three face photos, then manually capture a face or barcode using the same camera view.
- **Demo scenarios:** Trigger simulated events to demonstrate warnings, reports, and sensor-reliability checks.

## How BLINDSPOT works

1. Simulated sensors provide crew and habitat readings.
2. BLINDSPOT checks the readings and whether the supporting information is available.
3. The Mission Overview displays trends, important warnings, and the crew members who need follow-up.
4. Spacewalk and meal tools let users add observations and records.
5. Crew members can review and export information for further investigation.

## Getting started

BLINDSPOT is built with Python and Streamlit. With Python installed, set up a virtual environment, install the project requirements, and start the dashboard:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Camera features may also require the packages in `requirements-camera.txt`, along with `zxing-cpp` and `Pillow`. The simulated sensor services run separately through `remote_sensor_api.py` and require their configured addresses and access tokens.

## Research and data sources

BLINDSPOT takes inspiration from space-medicine and astronaut-monitoring research, including:

- [NASA — Space Radiation](https://www.nasa.gov/directorates/esdmd/hhp/space-radiation/)
- [NASA — RadLab radiation data portal](https://visualization.osdr.nasa.gov/radlab)
- [Canadian Space Agency — Monitoring radiation for astronaut health](https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp)
- [Canadian Space Agency — Radi-N2](https://www.asc-csa.gc.ca/eng/sciences/radi-n2.asp)
- [Open Food Facts](https://world.openfoodfacts.org/) for food-product information

**Research references are not the same as live data feeds.** The current monitoring demonstration uses synthetic crew, habitat, and radiation readings rather than live NASA measurements.

## Important limitations

BLINDSPOT is an educational and research prototype, **not a medical device**. It cannot diagnose illness, determine medical fitness, or provide verified radiation exposure. Crew rankings and meal reminders are prompts for review, not medical recommendations. Camera recognition and food lookups may be inaccurate and should be checked before saving records.

Do not publish personal health or face-registration data, local databases, access tokens, or secret configuration files.
