# scheduler/utils.py
import logging
from .constants import SHIFT_TYPES, DAYS_OF_WEEK, SHIFTS as DEFAULT_SHIFTS

logger = logging.getLogger(__name__)


def time_to_minutes(time_str):
    """Convert time string (HH:MM) to minutes since midnight."""
    if not time_str or ":" not in time_str:
        logger.warning(f"Invalid time format: {time_str}")
        return -1
    try:
        hours, minutes = map(int, time_str.split(":"))
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return hours * 60 + minutes
        else:
            logger.warning(f"Time out of range: {time_str}")
            return -1
    except ValueError as e:
        logger.warning(f"Time parsing error for '{time_str}': {e}")
        return -1


def calculate_daily_hours(employee_id, day_of_week, schedule, shift_definitions):
    """Calculate total hours worked by an employee on a specific day.
    
    Args:
        employee_id (str): Employee ID
        day_of_week (str): Day name (e.g., 'Monday')
        schedule (dict): Complete schedule dictionary
        shift_definitions (dict): Shift definitions with hours
        
    Returns:
        float: Total hours worked on the specified day
    """
    total_hours = 0.0
    current_shifts = (
        shift_definitions if isinstance(shift_definitions, dict) else DEFAULT_SHIFTS
    )

    if (
        not isinstance(schedule, dict)
        or day_of_week not in schedule
        or not isinstance(schedule[day_of_week], dict)
    ):
        return 0.0

    for shift_type, roles_dict in schedule[day_of_week].items():
        shift_info = current_shifts.get(shift_type)
        if (
            shift_info
            and isinstance(roles_dict, dict)
            and isinstance(shift_info.get("hours"), (int, float))
        ):
            for role, assigned_list in roles_dict.items():
                if isinstance(assigned_list, list) and employee_id in assigned_list:
                    total_hours += shift_info["hours"]
    return total_hours


def validate_shift_definitions(shift_defs):
    """Validate shift definitions structure and time consistency.
    
    Args:
        shift_defs (dict): Shift definitions with start/end times and hours
        
    Returns:
        tuple: (bool, str|None) - (is_valid, error_message)
    """
    if not isinstance(shift_defs, dict):
        return False, "shiftDefinitions must be an object."
    if not all(key in shift_defs for key in SHIFT_TYPES):
        return (
            False,
            "Missing required shift types (HALF_DAY_AM, HALF_DAY_PM).",
        )
    try:
        am_start = shift_defs["HALF_DAY_AM"]["start"]
        am_end = shift_defs["HALF_DAY_AM"]["end"]
        pm_start = shift_defs["HALF_DAY_PM"]["start"]
        pm_end = shift_defs["HALF_DAY_PM"]["end"]
        times_to_check = [am_start, am_end, pm_start, pm_end]
        if not all(
            isinstance(t, str) and len(t) == 5 and t[2] == ":" for t in times_to_check
        ):
            return False, "Invalid time format (must be HH:MM)."
        # Check times are valid minutes
        if (
            time_to_minutes(am_start) < 0
            or time_to_minutes(am_end) < 0
            or time_to_minutes(pm_start) < 0
            or time_to_minutes(pm_end) < 0
        ):
            return False, "Invalid time value in shift definitions."
        # Check start < end
        if time_to_minutes(am_start) >= time_to_minutes(am_end):
            return False, "AM start must be before AM end."
        if time_to_minutes(pm_start) >= time_to_minutes(pm_end):
            return False, "PM start must be before PM end."
        # Check consistency
        if am_end != pm_start:
            return False, "AM shift end must equal PM shift start."
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Error during shift definition validation: {e}")
        return False, "Invalid structure or value within shiftDefinitions object."
    return True, None  # Validation passed


def calculate_total_weekly_hours(employee_id, schedule, current_shifts_definitions):
    """Calculate total weekly hours for an employee across all days.
    
    Args:
        employee_id (str): Employee ID
        schedule (dict): Complete schedule dictionary
        current_shifts_definitions (dict): Shift definitions with hours
        
    Returns:
        float: Total weekly hours worked
    """
    total_hours = 0.0
    if not isinstance(schedule, dict):
        return 0.0
    for day in DAYS_OF_WEEK:
        total_hours += calculate_daily_hours(
            employee_id, day, schedule, current_shifts_definitions
        )
    return total_hours
