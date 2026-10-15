import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import cv2
from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import CameraConfig, Settings, load_cameras
from app.escalation.escalator import Escalator, make_escalator
from app.incidents.service import IncidentService
from app.incidents.store import IncidentStore
from app.models import Incident, IncidentStatus, InvalidTransition
from app.playback import PlaybackControl
from app.reports import load_reports
from app.verify.base import Verifier
from app.verify.mock_verifier import make_verifier
from app.ws import WsHub

log = logging.getLogger("cms")

FRONTEND_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


class DecisionBody(BaseModel):
    operator: str | None = None


class LoopBody(BaseModel):
    loop: bool


class PauseBody(BaseModel):
    paused: bool


def probe_sync_info(path: Path) -> dict | None:
    """fps / duration / size of a clip, for the frontend's playback sync."""
    if not path.exists():
        return None
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not fps or not frames:
            return None
        return {
            "fps": fps,
            "duration": frames / fps,
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        }
    finally:
        cap.release()


async def _supervise(name: str, coro) -> None:
    try:
        await coro
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("pipeline %s stopped", name)


async def _build_pipelines(app: FastAPI) -> list:
    from app.pipeline import CameraPipeline, ReplayPipeline
    from app.trigger import make_trigger
    from app.video.buffer import FrameBuffer

    settings: Settings = app.state.settings
    pipelines = []
    for cam in app.state.cameras:
        if not cam.analyse:
            continue
        if settings.mode == "replay":
            path = settings.data_dir / "precomputed" / f"{cam.id}.json"
            if not path.exists():
                log.warning("replay file missing for %s: %s (run scripts/precompute.py)", cam.id, path)
                continue
            pipelines.append(
                ReplayPipeline(cam, path, app.state.service, app.state.hub, suspect_flag_s=settings.suspect_flag_s,
                               control=app.state.playback)
            )
        else:
            from app.detect.detector import Detector

            detector = await asyncio.to_thread(Detector)  # one tracker state per stream
            buffer = FrameBuffer()  # shared: the pipeline fills it, the Gemini trigger reads it
            pipelines.append(
                CameraPipeline(
                    cam, settings, detector, make_trigger(settings, cam, buffer), app.state.verifier,
                    app.state.service, app.state.hub, buffer, control=app.state.playback,
                )
            )
    return pipelines


def create_app(
    settings: Settings | None = None,
    escalator: Escalator | None = None,
    verifier: Verifier | None = None,
    start_pipelines: bool = True,
) -> FastAPI:
    settings = settings or Settings()
    hub = WsHub()
    snapshots_dir = settings.data_dir / "snapshots"

    async def on_change(incident: Incident) -> None:
        await hub.broadcast({"type": "incident.updated", "incident": incident.model_dump(mode="json")})

    service = IncidentService(IncidentStore(settings.db_path), snapshots_dir, on_change)
    cameras = load_cameras(settings.data_dir / "cameras.json")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks: list[asyncio.Task] = []
        if start_pipelines:
            for pipeline in await _build_pipelines(app):
                tasks.append(asyncio.create_task(_supervise(type(pipeline).__name__, pipeline.run())))
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="CCTV Alert CMS", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"]
    )
    app.state.settings = settings
    app.state.hub = hub

    async def on_playback(state: dict) -> None:
        await hub.broadcast({"type": "playback", **state})

    app.state.playback = PlaybackControl(on_playback)
    app.state.service = service
    app.state.cameras = cameras
    app.state.verifier = verifier or make_verifier(settings)
    app.state.escalator = escalator or make_escalator(settings, service)
    cameras_by_id: dict[str, CameraConfig] = {c.id: c for c in cameras}
    sync_info = {c.id: probe_sync_info(settings.data_dir / c.clip) if c.clip else None for c in cameras}

    # ---- REST ----------------------------------------------------------------------------
    @app.get("/api/cameras")
    async def get_cameras() -> list[dict]:
        return [{**c.model_dump(), "sync": sync_info[c.id]} for c in cameras]

    @app.get("/api/playback")
    async def get_playback() -> dict:
        return app.state.playback.snapshot()

    @app.post("/api/playback")
    async def set_playback(body: LoopBody) -> dict:
        # loop off: every camera plays its clip once and holds; loop on: resume from the start
        await app.state.playback.set_loop(body.loop)
        return app.state.playback.snapshot()

    @app.post("/api/playback/pause")
    async def pause_playback(body: PauseBody) -> dict:
        # every camera freezes on its current frame (alerts already raised carry on); resume continues
        await app.state.playback.set_paused(body.paused)
        return app.state.playback.snapshot()

    @app.post("/api/playback/restart")
    async def restart_playback() -> dict:
        await app.state.playback.restart()
        return app.state.playback.snapshot()

    @app.get("/api/reports")
    async def get_reports() -> dict:
        # a fresh clone has no reports: sections are null and generated_hint says how to make them
        return load_reports(settings.reports_dir, settings.data_dir / "labels.csv")

    @app.get("/api/incidents")
    async def list_incidents(status: IncidentStatus | None = None) -> list[Incident]:
        return service.store.list(status)

    @app.get("/api/incidents/{incident_id}")
    async def get_incident(incident_id: str) -> Incident:
        incident = service.store.get(incident_id)
        if incident is None:
            raise HTTPException(404, "incident not found")
        return incident

    @app.delete("/api/incidents/{incident_id}")
    async def delete_incident(incident_id: str) -> dict:
        try:
            await service.delete(incident_id)
        except KeyError:
            raise HTTPException(404, "incident not found")
        await hub.broadcast({"type": "incident.deleted", "id": incident_id})
        return {"id": incident_id}

    async def _escalate(incident: Incident) -> None:
        camera = cameras_by_id.get(incident.camera_id)
        if camera is None:
            log.error("no camera %s for incident %s", incident.camera_id, incident.id)
            return
        try:
            await app.state.escalator.escalate(incident, camera)
        except Exception:
            log.exception("escalation failed for %s", incident.id)

    async def _decide(incident_id: str, body: DecisionBody | None, approve: bool) -> Incident:
        operator = (body.operator if body and body.operator else None) or settings.operator_name
        try:
            if approve:
                return await service.approve(incident_id, operator)
            return await service.reject(incident_id, operator)
        except KeyError:
            raise HTTPException(404, "incident not found")
        except InvalidTransition as exc:
            raise HTTPException(409, f"already handled ({exc})")

    @app.post("/api/incidents/{incident_id}/approve")
    async def approve(incident_id: str, background: BackgroundTasks, body: DecisionBody | None = None) -> Incident:
        incident = await _decide(incident_id, body, approve=True)
        background.add_task(_escalate, incident)
        return incident

    @app.post("/api/incidents/{incident_id}/reject")
    async def reject(incident_id: str, body: DecisionBody | None = None) -> Incident:
        return await _decide(incident_id, body, approve=False)

    # ---- media (FileResponse honours HTTP Range, which <video> seeking needs) -------------
    def _serve(root: Path, name: str, suffixes: tuple[str, ...], media_type: str) -> FileResponse:
        path = root / name
        if Path(name).name != name or path.suffix.lower() not in suffixes or not path.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(path, media_type=media_type)

    @app.get("/media/clips/{file}")
    async def clip(file: str) -> FileResponse:
        return _serve(settings.data_dir, file, (".mp4",), "video/mp4")

    @app.get("/media/snapshots/{file}")
    async def snapshot(file: str) -> FileResponse:
        return _serve(snapshots_dir, file, (".jpg", ".jpeg"), "image/jpeg")

    # ---- websocket -----------------------------------------------------------------------
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await hub.connect(ws)
        try:
            while True:
                await ws.receive_text()  # we only push; reading detects the disconnect
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(ws)

    return app


def __getattr__(name: str) -> Any:
    # `uvicorn app.main:app` builds the real app on first access, so importing this module
    # (tests, create_app callers) has no side effects
    if name == "app":
        instance = create_app()
        globals()["app"] = instance
        return instance
    raise AttributeError(name)
