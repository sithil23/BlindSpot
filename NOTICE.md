# Provenance and third-party components

HMS was supplied by the user as `hms_project (1).zip`. No standalone licence file was
present. BLINDSPOT adapts its SQLite logging design (WAL, parameterized writes, thread
lock) into an explicit session store. No medical validity is claimed for HMS or this remake.
Confirm rights and competition treatment of pre-existing work before public submission.

The hand landmark model is Google's MediaPipe Hand Landmarker float16 version 1:
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

SHA256: fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1

Model information and applicable terms:
https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker
https://developers.google.com/terms

MediaPipe, OpenCV, Streamlit and other dependencies retain their own licences. Their
package licence files apply. The model is unmodified and provided for local inference.
No NASA logos, astronaut records or third-party patient data are included.

The NASA resource is attributed in README.md and `blindspot/data/nasa_context.json`.
The short offline research note is a project paraphrase, not a reproduced NASA article.
NASA does not endorse or validate BLINDSPOT.

This delivery was developed with OpenAI Codex assistance. No new blanket licence is
asserted over the user's supplied project.
