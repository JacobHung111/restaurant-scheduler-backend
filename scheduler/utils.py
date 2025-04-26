# scheduler/utils.py
import traceback
from .constants import DAYS_OF_WEEK, SHIFTS


def time_to_minutes(time_str):
    if not time_str or ":" not in time_str:
        return 0
    try:
        hours, minutes = map(int, time_str.split(":"))
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return hours * 60 + minutes
        else:
            print(f"Warning: time_to_minutes received out-of-range time: {time_str}")
            return 0
    except ValueError:
        print(f"Warning: time_to_minutes encountered ValueError for: {time_str}")
        return 0


def is_available(employee_id, day_of_week, shift, unavailability_list):
    if not isinstance(unavailability_list, list):
        return True
    if not isinstance(shift, dict) or "start" not in shift or "end" not in shift:
        return False

    try:
        record = next(
            (
                item
                for item in unavailability_list
                if isinstance(item, dict)
                and item.get("employeeId") == employee_id
                and item.get("dayOfWeek") == day_of_week
            ),
            None,
        )
    except Exception as e:
        print(
            f"Error finding unavailability record for {employee_id} on {day_of_week}: {e}"
        )
        traceback.print_exc()
        return True

    if record is None:
        return True

    shift_start_min = time_to_minutes(shift["start"])
    shift_end_min = time_to_minutes(shift["end"])
    if shift_start_min >= shift_end_min and not (
        shift_start_min == 0 and shift_end_min == 0
    ):
        return False

    unavailable_shifts = record.get("shifts")
    if not isinstance(unavailable_shifts, list):
        return True

    for unav_shift in unavailable_shifts:
        if (
            not isinstance(unav_shift, dict)
            or "start" not in unav_shift
            or "end" not in unav_shift
        ):
            continue

        unav_start_min = time_to_minutes(unav_shift["start"])
        unav_end_min = time_to_minutes(unav_shift["end"])
        effective_unav_end_min = (
            24 * 60
            if (
                unav_end_min <= unav_start_min
                and not (unav_start_min == 0 and unav_end_min == 0)
            )
            else unav_end_min
        )
        if effective_unav_end_min == 0 and unav_start_min == 0:
            continue
        overlap = (shift_start_min < effective_unav_end_min) and (
            unav_start_min < shift_end_min
        )
        covers = (unav_start_min <= shift_start_min) and (
            effective_unav_end_min >= shift_end_min
        )

        if overlap or covers:
            return False
    return True


def calculate_daily_hours(employee_id, day_of_week, schedule):
    total_hours = 0.0
    if (
        not isinstance(schedule, dict)
        or day_of_week not in schedule
        or not isinstance(schedule[day_of_week], dict)
    ):
        return 0.0
    for shift_key, roles_dict in schedule[day_of_week].items():
        shift_info = SHIFTS.get(shift_key)
        if shift_info and isinstance(roles_dict, dict):
            for role, assigned_list in roles_dict.items():
                if isinstance(assigned_list, list) and employee_id in assigned_list:
                    total_hours += shift_info.get("hours", 0.0)
    return total_hours


def calculate_total_weekly_hours(employee_id, schedule):
    total_hours = 0.0
    if not isinstance(schedule, dict):
        return 0.0
    for day in DAYS_OF_WEEK:
        total_hours += calculate_daily_hours(employee_id, day, schedule)
    return total_hours
