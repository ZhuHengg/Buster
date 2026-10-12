# Filming Guide: Staged Clips

These clips train and test the Phase 2 action model, and some of them become the demo clips. Spec reference: [SOLUTION_PLAN.md](SOLUTION_PLAN.md) §7 and §12.

## What to film

| Take type | Minimum | Notes |
|---|---|---|
| Snatch | **15 takes** | 2-3 different high fixed angles; film both day and dusk |
| Normal | **10 takes** | Same spots and same angles as the snatch takes, same light |

More is better. The model learns what "nothing happening" looks like from the normal takes, so film the things that look like a snatch but are not (see below).

### The snatch take (about 20 s per take)

1. Start with 5 s of the empty scene, then a pedestrian (the "victim") walks in carrying a bag on the shoulder side nearest the road.
2. A motorcycle with **two riders** approaches from behind or from the side, at walking-pace plus a little. Slow, never fast.
3. The pillion reaches out and takes the bag (the actors hold on gently and let go; nobody is pulled).
4. The motorcycle accelerates away. Let it ride out of frame, and keep recording 5 s after.
5. The victim stays in frame for a few seconds (stumbles, turns, stands).

Vary between takes: the side the motorcycle comes from, the victim's walking direction, bag type, clothing colour (the pillion in red once, dark once), helmet colour, and one or two takes with a second pedestrian or a parked car in the scene.

### The normal take (about 20 s per take)

Same spot, same framing. Mix these:

- Pedestrians walking, with and without a bag.
- A motorcycle riding past, near a pedestrian, without any grab (this is the hard negative that matters most).
- A motorcycle stopping and a rider talking to a pedestrian.
- Two people handing over a bag or a parcel.
- Someone jogging or running, someone dropping and picking up a bag.
- Parked motorcycles with people walking between them.
- At least 2 takes with an empty scene.

## Camera setup

- Phone mounted **at least 2.5 m high**, pointing down at the pavement, fixed (tripod, clamp or bracket). No hand-holding, no zoom, no movement during a take.
- **1080p, 30 fps, landscape.** Lock exposure and focus if the phone allows it.
- Frame the road edge and pavement so a motorcycle and a pedestrian are each at least 5% of the frame height.
- Film at least 2 different spots, 3 if possible. Do not reuse the same spot for every take, otherwise the model learns the background.
- Day and dusk. Night is a bonus if the lighting is safe.

## Safety and permission (not optional)

- Film on **private ground or with the owner's written or recorded permission**. Warn the property guards beforehand so that nobody thinks it is a real crime.
- Riders wear helmets and ride slowly. No real grabbing or pulling; a **fake bag** with nothing valuable inside.
- Actors are team members or friends who agreed to be filmed. Nobody else is recognisable in the frame; stop and re-shoot if a passer-by walks through.
- Have a spotter at the road to stop the take if a car comes.

## Direction of escape

For every camera position, write down which way the motorcycle leaves **in the image** (left / right / up / down) and which township gate lies that way. This goes into `backend/data/cameras.json` (`exits`) for any clip used on a demo camera.

```
spot_a: leaves image-right -> Gate B
spot_b: leaves image-left  -> Gate A
```

Keep this note next to the clips (`backend/data/datasets/staged/README.txt`).

## File naming

```
staged_<spot>_<take>_<snatch|normal>.mp4
```

Examples: `staged_gateB_01_snatch.mp4`, `staged_gateB_07_normal.mp4`, `staged_shoplotA_03_snatch.mp4`.

Rules:

- `<spot>` has no spaces or underscores (`gateB`, `shoplotA`).
- `<take>` is a two-digit number, unique per spot.
- Do not trim the clips: keep a few seconds before and after the event. The labelling tool marks the exact segment.
- H.264 `.mp4` (the phone default). Check with `uv run python scripts/probe_clips.py`.

## After filming

1. Copy the clips to `backend/data/datasets/staged/`.
2. `cd backend`, then `uv run python -m training.ingest data/datasets/staged --origin staged --angle high --light day` (change `--light` per batch; run it once for each batch of the same light).
3. For each snatch clip: `uv run python -m training.label_tool data/datasets/staged/staged_gateB_01_snatch.mp4`. Mark the snatch segment (about 2-3 s: the approach of the pillion's arm, the grab, the first moment of getaway) with `[` and `]`, then `s`.
4. Normal clips (`*_normal.mp4`) go into a folder whose name contains `normal` so that ingest labels them as whole-video `normal` automatically, for example `backend/data/datasets/staged/normal/`.

Hold back a few snatch takes (and at least one whole spot) as the **demo clips**. Put them in `backend/data/` and `cameras.json` instead of `datasets/`. They are then never used for training, validation or testing selection.
