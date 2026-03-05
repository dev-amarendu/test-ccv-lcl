"""Test Schedule Endpoints and CRON logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from api_service.main import app
from shared.firestore_models import ScheduleDoc, RepoDoc
from shared.repositories.schedule_store import ScheduleStore

# Mock Repo
MOCK_REPO = RepoDoc(id="repo-1", org_id="org-1", name="repo-1")

@pytest.fixture
def client():
    return TestClient(app)

@patch("shared.repositories.repos.RepoStore.get_repo")
@patch("shared.repositories.schedule_store.ScheduleStore.create_schedule")
@patch("shared.repositories.audit_store.AuditStore.log_entry")
def test_create_cron_schedule(mock_audit, mock_create, mock_get_repo, client):
    """Test creating a schedule with a valid CRON expression."""
    mock_get_repo.return_value = MOCK_REPO
    
    payload = {
        "repo_id": "repo-1",
        "branch": "main",
        "cron_expression": "0 0 * * MON"  # Weekly on Monday
    }
    
    response = client.post("/schedules", json=payload)
    
    assert response.status_code == 201
    assert mock_create.called
    created = mock_create.call_args[0][0]
    
    assert created.cron_expression == "0 0 * * MON"
    # Ensure next_run_at is calculated and in the future
    assert created.next_run_at > datetime.now(timezone.utc)

@patch("shared.repositories.repos.RepoStore.get_repo")
def test_create_invalid_cron(mock_get_repo, client):
    """Test creating a schedule with an INVALID CRON expression."""
    mock_get_repo.return_value = MOCK_REPO
    
    payload = {
        "repo_id": "repo-1",
        "branch": "main",
        "cron_expression": "invalid cron string"
    }
    
    response = client.post("/schedules", json=payload)
    
    assert response.status_code == 400
    assert "Invalid cron expression" in response.json()["detail"]

@patch("shared.repositories.schedule_store.ScheduleStore.list_due_schedules")
@patch("shared.repositories.schedule_store.ScheduleStore.update_schedule")
@patch("shared.repositories.scan_store.ScanStore.create_scan")
@patch("api_service.routes.schedules.publish_run_scan")
@patch("shared.repositories.audit_store.AuditStore.log_entry")
def test_tick_trigger_cron(
    mock_audit, mock_pub, mock_scan, mock_update, mock_list_due, client
):
    """Test that the tick endpoint triggers scans and recalculates next_run for CRON."""
    
    # Setup a due schedule with CRON
    now = datetime.now(timezone.utc)
    due_schedule = ScheduleDoc(
        id="sched-1",
        repo_id="repo-1",
        branch="main",
        cron_expression="*/5 * * * *",  # Every 5 mins
        next_run_at=now - timedelta(minutes=1), # Overdue
        enabled=True
    )
    mock_list_due.return_value = [due_schedule]
    
    response = client.post("/schedules/tick")
    
    assert response.status_code == 200
    assert response.json()["triggered"] == 1
    
    # Verify Scan Created
    assert mock_scan.called
    
    # Verify Trigger Published
    assert mock_pub.called
    
    # Verify Next Run Updated
    assert mock_update.called
    args = mock_update.call_args
    assert args[0][0] == "sched-1"
    updated_fields = args[0][1]
    assert "next_run_at" in updated_fields
    
    # Next run should be > now
    assert updated_fields["next_run_at"] > now
