"""Schedule CRUD and run-now endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import AuditLogDoc, ScanDoc, ScheduleDoc, ScanStatus, TriggerType
from shared.logging import get_logger, get_request_id
from shared.pubsub_client import publish_run_scan
from shared.repositories.audit_store import AuditStore
from shared.repositories.scan_store import ScanStore
from shared.repositories.schedule_store import ScheduleStore
from shared.schemas import (
    ScheduleCreateRequest,
    ScheduleResponse,
    ScheduleUpdateRequest,
    ScanResponse,
    ScanStatusEnum,
    TriggerTypeEnum,
)
from shared.utils import generate_uuid

from api_service.deps import db_session

router = APIRouter(prefix="/schedules", tags=["schedules"])
logger = get_logger(__name__)


def _schedule_response(s: ScheduleDoc) -> ScheduleResponse:
    return ScheduleResponse(
        id=s.id, repo_id=s.repo_id, branch=s.branch,
        interval_minutes=s.interval_minutes,
        cron_expression=s.cron_expression,
        run_once=s.run_once,
        enabled=s.enabled, next_run_at=s.next_run_at,
        created_at=s.created_at, updated_at=s.updated_at,
    )


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    db: AsyncClient = Depends(db_session),
) -> list[ScheduleResponse]:
    """List all scan schedules."""
    store = ScheduleStore(db)
    schedules = await store.list_schedules()
    return [_schedule_response(s) for s in schedules]


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    body: ScheduleCreateRequest,
    db: AsyncClient = Depends(db_session),
) -> ScheduleResponse:
    """Create a new scan schedule for a repo + branch."""
    schedule_store = ScheduleStore(db)
    audit_store = AuditStore(db)

    schedule = ScheduleDoc(
        id=str(generate_uuid()),
        repo_id=str(body.repo_id),
        branch=body.branch,
        # artifact_uri intentionally ignored server-side (frontend no longer supplies artifact URIs)
        interval_minutes=body.interval_minutes,
        cron_expression=body.cron_expression,
        run_once=body.run_once,
        enabled=True,
    )
    
    # Calculate initial run time
    if body.cron_expression:
        from croniter import croniter
        if not croniter.is_valid(body.cron_expression):
            raise HTTPException(status_code=400, detail="Invalid cron expression")
        schedule.next_run_at = croniter(body.cron_expression, datetime.now(timezone.utc)).get_next(datetime)
    else:
        # Fallback to immediate or interval? Usually schedules start immediately or +interval
        schedule.next_run_at = datetime.now(timezone.utc)

    await schedule_store.create_schedule(schedule)

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="create_schedule",
        entity_type="schedule",
        entity_id=schedule.id,
        status="created",
    ))

    logger.info("schedule_created", schedule_id=schedule.id)
    return _schedule_response(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    body: ScheduleUpdateRequest,
    db: AsyncClient = Depends(db_session),
) -> ScheduleResponse:
    """Partially update a schedule."""
    schedule_store = ScheduleStore(db)
    audit_store = AuditStore(db)

    schedule = await schedule_store.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    update_data = body.model_dump(exclude_unset=True)
    # Convert enum values
    for key, value in update_data.items():
        if hasattr(value, "value"):
            update_data[key] = value.value
    # Ignore artifact_uri updates from frontend — artifact handling moved to server/runner
    update_data.pop("artifact_uri", None)

    await schedule_store.update_schedule(schedule_id, update_data)

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="update_schedule",
        entity_type="schedule",
        entity_id=schedule_id,
        status="updated",
        details_json=update_data,
    ))

    updated = await schedule_store.get_schedule(schedule_id)
    logger.info("schedule_updated", schedule_id=schedule_id)
    return _schedule_response(updated)


@router.post("/{schedule_id}/run", response_model=ScanResponse, status_code=201)
async def run_schedule_now(
    schedule_id: str,
    db: AsyncClient = Depends(db_session),
) -> ScanResponse:
    """Immediately trigger a scan from a schedule."""
    schedule_store = ScheduleStore(db)
    scan_store = ScanStore(db)
    audit_store = AuditStore(db)

    schedule = await schedule_store.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    scan = ScanDoc(
        id=str(generate_uuid()),
        repo_id=schedule.repo_id,
        branch=schedule.branch,
        trigger_type=TriggerType.SCHEDULED,
        status=ScanStatus.QUEUED,
    )
    await scan_store.create_scan(scan)

    publish_run_scan(scan.id)

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="run_schedule_now",
        entity_type="scan",
        entity_id=scan.id,
        status="created",
        details_json={"schedule_id": schedule_id},
    ))

    logger.info("schedule_run_now", schedule_id=schedule_id, scan_id=scan.id)
    return ScanResponse(
        id=scan.id, repo_id=scan.repo_id, branch=scan.branch,
        trigger_type=TriggerTypeEnum(scan.trigger_type.value),
        status=ScanStatusEnum(scan.status.value),
        created_at=scan.created_at, updated_at=scan.updated_at,
    )


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    db: AsyncClient = Depends(db_session),
) -> None:
    """Delete a scan schedule."""
    schedule_store = ScheduleStore(db)
    audit_store = AuditStore(db)

    schedule = await schedule_store.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await schedule_store.delete_schedule(schedule_id)

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="delete_schedule",
        entity_type="schedule",
        entity_id=schedule_id,
        status="deleted",
    ))

    logger.info("schedule_deleted", schedule_id=schedule_id)


@router.post("/tick", status_code=200)
async def trigger_due_schedules(
    db: AsyncClient = Depends(db_session),
) -> dict:
    """Check for due schedules and trigger scans.
    
    Intended to be called by Cloud Scheduler (e.g., every 5 minutes).
    """
    schedule_store = ScheduleStore(db)
    scan_store = ScanStore(db)
    audit_store = AuditStore(db)
    
    now = datetime.now(timezone.utc)
    due = await schedule_store.list_due_schedules(now)
    
    triggered_count = 0
    
    for schedule in due:
        # 1. Create Scan
        scan = ScanDoc(
            id=str(generate_uuid()),
            repo_id=schedule.repo_id,
            branch=schedule.branch,
            trigger_type=TriggerType.SCHEDULED,
            status=ScanStatus.QUEUED,
        )
        await scan_store.create_scan(scan)
        
        # 2. Publish Event
        publish_run_scan(scan.id)
        
        # 3. Handle run_once or calculate next run
        if schedule.run_once:
            # Disable one-time schedules immediately
            await schedule_store.update_schedule(schedule.id, {"enabled": False, "next_run_at": None})
        else:
            if schedule.cron_expression:
                from croniter import croniter
                try:
                    # Use current time as base for next run
                    iter = croniter(schedule.cron_expression, now)
                    next_run = iter.get_next(datetime)
                except Exception as e:
                    logger.error("schedule_cron_error", schedule_id=schedule.id, error=str(e))
                    # Disable broken schedule to prevent loops
                    await schedule_store.update_schedule(schedule.id, {"enabled": False})
                    continue
            else:
                # Fallback to interval
                from datetime import timedelta
                interval = schedule.interval_minutes or 60
                next_run = now + timedelta(minutes=interval)
            
            # 4. Update Schedule
            await schedule_store.update_schedule(schedule.id, {"next_run_at": next_run})
        
        # 5. Audit
        await audit_store.log_entry(AuditLogDoc(
            request_id=get_request_id(),
            actor="scheduler",
            action="run_schedule_tick",
            entity_type="scan",
            entity_id=scan.id,
            status="created",
            details_json={"schedule_id": schedule.id},
        ))
        
        logger.info("schedule_tick_triggered", schedule_id=schedule.id, scan_id=scan.id)
        triggered_count += 1
        
    if triggered_count > 0:
        logger.info("scheduler_tick_summary", triggered=triggered_count)
        
    return {"status": "ok", "triggered": triggered_count}
