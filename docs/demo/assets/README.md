# Demo photo assets

## What's here (committed)
- `fraud_screen.jpg`, `fraud_screenshot.jpg` — synthetic **fraud** samples. They reliably
  trip the catch side (Suspect: "photo of another screen", "designed graphic / screenshot").
  Safe to commit, no real data.

## What you must add (NOT committed — real photos)
The **"genuine scores high"** wow-moment needs **real photographs** — a good vision model
(correctly) flags cartoon/graphic stand-ins as designed graphics, so PIL-generated images
can't fake it. Drop 2–3 real, **non-customer** photos here:

- `genuine_meeting.jpg` — two people at a desk / in a room (a plausible advisor meeting).
- `genuine_field.jpg` — an outdoor site / shopfront / field visit.
- (optional) `genuine_home.jpg` — a home-visit style photo.

Any real photo works — your own, or a royalty-free stock photo. Keep them modest resolution.

## Score them
```bash
GITHUB_MODELS_TOKEN=<your github_pat_…> PYTHONPATH=src \
  python docs/demo/score_photo.py docs/demo/assets/*.jpg
```
Expected: genuine photos → high score / **Clear**; the fraud samples → **Suspect**.
