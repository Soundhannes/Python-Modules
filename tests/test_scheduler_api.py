"""Tests fuer Scheduler API-Endpoints - RED Phase (TDD)."""

import pytest
from httpx import ASGITransport, AsyncClient
from datetime import datetime

import sys
sys.path.insert(0, "/opt/python-modules")
sys.path.insert(0, "/app")


@pytest.mark.asyncio
class TestSchedulesEndpoint:
    """Tests fuer /api/scheduler/schedules Endpoints."""

    async def test_get_schedules_returns_list(self):
        """Sollte Liste aller Schedules zurueckgeben."""
        # Arrange
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            
            # Act
            response = await client.get("/api/scheduler/schedules")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            # Liste kann leer sein oder Schedules enthalten
            if len(data) > 0:
                schedule = data[0]
                assert "id" in schedule
                assert "name" in schedule
                assert "type" in schedule

    async def test_post_schedule_creates_interval_schedule(self):
        """Sollte neuen Interval-Schedule mit 30 Minuten erstellen."""
        # Arrange
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            new_schedule = {
                "name": "Test Interval Schedule",
                "type": "interval",
                "interval_minutes": 30
            }
            
            # Act
            response = await client.post("/api/scheduler/schedules", json=new_schedule)
            
            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Test Interval Schedule"
            assert data["type"] == "interval"
            assert data["interval_minutes"] == 30
            assert "id" in data

    async def test_put_schedule_updates_interval_minutes(self):
        """Sollte interval_minutes eines existierenden Schedules aktualisieren."""
        # Arrange
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Erstelle zuerst einen Schedule
            new_schedule = {
                "name": "Update Test Schedule",
                "type": "interval",
                "interval_minutes": 15
            }
            create_response = await client.post("/api/scheduler/schedules", json=new_schedule)
            schedule_id = create_response.json()["id"]
            
            # Act
            update_data = {"interval_minutes": 45}
            response = await client.put(f"/api/scheduler/schedules/{schedule_id}", json=update_data)
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["interval_minutes"] == 45
            assert data["id"] == schedule_id

    async def test_delete_schedule_removes_schedule(self):
        """Sollte Schedule loeschen wenn ID existiert."""
        # Arrange
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Erstelle Schedule zum Loeschen
            new_schedule = {
                "name": "Delete Test Schedule",
                "type": "interval",
                "interval_minutes": 20
            }
            create_response = await client.post("/api/scheduler/schedules", json=new_schedule)
            schedule_id = create_response.json()["id"]
            
            # Act
            response = await client.delete(f"/api/scheduler/schedules/{schedule_id}")
            
            # Assert
            assert response.status_code == 204
            
            # Verify: Schedule sollte nicht mehr existieren
            get_response = await client.get(f"/api/scheduler/schedules/{schedule_id}")
            assert get_response.status_code == 404


@pytest.mark.asyncio
class TestJobsEndpoint:
    """Tests fuer /api/scheduler/jobs Endpoints."""

    async def test_get_jobs_returns_list_with_schedule_name(self):
        """Sollte Liste aller Jobs mit schedule_name zurueckgeben."""
        # Arrange
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            
            # Act
            response = await client.get("/api/scheduler/jobs")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            # Liste kann leer sein oder Jobs enthalten
            if len(data) > 0:
                job = data[0]
                assert "id" in job
                assert "name" in job
                assert "schedule_id" in job
                assert "schedule_name" in job
                assert "enabled" in job

    async def test_put_job_updates_schedule_id(self):
        """Sollte schedule_id eines Jobs aendern."""
        # Arrange
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Erstelle zwei Schedules
            schedule1 = await client.post("/api/scheduler/schedules", json={
                "name": "Schedule 1",
                "type": "interval",
                "interval_minutes": 10
            })
            schedule1_id = schedule1.json()["id"]
            
            schedule2 = await client.post("/api/scheduler/schedules", json={
                "name": "Schedule 2",
                "type": "interval",
                "interval_minutes": 20
            })
            schedule2_id = schedule2.json()["id"]
            
            # Hole ersten Job
            jobs_response = await client.get("/api/scheduler/jobs")
            jobs = jobs_response.json()
            assert len(jobs) > 0
            job_id = jobs[0]["id"]
            
            # Act
            update_data = {"schedule_id": schedule2_id}
            response = await client.put(f"/api/scheduler/jobs/{job_id}", json=update_data)
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["schedule_id"] == schedule2_id
            assert data["id"] == job_id

    async def test_put_job_toggles_enabled_status(self):
        """Sollte enabled-Status eines Jobs umschalten."""
        # Arrange
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Hole ersten Job
            jobs_response = await client.get("/api/scheduler/jobs")
            jobs = jobs_response.json()
            assert len(jobs) > 0
            job = jobs[0]
            job_id = job["id"]
            current_enabled = job["enabled"]
            
            # Act
            update_data = {"enabled": not current_enabled}
            response = await client.put(f"/api/scheduler/jobs/{job_id}", json=update_data)
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] == (not current_enabled)

    async def test_post_job_run_executes_job_manually(self):
        """Sollte Job manuell ausfuehren und Execution erstellen."""
        # Arrange
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Hole ersten Job
            jobs_response = await client.get("/api/scheduler/jobs")
            jobs = jobs_response.json()
            assert len(jobs) > 0
            job_id = jobs[0]["id"]
            
            # Act
            response = await client.post(f"/api/scheduler/jobs/{job_id}/run")
            
            # Assert
            assert response.status_code == 202
            data = response.json()
            assert "execution_id" in data
            assert "status" in data
            assert data["status"] in ["running", "queued"]
