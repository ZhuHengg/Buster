# Solution Plan: Proactive CCTV Alert System

**Sime Darby Property University Hackathon 2026 · Theme 1: People / Safety & Security**
Companion to [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md).

---

## 1. Intent

Township CCTV today is **reactive**: it records everything and alerts no one. This project makes it **proactive**. The system watches the feeds, detects a crime as it happens, and gives the security team a clear, actionable alert while there is still time to act.

"Proactive" here means **detect and alert in real time**. It does not mean predicting crime before it happens.

**Hero scenario:** a motorcycle snatch theft near township shoplots or a bus stop.
- It is common and emotional in Malaysia.
- Commercial CCTV analytics (line crossing, loitering, intrusion zones) do not detect it.
- A township has a limited number of exits, so a fast alert with a suspect description gives security a real chance to intercept before the motorcycle leaves.

---

## 2. Goals, non-goals, anti-goals

**Goals**
- Detect a motorcycle snatch theft in CCTV footage, near real time.
- Turn the detection into an **actionable alert**: what happened, where, when, suspect and vehicle description, direction of escape, and a face/upper-body snapshot.
- Keep a **human in the loop**: a guard in the Central Monitoring System (CMS) approves or rejects every alert before anything is escalated.
- On approval, escalate automatically: a phone call and SMS to the police station (mocked as a teammate's phone) and an alert to the exit-gate guard.
- Prove it is not rigged: a normal street clip must produce **no** alert.
- Look like a real control-room product, not a student prototype.

**Non-goals**
- Identifying people by name, matching faces against databases, or storing face embeddings.
- Real PDRM integration or real camera hardware.
- Multi-township deployment, user accounts and access control.
- Detecting other scenarios (fights, collapses, break-ins). These are mentioned in the pitch as "same pipeline, new model" only.

**Anti-goals: the demo fails if any of these happen, even if the code technically works**
- The system calls the police without a guard approving first.
- The normal clip triggers an alert on stage.
- The alert shows only "anomaly detected" with no description. The whole point is actionable output.
- The CMS looks like a toy (default styling, debug text, visible frame counters).

---

## 3. Constraints

| Constraint | Detail |
|---|---|
| Stack | Python backend; TypeScript, Next.js (React) and Tailwind CSS frontend |
| Hardware | One laptop/desktop with an NVIDIA RTX 3080 for training and running the demo |
| Network | Step 2 verification and Twilio need internet. The venue Wi-Fi may be unreliable, so bring a phone hotspot, and see replay mode (§9) |
| Privacy | PDPA (Amendment) 2024 classes biometric data as sensitive. No face recognition, no face embeddings; snapshots are kept only inside incident records |
| Demo footage | Staged by the team (with consent and permission) plus clips found online for training (§10) |
| Deadline | **Not yet confirmed.** The milestone plan depends on it |

---

## 4. Demo walkthrough (~3 minutes)

1. **CMS on screen.** A 3×3 grid of camera feeds in a dark control-room theme. Each tile shows a camera ID and name ("CAM-07 · Elmina Shoplot Row B"), a live timestamp and a red REC dot. Every person and motorcycle has a box and a track ID.
2. **The snatch happens on CAM-07.** A motorcycle with two riders approaches a woman walking; the pillion grabs her bag; they speed off.
3. **Within seconds** the suspects' boxes turn red and the tile flashes. The **alert card** pops up:
   - a replay of the incident (about 6 seconds, looping)
   - a face or upper-body snapshot of each suspect
   - the description: *"2 male suspects on black motorcycle. Pillion in red jacket, black full-face helmet. Snatched handbag from female pedestrian. Fled north toward Gate B."*
   - camera, location, time, and confidence
   - buttons: **Approve and escalate** / **Reject (false positive)**
4. **The guard approves.** An escalation timeline shows each step: police called → SMS sent → Gate B alerted. A teammate's phone rings on stage and reads out the incident details.
5. **A normal street clip** plays on another tile. Nothing fires.
6. **Incident log.** The approved incident shows with its timeline; one earlier rejected false positive is also listed.

---

## 5. Architecture

```
┌──────────── Backend (Python, FastAPI) ─────────────────────────────────────┐
│                                                                             │
│  Video sources ──► Person/vehicle detection ──► Step 1: fast screening      │
│  (clip files,      + tracking                   (action model OR rules)     │
│   played at        (YOLO + ByteTrack, pose)          │ candidate event      │
│   real-time pace)        │                           ▼                      │
│                          │                 Step 2: AI verification          │
│                          │                 (Claude vision, structured JSON) │
│                          │                           │ verified incident    │
│                          ▼                           ▼                      │
│                   Detections stream ◄──── Incident service (SQLite) ──┐     │
│                          │                           │                │     │
│                          │                    on guard approval       │     │
│                          │                           ▼                │     │
│                          │                 Escalation (Twilio voice + SMS,  │
│                          │                 gate alert)                │     │
└──────────────────────────┼───────────────────────────┼────────────────┼─────┘
                           │ WebSocket                 │ REST           │
┌──────────────────────────▼───────────────────────────▼────────────────┴─────┐
│  Frontend (Next.js + TypeScript + Tailwind): CMS dashboard                   │
│  Camera grid + box overlay · Alert card · Escalation timeline · Incident log │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Components

### 6.1 Video sources
- Each "camera" is a video file played on a loop at real-time speed, so it behaves like a live feed.
- `cameras.json` defines each camera: `id`, `name`, `location`, `clip`, and a `direction → exit` map (e.g. `north → Gate B`) used to turn the direction of escape into an exit name.
- Only the cameras with clips of interest are analysed; the other grid tiles play normal footage for realism. *(My call: analysing 2–3 feeds is enough for the demo and keeps the GPU load low.)*

### 6.2 Detection and tracking
- **Ultralytics YOLO** (a small model such as YOLO11n/s) detects the `person` and `motorcycle` classes, and **ByteTrack** keeps track IDs stable.
- A **YOLO pose** model supplies arm and wrist keypoints for the rule-based trigger.
- The output for every analysed frame: `{camera_id, pts, tracks: [{id, class, bbox, keypoints?}]}`, streamed to the frontend.

### 6.3 Step 1: fast screening (high recall)
Step 1 watches continuously and raises **candidate events**. Its job is to miss nothing; Step 2 removes false alarms. A candidate is raised if **either** of these fires:

- **A. Action model (primary).** A video classifier fine-tuned to tell `snatch_theft` from `normal`.
  - *My call:* VideoMAE-base (Hugging Face `transformers`, Kinetics-pretrained). Fall back to X3D-S if the RTX 3080 runs out of memory or training is too slow.
  - Input: a sliding window of 16 frames covering about 2 seconds, moving forward every 0.5 seconds.
  - It fires when the score passes a threshold on 2 consecutive windows.
- **B. Rules on tracks and pose (backup, always on).** All three must happen in order, within about 3 seconds:
  1. a motorcycle track comes within a set distance of a pedestrian track
  2. an arm of the pillion rider extends towards the pedestrian (from pose keypoints)
  3. the motorcycle speeds up away from the pedestrian, or the pedestrian makes a sudden jerk or falls

If the action model is not ready in time, rule B alone feeds Step 2 and the demo still works.

### 6.4 Step 2: AI verification and description (high precision)
- It runs only when Step 1 raises a candidate.
- The backend sends the vision model about 8 keyframes covering ±3 seconds around the event, with track boxes and IDs drawn on, plus the camera name and location.
- **Model:** Claude (`claude-opus-5-5`) via the Anthropic Python SDK, with structured outputs (`output_config.format`) so the reply always matches the schema below, and effort set to `low` for speed.
- Refusal fallbacks are enabled (`fallbacks: "default"`), so a safety-classifier refusal does not drop the alert.
- The model name is a config value, so it can be swapped.

Output schema:

```json
{
  "is_incident": true,
  "incident_type": "snatch_theft | robbery | assault | other | none",
  "confidence": 0.0,
  "summary": "One-sentence plain-language description",
  "suspects": [{ "track_id": 3, "description": "male, red jacket, black full-face helmet, pillion" }],
  "victim": { "track_id": 1, "description": "female, white blouse, carrying handbag" },
  "vehicle": { "type": "motorcycle", "colour": "black", "plate_visible": false, "plate_text": null },
  "escape_direction": "north | south | east | west | unknown"
}
```

- If `is_incident` is false, the candidate is logged as an AI-filtered false alarm and the guard never sees it.
- Otherwise the backend creates the incident.
- **Direction of escape comes from the tracker, not the AI model.** The backend reads the motorcycle track's motion vector over the last frames and maps it to an exit using `cameras.json`. The model's `escape_direction` is only a cross-check, because the tracker is more reliable for direction.

### 6.5 Suspect snapshot
- From each suspect's track, pick the sharpest head/upper-body crop. *(My call: sharpness by Laplacian variance.)*
- This is a cropped image only. There is no face recognition and no embedding.
- Snapshots from rejected incidents are deleted when the guard rejects the alert.

### 6.6 Incident service
- Stored in SQLite.
- Lifecycle: `CANDIDATE → AI_REJECTED` or `CANDIDATE → PENDING_REVIEW → APPROVED → ESCALATED`, or `PENDING_REVIEW → REJECTED`.
- Each incident stores: camera, timestamps, the Step 1 trigger source (model or rule), the Step 2 JSON, snapshot paths, the replay clip path, the guard decision with time, and the escalation results.
- Timing metrics are recorded per incident: event → candidate, candidate → verified, verified → shown to guard, guard decision → call placed.

### 6.7 Escalation (only after guard approval)
- **Voice call:** Twilio places a call to the "police" number (a teammate's phone) and reads a script aloud: incident type, location, time, suspect and vehicle description, direction of escape, and the reporting CMS operator.
- **SMS** to the same number with the summary.
- **Gate alert:** an SMS to a second phone (the "Gate B guard") with the description and direction. The CMS shows the alert as delivered.
- Every step shows live in the escalation timeline (queued → ringing → answered / failed).
- A Twilio trial account can only call verified numbers and plays a trial message first; that is acceptable for the demo.
- **The voice call is the primary channel; SMS is best effort.** Enable Malaysia in Twilio's voice and SMS geo-permissions. SMS to Malaysian numbers may need a paid account or a registered sender, so if SMS fails, the CMS shows the gate alert on screen and the demo goes on. Test both channels in the first week, not the day before.

### 6.8 Frontend (CMS)
- **Pages:** `/` is the CMS dashboard; `/incidents` is the incident log and detail view.
- **Camera grid:** each tile is a `<video>` with a `<canvas>` overlay. Boxes are drawn from the detections stream, matched to the video's playback timestamp. Boxes are red for suspects, white for others, and show track IDs.
- **Alert card:** a modal that slides in, with an alert sound and a pulsing border on the camera tile. It shows the replay clip, snapshots, the summary, a description table, location, confidence and the Approve / Reject buttons.
- **Escalation timeline:** a stepper with the status of each escalation step.
- **Look and feel:** dark control-room theme, monospaced timestamps, camera labels on the video like real CCTV, nothing that looks like debugging.

---

## 7. Data and training plan (Step 1 action model)

| Source | Use |
|---|---|
| **UCF-Crime**: `Robbery`, `Stealing` and `Normal` classes | Base training data |
| **Online snatch-theft clips** (keywords in §10) | The main positive class; this is the closest match to the hero scenario |
| **The team's own staged clips** | Training, plus a held-out test set and the demo clips |
| Online normal street CCTV clips | Negatives; they teach the model what "nothing happening" looks like |

- **Labelling:** cut each video into short clips around the snatch moment (positive) and plain stretches (negative). Keep a spreadsheet: `source_url, file, start, end, label, camera_angle, day/night`.
- **Split by video, not by clip**, so the test set never contains footage from a video used in training.
- **Augmentation:** horizontal flip, brightness and contrast changes, blur and compression artefacts (CCTV-like), and random crops.
- **Targets on the held-out set:** recall ≥ 0.9 on snatch clips, and zero alerts after Step 2 on the normal demo clips.

**Demo clips are never used for training**, so the on-stage result is honest.

---

## 8. Measures of success

| Measure | Target |
|---|---|
| Snatch moment → alert card on screen | ≤ 10 s (Step 1 ≤ 2 s, Step 2 ≤ 6 s) |
| Guard approval → police phone ringing | ≤ 5 s |
| Normal demo clips | 0 alerts |
| Held-out snatch clips detected | ≥ 90% |
| Step 1 false triggers rejected by Step 2 | Reported as a number. This is the evidence that the two-step design works |

These numbers go into the pitch as **evidence**, next to the baseline "time until someone notices on today's CCTV" from the guard interviews.

---

## 9. Risks and fallbacks

| Risk | Fallback |
|---|---|
| The action model is not accurate enough in time | Rule B alone triggers Step 2; Step 2 still provides precision |
| Live processing stutters on the demo laptop | **Replay mode:** detections, candidates and Step 2 results are precomputed for the demo clips and played back in sync. It looks identical on screen. Switched by a config flag |
| No internet at the venue | Phone hotspot. In replay mode Step 2 uses cached results; the Twilio call needs data, so the backup is a pre-recorded screen capture of the call |
| Step 2 is too slow | Lower the keyframe count or resolution. The card shows "Verifying…" immediately on the candidate and fills in when Step 2 returns |
| Twilio trial restrictions | Verify both teammate numbers in advance; test the call the day before |
| Staged clips look fake | Film from a high fixed angle at a real shoplot with permission, at CCTV-like quality; add a timestamp overlay in the frontend, not burned into the video |

---

## 10. Finding clips online: search keywords

**Snatch theft (positives)**
- Malay: `ragut beg CCTV`, `kes ragut motosikal rakaman CCTV`, `peragut motosikal CCTV`, `ragut rantai CCTV`
- English: `snatch theft CCTV Malaysia`, `bag snatching motorcycle CCTV`, `purse snatching caught on camera`, `phone snatching moped CCTV`
- India (high volume): `chain snatching CCTV footage`, `bike chain snatching caught on camera`
- Indonesia: `jambret tas CCTV`, `jambret motor terekam CCTV`
- Vietnam (many motorcycle cases): `cướp giật CCTV`, `cướp giật túi xách xe máy camera`

**Normal footage (negatives)**
- `Malaysia street CCTV footage`, `kaki lima CCTV`, `shoplot street CCTV`
- `pedestrian sidewalk CCTV footage`, `motorcycle passing street CCTV`, `bus stop CCTV footage`
- Include night clips and rainy clips, so the model doesn't learn "dark = crime".

**Public datasets**
- **UCF-Crime**: 1,900 real CCTV videos in 13 crime classes plus Normal; use Robbery, Stealing and Normal.
- **XD-Violence** and **RWF-2000**: for future scenarios (fights, assault). Not needed for the hero scenario.

**What makes a clip useful**
- A fixed, high camera angle like real CCTV (skip dashcam and handheld footage).
- The snatch is fully visible: the approach, the grab and the escape.
- 480p or better; a mix of day and night.

**Ground rules**
- Use online clips for training and testing only.
- Do not show real victims in the pitch; use the team's staged clips for that.
- Respect each platform's terms of use.

---

## 11. Suggested repository layout

```
backend/        Python: FastAPI app, video pipeline, detection, Step 1, Step 2, escalation
  training/     data preparation, fine-tuning and evaluation scripts for the action model
frontend/       Next.js + TypeScript + Tailwind CMS
data/           clips, labels spreadsheet (git-ignored)
models/         trained weights (git-ignored)
cameras.json    camera configuration
```

---

## 12. Decisions made on the team's behalf (review these)

- **Film staged clips early.** Filming is a first-week task, because the clips are needed for tuning Rule B, the held-out test set and the demo. Aim for at least 15 takes of the snatch from 2–3 angles (day and dusk), plus 10+ normal takes at the same spots. For each camera position, note which direction leads to which gate.
- **The live pipeline is the main demo; replay mode is only a fallback.** There is no "judge uploads their own clip" feature; the normal clip proves the system isn't rigged.
- **If time runs short, the action model is the first thing cut.** YOLO + Rule B + Step 2 verification is the minimum version that still delivers the full demo. Effort then goes to the CMS and escalation.
- **Direction of escape comes from tracking**, not from the AI model (§6.4).
- **Voice call first, SMS best effort** (§6.7).

## 13. Left to the builder

- The exact YOLO model size, thresholds, window sizes and rule distances. Tune them on the training clips.
- The WebSocket message format and how the boxes stay in sync with video playback.
- The voice-call script wording and the SMS format.
- Visual details of the CMS within the "real control room" direction.
- Which normal clips fill the other grid tiles.
