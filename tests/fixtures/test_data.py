"""
Simplified test data fixtures for restaurant scheduling system.
Focused on comprehensive logic coverage with minimal data complexity.
"""

# Standard shift definitions used across all tests
STANDARD_SHIFT_DEFINITIONS = {
    "HALF_DAY_AM": {"start": "12:00", "end": "19:00", "hours": 7},
    "HALF_DAY_PM": {"start": "19:00", "end": "02:00", "hours": 7}
}

# Minimal staff set covering all roles and constraint types
MINIMAL_STAFF = [
    {
        "name": "Manager Alice",
        "assignedRolesInPriority": ["Server", "Cashier", "Expo"],  # Multi-role
        "minHoursPerWeek": 30,
        "maxHoursPerWeek": 40,
        "id": "alice-mgr-001"
    },
    {
        "name": "Server Bob", 
        "assignedRolesInPriority": ["Server"],  # Single role
        "minHoursPerWeek": 20,
        "maxHoursPerWeek": 35,
        "id": "bob-srv-002"
    },
    {
        "name": "Cashier Carol",
        "assignedRolesInPriority": ["Cashier", "Server"],  # Role preference test
        "minHoursPerWeek": 15,
        "maxHoursPerWeek": 30,
        "id": "carol-csh-003"
    },
    {
        "name": "Expo Dave",
        "assignedRolesInPriority": ["Expo", "Server"],  # Critical role
        "minHoursPerWeek": 25,
        "maxHoursPerWeek": 40,
        "id": "dave-exp-004"
    },
    {
        "name": "Part-time Eve",
        "assignedRolesInPriority": ["Server", "Cashier"],  # Low hours constraint
        "minHoursPerWeek": 5,
        "maxHoursPerWeek": 15,
        "id": "eve-pt-005"
    }
]

# Basic weekly needs covering all roles
BASIC_WEEKLY_NEEDS = {
    "Monday": {
        "HALF_DAY_AM": {"Server": 1, "Cashier": 1, "Expo": 1},
        "HALF_DAY_PM": {"Server": 2, "Cashier": 1, "Expo": 1}
    },
    "Tuesday": {
        "HALF_DAY_AM": {"Server": 1, "Cashier": 1, "Expo": 1},
        "HALF_DAY_PM": {"Server": 2, "Cashier": 1, "Expo": 1}
    },
    "Wednesday": {
        "HALF_DAY_AM": {"Server": 1, "Cashier": 1, "Expo": 1},
        "HALF_DAY_PM": {"Server": 1, "Cashier": 1, "Expo": 1}
    },
    "Thursday": {
        "HALF_DAY_AM": {"Server": 1, "Cashier": 1, "Expo": 1},
        "HALF_DAY_PM": {"Server": 2, "Cashier": 1, "Expo": 1}
    },
    "Friday": {
        "HALF_DAY_AM": {"Server": 1, "Cashier": 1, "Expo": 1},
        "HALF_DAY_PM": {"Server": 2, "Cashier": 1, "Expo": 1}
    },
    "Saturday": {
        "HALF_DAY_AM": {"Server": 2, "Cashier": 1, "Expo": 1},
        "HALF_DAY_PM": {"Server": 2, "Cashier": 1, "Expo": 1}
    },
    "Sunday": {
        "HALF_DAY_AM": {"Server": 1, "Cashier": 1, "Expo": 1},
        "HALF_DAY_PM": {"Server": 1, "Cashier": 1, "Expo": 1}
    }
}

# Unavailability scenarios for constraint testing
BASIC_UNAVAILABILITY = [
    {
        "employeeId": "eve-pt-005",
        "dayOfWeek": "Monday", 
        "shifts": [{"start": "12:00", "end": "19:00"}]  # AM shift unavailable
    },
    {
        "employeeId": "bob-srv-002",
        "dayOfWeek": "Sunday",
        "shifts": [{"start": "00:00", "end": "23:59"}]  # Entire day unavailable
    }
]

# Staff priority for optimization testing
BASIC_STAFF_PRIORITY = [
    "alice-mgr-001",  # Highest priority - manager
    "dave-exp-004",   # Critical role
    "bob-srv-002",    # Regular staff
    "carol-csh-003",  # Regular staff
    "eve-pt-005"      # Lowest priority - part-time
]

def get_basic_scenario():
    """Get the basic test scenario covering all core logic."""
    return {
        "staffList": MINIMAL_STAFF,
        "unavailabilityList": BASIC_UNAVAILABILITY,
        "weeklyNeeds": BASIC_WEEKLY_NEEDS,
        "shiftDefinitions": STANDARD_SHIFT_DEFINITIONS,
        "shiftPreference": "PRIORITIZE_FULL_DAYS",
        "staffPriority": BASIC_STAFF_PRIORITY
    }

def get_understaffed_scenario():
    """Get scenario with insufficient staff for testing shortage handling."""
    return {
        "staffList": MINIMAL_STAFF[:2],  # Only 2 staff for all needs
        "unavailabilityList": [],
        "weeklyNeeds": BASIC_WEEKLY_NEEDS,
        "shiftDefinitions": STANDARD_SHIFT_DEFINITIONS,
        "shiftPreference": "NONE",
        "staffPriority": BASIC_STAFF_PRIORITY[:2]
    }

def get_overstaffed_scenario():
    """Get scenario with excess staff for testing priority optimization."""
    extra_staff = [
        {
            "name": f"Extra Staff {i}",
            "assignedRolesInPriority": ["Server"],
            "minHoursPerWeek": 10,
            "maxHoursPerWeek": 20,
            "id": f"extra-{i:03d}"
        }
        for i in range(1, 4)  # Add 3 extra staff
    ]
    
    return {
        "staffList": MINIMAL_STAFF + extra_staff,
        "unavailabilityList": [],
        "weeklyNeeds": {
            "Monday": {"HALF_DAY_AM": {"Server": 1}},  # Minimal needs
            "Tuesday": {"HALF_DAY_AM": {"Server": 1}}
        },
        "shiftDefinitions": STANDARD_SHIFT_DEFINITIONS,
        "shiftPreference": "NONE", 
        "staffPriority": BASIC_STAFF_PRIORITY + [f"extra-{i:03d}" for i in range(1, 4)]
    }

def get_high_constraint_scenario():
    """Get scenario with many overlapping constraints."""
    complex_unavailability = [
        {
            "employeeId": "alice-mgr-001",
            "dayOfWeek": "Monday",
            "shifts": [{"start": "19:00", "end": "02:00"}]  # PM unavailable
        },
        {
            "employeeId": "bob-srv-002", 
            "dayOfWeek": "Monday",
            "shifts": [{"start": "12:00", "end": "19:00"}]  # AM unavailable
        },
        {
            "employeeId": "carol-csh-003",
            "dayOfWeek": "Tuesday", 
            "shifts": [{"start": "15:00", "end": "22:00"}]  # Partial overlap
        }
    ]
    
    return {
        "staffList": MINIMAL_STAFF,
        "unavailabilityList": complex_unavailability,
        "weeklyNeeds": BASIC_WEEKLY_NEEDS,
        "shiftDefinitions": STANDARD_SHIFT_DEFINITIONS,
        "shiftPreference": "PRIORITIZE_FULL_DAYS",
        "staffPriority": BASIC_STAFF_PRIORITY
    }

# Invalid data for error testing
INVALID_STAFF_EXAMPLES = [
    {"name": "No ID", "assignedRolesInPriority": ["Server"]},  # Missing ID
    {"id": "no-name", "assignedRolesInPriority": ["Server"]},  # Missing name
    {"name": "No Roles", "id": "no-roles"},  # Missing roles
    {"name": "Bad Hours", "id": "bad-hours", "assignedRolesInPriority": ["Server"], 
     "minHoursPerWeek": 50, "maxHoursPerWeek": 20}  # Invalid hours
]

INVALID_UNAVAILABILITY_EXAMPLES = [
    {"dayOfWeek": "Monday", "shifts": [{"start": "12:00", "end": "19:00"}]},  # Missing employeeId
    {"employeeId": "test", "shifts": [{"start": "12:00", "end": "19:00"}]},  # Missing dayOfWeek
    {"employeeId": "test", "dayOfWeek": "BadDay", "shifts": [{"start": "12:00", "end": "19:00"}]}  # Invalid day
]

INVALID_WEEKLY_NEEDS_EXAMPLES = [
    {"BadDay": {"HALF_DAY_AM": {"Server": 1}}},  # Invalid day
    {"Monday": {"BAD_SHIFT": {"Server": 1}}},  # Invalid shift
    {"Monday": {"HALF_DAY_AM": {"BadRole": 1}}},  # Invalid role
    {"Monday": {"HALF_DAY_AM": {"Server": -1}}}  # Invalid count
]