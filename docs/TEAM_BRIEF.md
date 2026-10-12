# Team Brief: The Ideal Proactive CCTV Alert System

**Sime Darby Property University Hackathon 2026 · Theme 1: People / Safety & Security**

This page describes the system **as it should work in the ideal case**. Use it to write your part of the solution (pitch, slides, write-up, script). It is the target, not a status report. For what is built today and what is measured, see [../README.md](../README.md).

Longer sources: [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) · [SOLUTION_PLAN.md](SOLUTION_PLAN.md) · [FILMING_GUIDE.md](FILMING_GUIDE.md)

---

## 1. The idea in 30 seconds

Township CCTV records everything and alerts no one. A crime is only noticed if a guard happens to watch the right screen at the right moment, and then the system gives them raw video, not a next step. By then the intruder is gone.

**Our answer:** three layers of AI watch every camera, narrowing thousands of ordinary moments down to the rare real crime. A human guard confirms it with one click. The system then alerts the **nearest police station** and the exit-gate guard, with a clear description of what happened, where, and which way the suspects fled.

- **Proactive means detect and alert in real time.** It does not mean predicting crime.
- **Hero scenario:** motorcycle snatch theft ("ragut"). It is common, it counts in PDRM's rising property-crime index, and standard CCTV analytics (line crossing, loitering, intrusion zones) do not detect it. A township has few exits, so a fast alert with a suspect description gives security a real chance to intercept.
- We **build on SDP's existing CCTV and auxiliary police**. We do not replace them.

## 2. The three-layer funnel

Each layer is more accurate and more expensive than the one before, so each runs only on what the previous layer lets through. Cheap checks run on everything. Costly checks run on almost nothing.

```
All camera feeds, all the time
        |
        v
LAYER 1   YOLO + tracking + pose rules         "Is something that looks like a snatch happening?"
          cheap, runs on every camera           Goal: miss nothing (high recall)
        |  candidate clip (a few seconds)
        v
LAYER 2   Trained action model                 "Does this clip actually move like a snatch theft?"
          runs only on Layer 1 candidates       Goal: drop most false triggers
        |  likely-snatch clip
        v
LAYER 3   Vision LLM classifier                "What exactly happened? Is it a real incident?"
          runs only on Layer 2 positives        Goal: precision + a written description
        |  verified incident with description
        v
HUMAN     Guard in the Central Monitoring System (CMS) reviews and decides
        |  Approve
        v
ALERT     Nearest police station (call + SMS) and the exit-gate guard
```

| | Layer 1: YOLO + rules | Layer 2: trained model | Layer 3: vision LLM |
|---|---|---|---|
| **Job** | Spot the ingredients of a snatch | Recognise the *movement* of a snatch | Judge the scene and describe it in words |
| **How** | YOLO detects people and motorcycles, a tracker keeps IDs stable, a pose model gives arms and wrists. Rule: a motorcycle comes close to a pedestrian, an arm reaches toward them, then the bike speeds off or the pedestrian is jerked or falls, all within about 3 seconds | A video classifier (for example VideoMAE) fine-tuned on snatch-theft versus normal clips. Looks at a 2-second window of 16 frames and outputs a snatch score | About 8 keyframes around the event, with boxes drawn on, plus camera name and location, go to a vision LLM. It returns structured JSON: is it an incident, type, confidence, summary, suspects, victim, vehicle, direction |
| **Strength** | Fast, explainable, no training data needed, runs on every camera | Learns what a real snatch looks like, so it survives blur and bad angles that break hand-written rules | Understands context ("a man hands his friend a bag" is not a theft) and writes the alert text |
| **Weakness** | Over-sensitive; fooled by anything that resembles the pattern | Only as good as its training data; can mistake lookalikes | Slowest, costs money per call, can be wrong, so it never acts alone |
| **Target time** | under 2 s | under 2 s | under 6 s |
| **Output** | Candidate clip + track IDs | Score above threshold | Verified incident or "false alarm" (the guard never sees it) |

**Why layered:**
- **Cost and speed.** The expensive LLM sees a handful of clips per day, not every frame.
- **Accuracy.** Layer 1 catches everything, Layers 2 and 3 clean it up. We report how many false triggers each layer removes. That is the evidence that the design works.
- **Resilience.** If one layer is weak, the others compensate. Layer 1 alone can still feed the LLM as a safe fallback.
- **Explainability.** Every alert can say which layer fired and why.

**Escape direction comes from the tracker** (the motorcycle's motion vector mapped to an exit in the camera config), not from the LLM. The LLM's direction is only a cross-check, because the tracker is more reliable.

## 3. The user flow

### 3.1 The guard's day (the main flow)

1. **Normal state.** The guard opens the CMS: a grid of camera feeds in a dark control-room theme. Each tile shows camera ID and name ("CAM-07 · Elmina Shoplot Row B"), a live timestamp and a REC dot. People and motorcycles carry boxes and track IDs. Nothing demands attention. The guard no longer has to stare at every screen.
2. **A snatch happens.** A motorcycle with two riders approaches a woman walking. The pillion grabs her bag and they speed away. The guard may be looking elsewhere.
3. **The system reacts in seconds.** Layers 1, 2 and 3 run in order. The suspects' boxes turn red, the tile flashes, an alert sound plays, and the **alert card** slides in. The guard never sees the false triggers the layers filtered out.
4. **The guard reads the card.** It already answers *what, where, when, how urgent, what next*:
   - a looping replay of the incident (about 6 seconds)
   - a snapshot of each suspect (a plain image crop, no face recognition)
   - the description, for example: *"2 male suspects on black motorcycle. Pillion in red jacket, black full-face helmet. Snatched handbag from female pedestrian. Fled toward Gate B."*
   - camera, location, time, confidence, and which layers agreed
   - the **nearest police station** that will be alerted
   - two buttons: **Approve and escalate** / **Reject (false positive)**
5. **The guard decides.** They look at the replay and use their judgement.
   - **Reject:** the alert is closed, the snapshots are deleted, and the clip is saved as a new "normal" training example so the models improve.
   - **Approve:** go to step 6.
6. **Automatic escalation.** On approval, and only then:
   - the **nearest police station** gets a phone call that reads out the incident type, location, time, suspect and vehicle description, direction of escape and the reporting CMS operator, plus an SMS summary
   - the **exit-gate guard** in the direction of escape gets an alert with the description
   - an **escalation timeline** in the CMS shows each step live: queued → ringing → answered or failed
7. **Afterwards.** The incident appears in the incident log with its full timeline and timing metrics. Every approval and rejection is recorded with the operator and time.

### 3.2 The police station's view

1. The phone rings. A clear scripted voice states: incident type, exact location, time, suspect and vehicle description, direction of escape, and who in the CMS reported it.
2. An SMS with the same summary arrives so details can be re-read.
3. Officers get the information while the suspects are still moving, not after a resident files a report.

**Choosing the nearest station:** each camera has a location, and a table of police stations (name, coordinates, phone) is kept in configuration. The system picks the closest station to the camera that raised the incident. For the hackathon demo, that "station" is a teammate's phone.

### 3.3 The gate guard's view

1. An alert arrives with the suspect description and the direction of escape, already translated into "heading toward your gate".
2. The guard watches for a matching motorcycle at the exit. A township has a limited number of exits, so this is where interception becomes realistic.

### 3.4 The township manager's view

1. A results page shows how many incidents were detected, how many the guard approved or rejected, how many false triggers each layer removed, and the detection-to-alert time.
2. This is the measurable proof that security spending works, set against the baseline of "how long it takes someone to notice today".

## 4. What the ideal case promises (targets)

| Measure | Ideal target |
|---|---|
| Snatch moment → alert card on the guard's screen | 10 seconds or less (Layer 1 ≤ 2 s, Layer 2 ≤ 2 s, Layer 3 ≤ 6 s) |
| Guard approval → police phone ringing | 5 seconds or less |
| Snatches caught on a held-out test set | 90% or more |
| False alarms reaching the guard on normal footage | zero in the demo; as low as possible in the field |
| Alerts reaching the police without a guard's approval | never |
| Guard workload | far fewer feeds to watch; only verified alerts interrupt them |

These are the goals. Do not present a target as a measured result in your write-up unless a benchmark run produced it.

## 5. Design principles (good material for the "responsible AI" part of your write-up)

- **Human in the loop.** The AI recommends, a guard decides. Nothing reaches the police without approval.
- **No face recognition.** The system describes suspects (clothing, helmet, vehicle). It never identifies anyone, never matches faces against a database, never stores face embeddings. Reason: biometric data is sensitive under the PDPA (Amendment) 2024, with penalties up to RM1M, and face identification is unreliable on CCTV anyway (night, angles, helmets).
- **Privacy by deletion.** Snapshots exist only inside the incident record and are deleted when an alert is rejected.
- **Graceful failure.** If the LLM is slow or down, the candidate still reaches the guard marked "unverified: operator to confirm". The video loop never stops.
- **Learns from guards.** Every rejected alert becomes a new training example for the "normal" class, so false alarms fall over time.
- **Honest evaluation.** Demo clips are never used for training or for choosing thresholds, and the normal clip must produce no alert.
- **Builds on what exists.** It uses SDP's existing cameras and auxiliary police. It adds a layer of understanding on top.

## 6. What we need to make the ideal case real

| Need | Why | Where to find it / how |
|---|---|---|
| **Training clips for Layer 2** | The trained model learns from labelled snatch and normal clips | Public datasets (Snatch 1.0 on Zenodo, RoadCrime-CCTV on Mendeley, UCF-Crime Robbery/Stealing/Normal) plus online snatch clips (search keywords are in [SOLUTION_PLAN.md](SOLUTION_PLAN.md) §10) |
| **Staged clips filmed by us** | Hold-out test set and demo clips, at CCTV-like angle and quality | [FILMING_GUIDE.md](FILMING_GUIDE.md): at least 15 snatch and 10 normal takes, 2-3 fixed high angles, day and dusk, with permission and a fake bag |
| **Normal street footage, day, night, rain** | So the model learns that "dark" or "rain" does not mean crime | Online and filmed clips |
| **Split by source video** | The test set must never share a video with training | Built into our dataset tools |
| **Guard and management interviews** | Gives the baseline "time until someone notices today" and validates our assumptions | 3-5 guards or auxiliary police, plus township management |
| **Vision LLM access** | Layer 3 | API key, with a rate-limit check |
| **Phone numbers and a calling service** | Police and gate alerts | Voice call is the main channel; SMS is best effort |
| **Police station table** | Choosing the nearest station | Name, coordinates, phone for each station near the township |

## 7. Where the system can grow

- **More crime types** (fights, collapses, break-ins): same three layers with a new rule set, a new trained model and a new LLM prompt. Mention in the pitch as "same pipeline, new model". Do not build it now.
- **More cameras per GPU:** Layer 1 is the heavy part because it runs on every camera. Faster options are a smaller input size, batching frames across cameras, TensorRT, or a server GPU. Layers 2 and 3 only run on rare candidates, so they scale cheaply.
- **Bigger network:** one township shows the pattern; each new phase adds cameras without needing guards added at the same rate.

## 8. Fallbacks (so the demo never dies)

| Risk | Fallback |
|---|---|
| Trained model not good enough in time | Layer 1 feeds Layer 3 directly; the demo still works |
| Live processing stutters on the demo laptop | **Replay mode:** results are precomputed and played back in sync, looks identical |
| No venue internet | Phone hotspot; replay mode with cached LLM results; a pre-recorded screen capture of the call |
| LLM too slow | Show "Verifying…" at once, fill in the card when the answer arrives |
| Calling service trial limits | Verify teammate numbers in advance; test the call the day before |
| Staged clips look fake | Film from a high fixed angle with permission; add the timestamp overlay in the interface, not burned into the video |

**Cut order if time runs short:** the trained model (Layer 2) goes first. Layer 1 + Layer 3 + guard review + escalation is the minimum version that still delivers the full story.

## 9. The 3-minute demo story

1. CMS on screen: 3x3 grid, nine live feeds, one of them is the snatch camera.
2. The snatch plays. Boxes turn red, the tile flashes, the card slides in with replay, snapshots and description.
3. The guard clicks **Approve and escalate**. The timeline shows police called, SMS sent, gate alerted. A teammate's phone rings on stage and reads the incident out.
4. A normal street clip on another tile: nothing fires.
5. Incident log: the approved incident, plus one earlier rejected false positive.

**The demo fails if:** the system calls the police without approval · the normal clip alerts on stage · the card says only "anomaly detected" with no description · the interface looks like a prototype.

## 10. Writing guidance for your section

**Do**
- Open with a person (a guard watching nine screens, a resident walking home), then the one-line answer.
- Explain the funnel: cheap and fast first, accurate and slow last, human at the end.
- Show the chain in one diagram: camera → Layer 1 → Layer 2 → Layer 3 → guard → police and gate.
- Say "builds on SDP's CCTV and auxiliary police".
- Give the privacy design its own short paragraph.
- Present figures as "target" unless a benchmark run produced them.

**Do not**
- Say the system "predicts" crime.
- Say it identifies suspects. It describes them.
- Quote accuracy, recall or timing figures we have not measured.
- Use the Subang Jaya case as a criticism of SDP. It is an industry example, not an SDP development.
- Show real victims. Use staged clips.
- Write "AI-powered" without saying what each AI layer does.

**Glossary**
- **CMS:** Central Monitoring System, the guard's screen.
- **Candidate:** Layer 1 fired. **Verified incident:** Layer 3 confirmed. **Escalation:** the guard approved and the alert went out.
- **Recall:** the share of real snatches caught. **False alarm:** an alert about something that was not a snatch.
- **Replay mode:** precomputed results played back with identical timing, used as a fallback.

## 11. Problem facts you can use

Links and sources are in [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md). Cite them if you use the numbers.

- Malaysia index crime rose 11.1% in 2024 to 58,255 cases. Property crime rose 12.4% to 47,188 cases and drove most of the increase (DOSM).
- A guarded Subang Jaya community with cameras, QR registration, electric fencing and 24/7 guards still had 6 burglaries in 5 months. Two unfamiliar cars sat inside for over an hour unnoticed.
- Only about 2% of Malaysians feel unsafe from violent crime in their own neighbourhood, yet 65% think crime is getting worse. Residents of gated areas report higher fear of crime.
- SDP was an early mover: Ara Damansara CCTV linked to the police in 2009, its own auxiliary police in 2016.

**Story framings** (the solution is the same, pick one to open with)
- **A, "From recording to responding"** (primary): SDP's next step after Safe City and the auxiliary police.
- **B, "The walk home"**: felt safety versus real safety.
- **C, "One township, one picture"**: fragmented signals brought into one place.

## 12. Open questions

- Submission deadline and format (slides, video, live demo, write-up).
- Real gate names, and which police stations to list.
- Who owns which section of the write-up and which data task.
