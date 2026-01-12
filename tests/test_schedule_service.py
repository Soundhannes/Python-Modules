"""Tests fuer ScheduleService - berechnet naechsten Ausfuehrungszeitpunkt."""

import pytest
from datetime import datetime, timedelta

import sys
sys.path.insert(0, "/opt/python-modules")

from schedule.service import calculate_next_run


class TestIntervalSchedule:
    """Tests fuer Interval-basierte Schedules."""

    def test_interval_schedule_15_minutes(self):
        """Sollte naechsten Run in 15 Minuten berechnen."""
        # Arrange
        schedule = {
            'type': 'interval',
            'interval_minutes': 15
        }
        reference_time = datetime(2026, 1, 12, 10, 0, 0)

        # Act
        next_run = calculate_next_run(schedule, reference_time)

        # Assert
        expected = datetime(2026, 1, 12, 10, 15, 0)
        assert next_run == expected


class TestDailySchedule:
    """Tests fuer tägliche Schedules."""

    def test_daily_schedule_time_not_reached_today(self):
        """Sollte heute 07:00 zurückgeben wenn jetzt 06:00 ist."""
        # Arrange
        schedule = {
            'type': 'daily',
            'time_of_day': '07:00'
        }
        reference_time = datetime(2026, 1, 12, 6, 0, 0)

        # Act
        next_run = calculate_next_run(schedule, reference_time)

        # Assert
        expected = datetime(2026, 1, 12, 7, 0, 0)
        assert next_run == expected

    def test_daily_schedule_time_already_passed_today(self):
        """Sollte morgen 07:00 zurückgeben wenn jetzt 08:00 ist."""
        # Arrange
        schedule = {
            'type': 'daily',
            'time_of_day': '07:00'
        }
        reference_time = datetime(2026, 1, 12, 8, 0, 0)

        # Act
        next_run = calculate_next_run(schedule, reference_time)

        # Assert
        expected = datetime(2026, 1, 13, 7, 0, 0)
        assert next_run == expected


class TestWeeklySchedule:
    """Tests fuer wöchentliche Schedules."""

    def test_weekly_schedule_monday_when_tuesday(self):
        """Sollte nächsten Montag 08:00 zurückgeben wenn jetzt Dienstag ist."""
        # Arrange
        schedule = {
            'type': 'weekly',
            'day_of_week': 0,  # 0 = Montag
            'time_of_day': '08:00'
        }
        reference_time = datetime(2026, 1, 13, 10, 0, 0)  # Dienstag 13.1.2026

        # Act
        next_run = calculate_next_run(schedule, reference_time)

        # Assert
        expected = datetime(2026, 1, 19, 8, 0, 0)  # Nächster Montag
        assert next_run == expected


class TestMonthlySchedule:
    """Tests fuer monatliche Schedules."""

    def test_monthly_schedule_first_day_when_mid_month(self):
        """Sollte nächsten 1. um 09:00 zurückgeben wenn jetzt 15. ist."""
        # Arrange
        schedule = {
            'type': 'monthly',
            'day_of_month': 1,
            'time_of_day': '09:00'
        }
        reference_time = datetime(2026, 1, 15, 12, 0, 0)

        # Act
        next_run = calculate_next_run(schedule, reference_time)

        # Assert
        expected = datetime(2026, 2, 1, 9, 0, 0)
        assert next_run == expected
