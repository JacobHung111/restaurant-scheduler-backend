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
    "11:00-16:00": {"start": "11:00", "end": "16:00", "hours": 5.0},
    "16:00-21:00": {"start": "16:00", "end": "21:00", "hours": 5.0},
}
ALL_ROLES = ["Server", "Cashier", "Expo"]
SHIFT_TYPES = ["HALF_DAY_AM", "HALF_DAY_PM", "FULL_DAY"]
