# Pitch Deck Content

**Sime Darby Property University Hackathon 2026 · Theme 1: People / Safety & Security**
Companion to [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) and [SOLUTION_PLAN.md](SOLUTION_PLAN.md).

How to read this file:
- **On slide** is the text that goes on the slide. Keep it short; the slide is not the script.
- **Say** is the speaker script, roughly what you would speak.
- **Visual** is what the slide should show.
- **[FILL]** marks a number or fact we do not have yet. Do not publish the deck with these still in it, and do not invent a number to fill them.
- **[CONFIRM]** marks something that must be checked against the current build.

Target length: 13 slides, about 7 minutes including the demo. If the slot is shorter, see the cut list at the end.

---

## Judge criteria map

| Criterion | Weight | Where it is answered |
|---|---|---|
| Impact & Sustainability Value | 25% | Slides 2, 4, 9 |
| Innovation & Differentiation | 20% | Slides 5, 6, 10 |
| Feasibility & Deliverability | 20% | Slides 7, 8, 12 |
| Strategic Fit & Theme Relevance | 15% | Slides 3, 11 |
| Commercial & Value Multiplication | 10% | Slides 9, 11, 12 |
| Team, Evidence & Pitch Quality | 10% | Slides 1, 8, 13 |

---

## Slide 1 · Cover

**On slide**
- Title: **The camera saw it. Now it tells someone.**
- Subtitle: Proactive CCTV alerts for Sime Darby Property townships
- Team name · members · university
- Sime Darby Property University Hackathon 2026 · Theme 1: People / Safety & Security

**Say** (10 s)
"We are [team name]. We built a system that turns township CCTV from something that records crime into something that responds to it."

**Visual**
Full-bleed dark control-room screenshot of the dashboard with the alert card open. No stock photos.

---

## Slide 2 · Hook

**On slide**
- Headline: **Six burglaries in five months. Cameras, guards, fences, QR registration.**
- Sub-line: Two unfamiliar cars sat inside for over an hour. Nobody noticed.
- Footnote: A guarded community in Subang Jaya (not an SDP development). Source: EdgeProp.

**Say** (30 s)
"This is a guarded community in Subang Jaya. It had cameras, a QR visitor system, electric fencing and guards around the clock. It still had six burglaries in five months. In one case, two cars that did not belong there sat inside for over an hour.

The cameras recorded all of it. The problem was not that nobody had cameras. Nothing told anyone to look."

**Visual**
Big number "6 in 5 months" on the left. On the right, a simple row of icons for the layers they had (camera, QR, fence, guard), then a red "?" for the gap. Keep it quiet and stark.

---

## Slide 3 · Problem

**On slide**
- Headline: **Township CCTV is reactive.**
- Four short lines:
  1. The camera sees, but does not understand.
  2. A person is the only alarm.
  3. Guards get raw video, not an answer.
  4. Response arrives after the intruder has left.
- Strip along the bottom: **SDP led here:** Ara Damansara Safe City (2009) → Auxiliary Police (2016) → **Next: cameras that act.**

**Say** (40 s)
"Today an incident goes like this. The intruder enters. The camera records. No one is watching that screen. The intruder leaves. A resident discovers the loss and reports it. The guard replays the footage. By then the footage is evidence, not prevention.

This is not an SDP weakness. It is how CCTV works across the industry. And SDP has been ahead of most developers: in 2009 it linked Ara Damansara's CCTV to the police, and in 2016 it set up its own auxiliary police. The next step is making those cameras act in real time."

**Visual**
The failure chain as a horizontal flow with the stalled steps greyed out: Intruder enters → Camera records → *No one watching* → Intruder leaves → Report → Replay → Suspect gone. SDP timeline strip underneath.

**Notes**
This slide carries the Strategic Fit points. Keep the SDP strip visible. Frame it as building on existing investment, never as a criticism.

---

## Slide 4 · Why it matters

**On slide**
- Headline: **Property crime is rising, and residents feel it even where they are protected.**
- Three stat cards:
  - **+11.1%**: Malaysia's index crime in 2024, to 58,255 cases (DOSM)
  - **+12.4%**: property crime, to 47,188 cases. It drove most of the rise.
  - **65% vs 2%**: believe crime is getting worse nationally vs feel unsafe from violent crime in their own neighbourhood
- One line below: Residents of gated areas report *higher* fear of crime than non-gated residents.
- One line below that: Townships keep growing. Guards cannot scale at the same rate.

**Say** (40 s)
"Index crime rose 11.1% in 2024, and property crime drove most of that, up 12.4%. That is where we focus.

There is also a gap in how safe people feel. Only about 2% of Malaysians feel unsafe from violent crime in their own neighbourhood, yet 65% believe it is getting worse nationally. Residents of gated areas actually report higher fear than non-gated ones. Most security work is invisible, so people cannot see the protection they already pay for.

And townships like Elmina cover thousands of acres. Every phase adds cameras. Hiring guards at the same rate is not sustainable."

**Visual**
Three large numbers. Small source line under each. Dataviz rules: one accent colour only, no decorative charts.

**Notes**
Sources are in PROBLEM_STATEMENT.md (DOSM, Malay Mail, NST, EdgeProp, UiTM). Keep the footnote small but present.

---

## Slide 5 · Solution and user flow

**On slide**
- Headline: **Detect it as it happens. Tell the guard what to do. Escalate in seconds.**
- Flow diagram, left to right:
  1. **Camera feeds** (existing CCTV)
  2. **AI screening**: spots a possible snatch theft
  3. **AI verification**: confirms it, describes suspects, vehicle and escape direction
  4. **Guard decides**: Approve or Reject
  5. **Escalate**: police call and SMS, exit-gate guard alert
- Under the diagram: *Hero scenario: motorcycle snatch theft. Same pipeline extends to other crimes.*

**Say** (40 s)
"Our system watches the feeds. When it sees what looks like a motorcycle snatch theft, a second AI check confirms it and writes the alert: what happened, where, who, what vehicle, and which way they fled.

That goes to the guard in the monitoring room. The guard approves or rejects. Nothing is escalated without a human decision. On approval, the system calls the police station, sends an SMS, and alerts the guard at the exit the suspects are heading for. A township has limited exits, so a fast alert gives a real chance to intercept.

'Proactive' here means detect and alert in real time. We do not predict crime."

**Visual**
One clean left-to-right diagram. A human icon on step 4, emphasised, to show the human in the loop. Do not show the full architecture; that goes in the appendix.

**Notes**
Why snatch theft: it is counted in the rising property-crime category, it is common and emotional in Malaysia, and standard commercial analytics (line crossing, loitering, intrusion zones) do not detect it.

---

## Slide 6 · Live demo (about 2 to 3 minutes)

**On slide**
Switch to the live dashboard. No slide text beyond a small "LIVE DEMO" tag if the deck stays visible.

**Demo script**
1. **Control room.** A grid of camera feeds, each with ID, location, timestamp. "Nine feeds, one guard. This is today's reality."
2. **The snatch on CAM-07.** Let it play. Say nothing for a moment.
3. **Alert fires.** Suspect boxes turn red, tile flashes, alert card appears with replay, snapshots and description. Read one line: *"Two male suspects on a black motorcycle, pillion in red jacket, snatched a handbag, fled north toward Gate B."*
4. **Guard approves.** Escalation timeline steps: police called → SMS sent → gate alerted. Teammate's phone rings on stage.
5. **Normal street clip** on another tile. Point out that nothing fires.
6. **Incident log.** Show one approved incident and one rejected false positive.

**Say**
Keep the narration to short statements at each step. Let the product do the work. When you reach step 5: "And this is just a normal street. Nothing. It is not rigged."

**Notes**
- Do not play a clip that was used in training. [CONFIRM] which clips are held out.
- Backup: a screen recording of the full run, ready on a second device. Also use replay mode if live processing stutters (SOLUTION_PLAN.md §9).
- Twilio trial restrictions and venue Wi-Fi: test the call the day before, bring a phone hotspot.
- Anti-goal: never approve a call without showing the guard decision on screen.

---

## Slide 7 · Key features

**On slide**
- Headline: **Built to be trusted by guards, residents and regulators.**
- Four feature blocks:
  1. **Accurate**: two-step design. Fast screening misses little; AI verification removes false alarms before a guard sees them.
  2. **Actionable**: every alert says what, where, when, who, which vehicle, which way. Not "anomaly detected".
  3. **Human in the loop**: a guard approves every escalation. The system never calls the police alone.
  4. **Privacy by design**: no face recognition, no face embeddings. Snapshots stay inside the incident record and are deleted on reject. Aligned with PDPA (Amendment) 2024.

**Say** (45 s)
"Four things matter. First, accuracy. A system that cries wolf gets ignored, so the second AI check filters false alarms before they reach a guard. Second, the alert is actionable: it answers what, where, who and which way. Third, a human is always in the loop. Fourth, privacy. Biometric data is sensitive under the PDPA amendment, with penalties up to RM1 million, and face identification is unreliable on CCTV anyway. We never identify anyone. We describe, we do not recognise."

**Visual**
2×2 grid of feature cards, one icon each, one line each. A small padlock or shield for privacy. No paragraphs.

---

## Slide 8 · Evidence

**On slide**
- Headline: **We tested it, and here is what happened.**
- Metric row (all **[FILL]**, from the benchmark run):
  - Snatch clips detected: **[FILL] of [FILL]** held-out clips
  - Normal clips with a false alert: **[FILL] of [FILL]**
  - False alarms removed by AI verification: **[FILL]**
  - Snatch → alert card on screen: **[FILL] s** (design target: ≤ 10 s)
  - Guard approval → phone ringing: **[FILL] s** (design target: ≤ 5 s)
- Baseline line: *Today: time from event on camera to someone acting on it = [FILL] (guard interviews)*
- Small honest note: **What we found hard:** [FILL: e.g. a case the system missed, and what we learned]

**Say** (40 s)
"We tested on held-out clips that were not used in training. [Read the real numbers.] Compare that to today, where our guard interviews suggest [baseline]. We also found cases that were hard. [Name one and what it taught you.] We would rather show you that than hide it."

**Visual**
Five big numbers with one-line labels. A single before/after bar: "today" vs "with alerts". Use a real baseline or remove the bar.

**Notes**
- The benchmark and baseline are not done yet. Do not present any number here until it has been measured. Design targets from SOLUTION_PLAN.md §8 may be shown only if labelled "target".
- Showing one honest limitation raises credibility with judges; it does not lower it. Pick the real one from the benchmark. [CONFIRM] against the current known misses.
- If there is no guard-interview baseline by pitch day, drop the baseline line and say plainly it is the first thing a pilot measures.

---

## Slide 9 · Impact and value

**On slide**
- Headline: **Faster response, fewer blind spots, security residents can feel.**
- Three columns:
  - **Residents**: a response chain that visibly works, so real safety becomes felt safety.
  - **Guards and auxiliary police**: fewer screens to watch blindly, clear priorities, one consistent procedure on every shift.
  - **SDP and township management**: security that scales with each new phase without guard headcount growing at the same rate, plus measurable proof the security budget works.
- Bottom strip, **How we will measure it:** detection-to-response time · share of incidents noticed live vs afterwards · alerts per guard and false-alert share · cameras covered per staff member · resident sense of safety

**Say** (40 s)
"For residents, security becomes something they can see working. For guards, it replaces staring at nine screens with a clear priority list and a standard procedure, the same on every shift. For SDP, it is a way to grow the township without growing guard headcount at the same rate, and to show that security spending works, with numbers.

These are the measures we would track in a pilot."

**Visual**
Three stakeholder columns with a simple icon each. Measurement strip at the bottom in a lighter style.

**Notes**
These are outcomes to measure, not results already achieved. Do not state a percentage improvement unless it was measured.

---

## Slide 10 · Why we stand out

**On slide**
- Headline: **Other approaches watch for rules. We watch for crime.**
- Comparison table:

| | Guards watching screens | Rule-based CCTV analytics | **Ours** |
|---|---|---|---|
| Notices events live | Only if looking at the right screen | Yes, for simple rules | **Yes** |
| Detects a crime in progress (e.g. snatch theft) | Only if seen | No: line crossing, loitering, intrusion zones only | **Yes** |
| Explains what happened | A person interprets | No: "rule triggered" | **Description with suspects, vehicle, direction** |
| Guides the next step | Varies by shift | No | **Approve → escalate with one tap** |
| Human decision before escalation | n/a | Varies | **Always** |
| Builds on existing cameras | n/a | Yes | **Yes** |

- Footer: *Not repackaging an alarm. Turning footage into an answer.*

**Say** (35 s)
"Rule-based analytics are already sold as standard: line crossing, loitering, intrusion zones. They tell you a rule was broken, not what happened. A snatch theft breaks no line. Our system looks at the action, then explains it, then guides the response, and a human stays in control. And it runs on the cameras the township already has."

**Visual**
The table, trimmed to the rows above. Highlight the "Ours" column. No vendor logos.

**Notes**
- Do not name specific vendors or claim what they cannot do unless verified. The comparison is to categories, which is defensible. [CONFIRM] the "builds on existing cameras" claim against how the pilot would connect to a real video system.
- If asked "isn't this just an AI camera?": the difference is the full chain: detect a crime, describe it, human approval, and automatic escalation including exit gates.

---

## Slide 11 · Customers, collaborators and who pays

**On slide**
- Headline: **Built for SDP townships first, designed to scale beyond.**
- Left, **Customers:**
  - Primary: SDP township management and security (e.g. City of Elmina, Bandar Bukit Raja, Ara Damansara)
  - Next: other township developers, gated and guarded communities, commercial precincts
- Middle, **Collaborators:**
  - SDP Auxiliary Police unit: the operators of the CMS
  - PDRM: receives earlier, better-quality information
  - Existing CCTV and video-management vendors: integration
- Right, **How it could be paid for (to validate in pilot):**
  - [FILL: choose and test one: per-camera subscription / included in township management fees / SDP-owned tool]

**Say** (35 s)
"The first customer is SDP's own township security team. They already run CCTV and an auxiliary police unit, so we plug into what exists. The collaborators are the people already in the response chain: the auxiliary police who monitor, PDRM who respond, and the CCTV vendors whose systems we connect to. Once it works in one township, the same product applies to any guarded community with cameras. We have a hypothesis for the commercial model, and the pilot is how we test it."

**Visual**
Three columns. Small icons. The "who pays" column should look intentionally provisional.

**Notes**
Do not state prices unless researched. Do not claim PDRM has agreed to anything. The police call in the demo goes to a teammate's phone; say so if asked.

---

## Slide 12 · Roadmap: pilot and scale

**On slide**
- Headline: **Start with one zone. Prove it. Then scale.**
- Four-step timeline:
  1. **Now**: working prototype, tested on staged and held-out clips
  2. **Pilot (e.g. 8 to 12 weeks)**: one shoplot row or bus-stop zone in one township, on existing cameras. *Shadow mode first:* alerts go to guards, escalation stays manual. Measure response time, false alerts per shift, and guard feedback.
  3. **Township rollout**: all cameras in a township, live escalation to auxiliary police and exit gates, real PDRM channel
  4. **Scale**: more crime types on the same pipeline (fights, break-ins, assaults), more townships
- Pilot success criteria: **[FILL: target response time and false-alert level agreed with SDP security]**

**Say** (40 s)
"We would not start by switching on police calls. The pilot begins in shadow mode: one zone, existing cameras, alerts to guards only. We measure response time and false alerts, and we get the guards' feedback. Once the numbers are good, escalation goes live and we widen from one zone to a township. Other crimes use the same pipeline with a new detection model."

**Visual**
Horizontal timeline with four milestones. The pilot is emphasised, with its measures listed beneath.

**Notes**
- Feasibility is 20%. The shadow-mode pilot is the answer to "could this be piloted within a township environment?". Keep it concrete.
- Timeline and scope are proposals. Do not imply SDP has agreed to a pilot.
- Out of scope today, and worth saying in Q&A: real PDRM integration, real camera hardware, multi-township, access control.

---

## Slide 13 · Closing

**On slide**
- Headline: **The camera saw it. This time, someone is told.**
- Three lines:
  - Detect in real time, so there is still time to act.
  - A guard decides, so a human is always responsible.
  - Built on what SDP already has.
- **Our ask:** a pilot in one SDP township. [FILL: any support asked for, e.g. access to a camera zone and security team for interviews]
- Team names and contact.

**Say** (25 s)
"Back to Subang Jaya. The cameras were there. What was missing was a way to tell someone. With this system, the camera does not only record: it tells the guard, the guard decides, and the township responds while there is still time. We would like to pilot it in one SDP township. Thank you."

**Visual**
Same dark treatment as the cover. One quiet line, one ask. No new information.

---

## Timing (about 7 minutes)

| Slide | Seconds |
|---|---|
| 1 Cover | 10 |
| 2 Hook | 30 |
| 3 Problem | 40 |
| 4 Why it matters | 40 |
| 5 Solution and flow | 40 |
| 6 Live demo | 150 |
| 7 Key features | 45 |
| 8 Evidence | 40 |
| 9 Impact | 40 |
| 10 Why we stand out | 35 |
| 11 Customers and collaborators | 35 |
| 12 Roadmap | 40 |
| 13 Closing | 25 |
| **Total** | **~ 710 s** |

**Cut list if the slot is shorter**
- 5 minutes: merge slides 3 and 4, merge 9 and 11, drop the table detail on slide 10.
- 3 minutes: slides 1, 2, 5, 6 (shortened demo), 8, 12, 13.

---

## Appendix slides (not presented, ready for Q&A)

**A1 · Architecture.** The diagram from SOLUTION_PLAN.md §5. [CONFIRM] it matches the current build: the screening and verification model choices have changed during development.

**A2 · Risks and fallbacks.** From SOLUTION_PLAN.md §9: replay mode, hotspot, cached results, Twilio limits.

**A3 · Data and training.** Training sources, held-out split by video, demo clips never used for training.

**A4 · Privacy.** No face recognition, no embeddings; PDPA (Amendment) 2024 reference; snapshot deletion on reject.

---

## Likely Q&A

**What about false alarms?**
Two-step design: the second check removes most before a guard sees them, and the guard can reject the rest. We report the false-alarm numbers from the benchmark on slide 8 [FILL]. In a pilot, false alerts per shift is a measured success criterion.

**Why not just hire more guards?**
Cost grows with every phase, and a person watching many feeds still cannot see everything. This lets existing guards focus on what matters. It supports guards; it does not replace them.

**Does it identify people?**
No. It describes clothing and vehicles. No face recognition, no embeddings. Biometric data is sensitive under the PDPA (Amendment) 2024.

**What if the AI is wrong and the guard approves?**
A human always approves, and the alert shows the replay so the guard can see the evidence. The system never calls the police alone.

**Is the police call real?**
In the demo it goes to a teammate's phone to show the chain. A real PDRM channel is a pilot-to-rollout step that needs their agreement.

**Does it work at night or in the rain?**
[FILL: only answer from tested clips. If not tested, say so and say that day, night and rain clips are part of the pilot measurement.]

**What does it cost?**
[FILL: only if researched.] Otherwise: running costs depend on the number of analysed cameras and how often a candidate reaches the verification step; the pilot establishes the real figure.

**What happens if the internet is down?**
[CONFIRM] against the current build. State honestly what is needed on site and what is not.

**How is this different from existing CCTV analytics?**
Slide 10: they detect rule breaks, such as crossing a line. We detect an action, describe it, and drive the response chain with a human in control.

---

## Before building the deck

Must do:
- [ ] Run the benchmark and fill slide 8
- [ ] Decide which demo clips are held out, and confirm none were used in training
- [ ] Get a guard-interview baseline, or decide to drop that line
- [ ] Rehearse the demo end to end, with a recorded backup
- [ ] Verify the Twilio call from the demo device and the hotspot

Should do:
- [ ] Choose the pilot location and duration for slide 12
- [ ] Decide the commercial hypothesis for slide 11
- [ ] Confirm the architecture slide matches the build

Do not:
- State numbers that have not been measured
- Imply SDP or PDRM have agreed to anything
- Show real victims; use staged clips only
