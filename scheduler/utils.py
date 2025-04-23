# scheduler/utils.py
import traceback
from .constants import DAYS_OF_WEEK, SHIFTS

def time_to_minutes(time_str):
    # Converts "HH:MM" time string to minutes since midnight
    if not time_str or ':' not in time_str:
        # print(f"Warning: time_to_minutes received invalid input: {time_str}") # Optional: Keep for debugging
        return 0
    try:
        hours, minutes = map(int, time_str.split(':'))
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return hours * 60 + minutes
        else:
            print(f"Warning: time_to_minutes received out-of-range time: {time_str}")
            return 0
    except ValueError:
        print(f"Warning: time_to_minutes encountered ValueError for: {time_str}")
        return 0

def is_available(employee_id, day_of_week, shift, unavailability_list):
    """Checks if an employee is available during a specific shift."""
    if not isinstance(unavailability_list, list):
        # print("Warning: is_available received non-list for unavailability_list.")
        return True # Assume available if data is invalid
    if not isinstance(shift, dict) or 'start' not in shift or 'end' not in shift:
        # print(f"Warning: is_available received invalid shift object: {shift}")
        return False

    try:
        record = next((item for item in unavailability_list
                       if isinstance(item, dict) and
                       item.get('employeeId') == employee_id and
                       item.get('dayOfWeek') == day_of_week), None)
    except Exception as e:
        print(f"Error finding unavailability record for {employee_id} on {day_of_week}: {e}")
        traceback.print_exc()
        return True # Assume available on error

    if record is None:
        return True

    shift_start_min = time_to_minutes(shift['start'])
    shift_end_min = time_to_minutes(shift['end'])
    # Check for invalid shift range (e.g., end before start), ignore 00:00-00:00
    if shift_start_min >= shift_end_min and not (shift_start_min == 0 and shift_end_min == 0):
        # print(f"Warning: is_available found invalid shift time range: {shift['start']}-{shift['end']}")
        return False

    unavailable_shifts = record.get('shifts')
    if not isinstance(unavailable_shifts, list):
        # print(f"Warning: Invalid 'shifts' format for {employee_id} on {day_of_week}.")
        return True # Assume available if format wrong

    for unav_shift in unavailable_shifts:
        if not isinstance(unav_shift, dict) or 'start' not in unav_shift or 'end' not in unav_shift:
            # print(f"Warning: Invalid unavailable shift format found: {unav_shift}")
            continue

        unav_start_min = time_to_minutes(unav_shift['start'])
        unav_end_min = time_to_minutes(unav_shift['end'])
        # Handle all-day unavailability (end <= start) by setting end to end-of-day
        effective_unav_end_min = 24 * 60 if (unav_end_min <= unav_start_min and not (unav_start_min == 0 and unav_end_min == 0)) else unav_end_min
        # Ignore potential 00:00-00:00 entries
        if effective_unav_end_min == 0 and unav_start_min == 0:
            continue

        # Check for overlap: (start1 < end2) and (start2 < end1)
        overlap = (shift_start_min < effective_unav_end_min) and (unav_start_min < shift_end_min)
        # Check if unavailable period completely covers the shift
        covers = (unav_start_min <= shift_start_min) and (effective_unav_end_min >= shift_end_min)

        if overlap or covers:
            # print(f"Debug: Availability conflict for {employee_id} on {day_of_week}. Shift {shift['start']}-{shift['end']} vs unav {unav_shift['start']}-{unav_shift['end']}")
            return False # Unavailable due to conflict
    return True # Available if no conflicts found

def calculate_daily_hours(employee_id, day_of_week, schedule):
    """Calculates total scheduled hours for an employee on a specific day."""
    total_hours = 0.0
    # Use global SHIFTS imported via relative import
    if not isinstance(schedule, dict) or day_of_week not in schedule or not isinstance(schedule[day_of_week], dict):
        return 0.0
    for shift_key, roles_dict in schedule[day_of_week].items():
        shift_info = SHIFTS.get(shift_key) # Use imported SHIFTS
        if shift_info and isinstance(roles_dict, dict):
            for role, assigned_list in roles_dict.items():
                if isinstance(assigned_list, list) and employee_id in assigned_list:
                    total_hours += shift_info.get('hours', 0.0)
                    # Assume one role per shift block per person for daily hour calculation
    return total_hours

def calculate_total_weekly_hours(employee_id, schedule):
    """Calculates total scheduled hours for an employee for the week."""
    total_hours = 0.0
    # Use global DAYS_OF_WEEK imported via relative import
    if not isinstance(schedule, dict):
        return 0.0
    for day in DAYS_OF_WEEK: # Use imported DAYS_OF_WEEK
        total_hours += calculate_daily_hours(employee_id, day, schedule) # Calls function within this module
    return total_hours