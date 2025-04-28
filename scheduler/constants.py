# scheduler/constants.py
DAYS_OF_WEEK = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

SHIFTS = {
    "HALF_DAY_AM": {"start": "11:00", "end": "16:00", "hours": 5.0},
    "HALF_DAY_PM": {"start": "16:00", "end": "21:00", "hours": 5.0},
}

SHIFT_TYPES = ["HALF_DAY_AM", "HALF_DAY_PM"]

ALL_ROLES = ["Cashier", "Server", "Expo"]
