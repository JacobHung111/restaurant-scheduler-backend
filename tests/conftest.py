"""
Shared test configuration and fixtures for restaurant scheduling backend.
"""
import pytest
import json
from flask import Flask
from application import create_app


@pytest.fixture
def app():
    """Create Flask application for testing."""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture  
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def sample_staff():
    """Sample staff data for testing."""
    return [
        {
            "name": "Alice",
            "assignedRolesInPriority": ["Server", "Cashier"],
            "minHoursPerWeek": 20,
            "maxHoursPerWeek": 40,
            "id": "staff-001"
        },
        {
            "name": "Bob", 
            "assignedRolesInPriority": ["Expo"],
            "minHoursPerWeek": 15,
            "maxHoursPerWeek": 35,
            "id": "staff-002"
        },
        {
            "name": "Charlie",
            "assignedRolesInPriority": ["Cashier", "Server"],
            "minHoursPerWeek": 25,
            "maxHoursPerWeek": 45,
            "id": "staff-003"
        }
    ]


@pytest.fixture
def sample_shift_definitions():
    """Sample shift definitions for testing."""
    return {
        "HALF_DAY_AM": {"start": "12:00", "end": "19:00", "hours": 7},
        "HALF_DAY_PM": {"start": "19:00", "end": "02:00", "hours": 7},
        "FULL_DAY": {"start": "12:00", "end": "02:00", "hours": 14}
    }


@pytest.fixture
def sample_weekly_needs():
    """Sample weekly needs for testing."""
    return {
        "Monday": {
            "HALF_DAY_AM": {"Server": 1, "Cashier": 1, "Expo": 1},
            "HALF_DAY_PM": {"Server": 1, "Cashier": 1, "Expo": 1}
        },
        "Tuesday": {
            "HALF_DAY_AM": {"Server": 1, "Cashier": 1, "Expo": 1},
            "HALF_DAY_PM": {"Server": 1, "Cashier": 1, "Expo": 1}
        }
    }


@pytest.fixture
def basic_schedule_request(sample_staff, sample_shift_definitions, sample_weekly_needs):
    """Basic valid schedule request for testing."""
    return {
        "staffList": sample_staff,
        "unavailabilityList": [],
        "weeklyNeeds": sample_weekly_needs,
        "shiftDefinitions": sample_shift_definitions,
        "shiftPreference": "NONE",
        "staffPriority": []
    }


@pytest.fixture
def cross_day_unavailability():
    """Cross-day unavailability test data."""
    return [
        {
            "employeeId": "staff-001",
            "dayOfWeek": "Monday", 
            "shifts": [{"start": "19:00", "end": "02:00"}]
        }
    ]


@pytest.fixture  
def same_day_unavailability():
    """Same-day unavailability test data."""
    return [
        {
            "employeeId": "staff-002",
            "dayOfWeek": "Tuesday",
            "shifts": [{"start": "12:00", "end": "19:00"}]
        }
    ]