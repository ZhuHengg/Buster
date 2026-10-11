# Problem Statement

**Sime Darby Property University Hackathon 2026**
**Theme 1: People / Safety & Security**

---

## The problem

> Sime Darby Property has built some of the strongest security foundations of any Malaysian township developer: guarded neighbourhoods, a dedicated auxiliary police unit, and CCTV networks going back to the Ara Damansara Safe City initiative. But township CCTV, like CCTV across the industry, is **reactive**. Cameras record everything and alert no one. A suspicious event is only noticed if a person happens to be watching the right screen at the right moment, and even then the system offers no clear next step. By the time anyone notices, decides and responds, the intruder is usually gone, and the footage becomes evidence for a police report instead of a way to stop the crime.

**How might we** make township CCTV proactive, so that suspicious activity is detected as it happens and turned into a clear, actionable alert for security teams while there is still time to act?

The core problem: **CCTV is reactive, not proactive.** It depends on people to notice, gives them nothing actionable to work with, and so the response comes too late. This is an industry-wide challenge. It is not a weakness specific to SDP.

---

## Why it matters

**Property crime is rising nationally.**
- Malaysia's index crime rose 11.1% in 2024 to 58,255 cases.
- Property crime (housebreaking, vehicle theft) drove most of the increase, up 12.4% to 47,188 cases.
- Robbery and homicide fell, so property crime is the right focus.

**Across Malaysia, more security layers have not automatically meant fewer incidents.**
- One guarded community in Subang Jaya (not an SDP development) had cameras, QR visitor registration, electric fencing and 24/7 guards. It still had 6 burglaries in 5 months. In one incident, two unfamiliar cars sat inside for over an hour without anyone noticing.
- Elsewhere, burglars drove luxury cars to get past guards, and intruders used cloned access cards.
- A Malaysian study on gated and guarded schemes concluded that physical layers alone are not enough, and called for smarter security tools.
- In each of these cases, the cameras were there. What was missing was an alert: nothing told anyone to look while it was happening.

**Residents' sense of safety does not match the protection they have.**
- Only about 2% of Malaysians feel unsafe from violent crime in their own neighbourhood, yet 65% believe crime is getting worse nationally.
- Residents of gated areas report *higher* fear of crime than residents of non-gated areas.
- Most security work happens out of sight, so residents cannot see the protection they already pay for.

**Townships are growing.**
- SDP townships such as City of Elmina cover thousands of acres.
- Every new phase adds cameras, gates and patrol routes. Adding guards at the same rate is costly and does not scale.

---

## Root cause: CCTV is reactive, not proactive

**How an incident typically plays out today:**

```
Intruder enters ──► Camera records it ──► No one is watching that screen
        │
        ▼
Intruder leaves ──► Resident discovers the loss ──► Reports it to the guardhouse
        │
        ▼
Guard replays the footage ──► Police report filed ──► Suspect is long gone
```

The cameras did their job: they captured everything. But nothing in the system *acted* on what it captured.

**Why CCTV ends up reactive:**

1. **The camera sees, but does not understand.** CCTV records pixels. It does not know that someone climbing a fence at 2am is different from a resident walking a dog. Every event looks the same to the system until a person interprets it.
2. **A person is the only alarm.** Detection depends entirely on a guard watching the right screen at the right moment. One person can only watch so many feeds, and attention drops quickly during continuous monitoring. As townships add cameras with every new phase, this gets worse.
3. **No actionable output.** Even when a guard does spot something, the system gives them raw video, not answers to *what is happening, where, how urgent, and what to do next*. The guard must interpret, decide and call someone, all under pressure, and the result varies by shift and by person.
4. **Response arrives too late.** Noticing late, plus deciding manually, plus escalating by phone, adds up. By the time security reaches the location, the intruder has left. Footage that could have prevented the crime only helps explain it afterwards.

**Contributing factors:**
- **Fragmented signals.** Guardhouse cameras, residents' doorbell cameras, WhatsApp group reports and patrol observations do not reach one place, so each piece of early warning is seen in isolation.
- **No consistent escalation path.** The route from guard to township security, auxiliary police and PDRM is informal, which slows response further.

---

## Who is affected

| Stakeholder | Need |
|---|---|
| Residents | To feel as safe as they actually are, and to see that something happens when they report a concern |
| Guards / auxiliary police | Fewer screens to watch blindly; clear priorities; a consistent procedure for what to do next |
| Township management (SDP) | Security that scales with township growth without staffing growing at the same rate; measurable proof that security spending works |
| PDRM | Earlier, better-quality information instead of footage reviewed after the fact |

---

## Scope

**In scope**
- Public areas within SDP townships that township CCTV covers: shoplot rows, bus stops, internal roads and walkways (for example City of Elmina, Bandar Bukit Raja, Ara Damansara).
- **Crimes in progress that commercial CCTV analytics do not detect**, starting with motorcycle snatch theft. Snatch theft ("curi ragut") is counted as property crime in PDRM's index crime, the category that is rising. Simple rule-based events such as fence climbing, loitering and line crossing are already sold as standard features, so they are not the focus.
- The response chain from camera to guard, then to township security or auxiliary police, then to PDRM, including alerting exit-gate guards. A township has a limited number of exits, so a fast alert gives a real chance to intercept.
- Building on SDP's existing CCTV and auxiliary police rather than replacing them.

**Out of scope (for now)**
- Other crime types (fights, break-ins, assaults). They use the same pipeline with a new detection model and are a later extension.
- Verbal harassment, which CCTV cannot reliably detect.
- Identifying individuals by face. Biometric data is classed as sensitive personal data under the PDPA (Amendment) 2024, with penalties up to RM1M. Face identification is also unreliable on typical CCTV (night, angles, helmets).

---

## Storytelling framings

The core problem stays the same in every framing. Only the pitch's opening and its human focus change. Every framing positions the solution as **building on what SDP already has**.

### Story A: "From recording to responding" *(primary)*
SDP was an early mover. In 2009 it linked Ara Damansara's CCTV directly to the police, and in 2016 it set up its own auxiliary police. The next step is making those cameras and teams act in real time. Use the industry cases (the Subang Jaya community with every layer in place, yet an unfamiliar car sat inside unnoticed for an hour) to show that reactive CCTV alone is not enough: the camera saw it, but nothing alerted anyone. Present the solution as SDP's next generation of township security, moving CCTV from reactive to proactive.

### Story B: "The walk home"
A resident (a woman coming home from work, an elderly person, a teenager) walks from the bus stop to their gate at night. The township is safe, but they do not feel safe, so they avoid walking. Security they can see and trust turns real safety into felt safety. This links Safety & Security to wellbeing and mobility.

### Story C: "One township, one picture"
One incident, seen from every side: a doorbell camera clip in the WhatsApp group, a guard watching another screen, a patrol across town. Each piece of information exists, but no one sees the whole picture. The solution connects what SDP's security teams and residents already see.

---

## Assumptions to validate

| Assumption | How to validate |
|---|---|
| Guards cannot effectively monitor the number of feeds they are given | Interview 3–5 guards or auxiliary police: number of screens, shift length, what they actually watch |
| Most incidents are noticed after they happen rather than live | Review recent incidents with the residents' association or township management: was it on camera, and when was it first noticed? |
| Residents cannot see what their security is doing | Interview 10+ residents in an SDP township |
| Escalation varies by shift and individual | Ask guards to walk through their last incident step by step |
| Security cost grows with each new township phase | Ask township management how guard headcount has changed as phases opened |

**Key number to establish:** the average time from an event appearing on camera to someone acting on it. This is the baseline any solution must improve.

---

## Measures of success (problem level)

- Detection-to-response time (minutes): from an event appearing on camera to a guard acting on it.
- Share of incidents noticed live vs. discovered afterwards.
- Residents' sense of safety in their own neighbourhood.
- Guard workload: number of feeds or alerts per guard, and how many of those alerts are false.
- Number of cameras each security staff member can effectively cover.

---

## Sources

- [DOSM – Crime Statistics Malaysia 2025](https://dosm.gov.my/portal-main/release-content/crime-statistics-malaysia-2025)
- [Malay Mail – Malaysia's crime rate up 11.1% in 2024](https://www.malaymail.com/amp/news/malaysia/2025/10/16/dosm-malaysias-crime-rate-up-111pc-in-2024-led-by-property-and-assault-offences/194807)
- [NST – Violent crime fears rise, but homicide rate stays low](https://www.nst.com.my/amp/news/nation/2025/06/1232062/violent-crime-fears-rise-homicide-rate-stays-low)
- [EdgeProp – USJ Heights residents living in fear despite paying for security](https://api.edgeprop.my/content/1420819/usj-heights-residents-living-fear-despite-paying-security-facilities)
- [NST – Burglars use luxury cars to fool guards into letting them into gated communities](https://nst.com.my/amp/news/crime-courts/2018/08/396789/burglars-use-luxury-cars-fool-guards-letting-them-gated-communities)
- [UiTM – Effective security in gated communities and guarded neighbourhoods in Malaysia](https://openaccess.library.uitm.edu.my/Record/ir_utm_79128)
- [Fear of crime in residential areas (Sakip, Abdullah & Salleh)](https://oalib-perpustakaan.upi.edu/Record/repouitm_8771/Description)
- [Rajah & Tann – The Personal Data Protection (Amendment) Bill 2024](https://www.rajahtannasia.com/?p=154128)
- [Sime Darby Property – Auxiliary Police unit](https://www.simedarbyproperty.com/node/368)
- [Sime Darby Property – Ara Damansara Safe City](https://www.simedarbyproperty.com/node/135)
- [Edgeprop – City of Elmina, sustainable integrated township](https://www.edgeprop.my/content/1912815/city-elmina—-sustainable-integrated-township)
