"""Test Webhook Endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api_service.main import app
from shared.firestore_models import RepoDoc, TriggerType

# Sample Bitbucket Payload
SAMPLE_PAYLOAD = {
    "repository": {
        "full_name": "org/repo-1",
        "name": "repo-1"
    },
    "pullrequest": {
        "id": 123,
        "title": "Fix bug",
        "source": {
            "branch": {"name": "feature/bugfix"},
            "commit": {"hash": "abc1234"}
        },
        "destination": {
            "branch": {"name": "main"}
        },
        "state": "MERGED"
    },
    "actor": {"display_name": "Dev User"}
}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_settings():
    with patch("api_service.routes.webhooks.settings") as mock:
        mock.return_value.bitbucket_enabled = True
        yield mock


@patch("shared.repositories.repos.RepoStore.list_repos")
@patch("shared.repositories.scan_store.ScanStore.create_scan")
@patch("api_service.routes.webhooks.publish_run_scan")
def test_bitbucket_webhook_triggers_scan(
    mock_publish, mock_create_scan, mock_list_repos, client, mock_settings
):
    """Test that a valid PR merge webhook triggers a scan."""
    
    # Mock configured repos
    mock_repo = RepoDoc(
        id="repo-123",
        org_id="org-1",
        name="repo-1",  # Matches payload name
        default_branch="main",
        connected=True,
    )
    mock_list_repos.return_value = [mock_repo]

    # Call Webhook
    response = client.post("/webhooks/bitbucket/pullrequest", json=SAMPLE_PAYLOAD)
    
    # Assertions
    assert response.status_code == 202
    assert "Scan triggered" in response.json()["message"]
    
    # Verify Scan Creation
    assert mock_create_scan.called
    created_scan = mock_create_scan.call_args[0][0]
    assert created_scan.repo_id == "repo-123"
    assert created_scan.branch == "main"
    assert created_scan.commit_sha == "abc1234"
    assert created_scan.trigger_type == TriggerType.WEBHOOK
    
    # Verify Pub/Sub Publish
    assert mock_publish.called
    assert mock_publish.call_args[0][0] == created_scan.id


@patch("shared.repositories.repos.RepoStore.list_repos")
@patch("shared.repositories.scan_store.ScanStore.create_scan")
@patch("api_service.routes.webhooks.publish_run_scan")
def test_bitbucket_webhook_ignored_branch(
    mock_publish, mock_create_scan, mock_list_repos, client, mock_settings
):
    """Test that PR to non-main branch does NOT trigger scan."""
    
    mock_repo = RepoDoc(id="repo-123", org_id="org-1", name="repo-1", default_branch="main", connected=True)
    mock_list_repos.return_value = [mock_repo]

    payload = SAMPLE_PAYLOAD.copy()
    payload["pullrequest"] = SAMPLE_PAYLOAD["pullrequest"].copy()
    payload["pullrequest"]["destination"] = {"branch": {"name": "develop"}}

    response = client.post("/webhooks/bitbucket/pullrequest", json=payload)
    
    assert response.status_code == 202
    # Should NOT have "Scan triggered"
    assert "Scan triggered" not in response.json()["message"]
    
    assert not mock_create_scan.called
    assert not mock_publish.called


@patch("shared.repositories.repos.RepoStore.list_repos")
@patch("shared.repositories.scan_store.ScanStore.create_scan")
@patch("api_service.routes.webhooks.publish_run_scan")
def test_bitbucket_webhook_unknown_repo(
    mock_publish, mock_create_scan, mock_list_repos, client, mock_settings
):
    """Test that unknown repo name ignores the event."""
    
    mock_list_repos.return_value = []  # No repos

    response = client.post("/webhooks/bitbucket/pullrequest", json=SAMPLE_PAYLOAD)
    
    assert response.status_code == 202
    assert "Scan triggered" not in response.json()["message"]
    
    assert not mock_create_scan.called
