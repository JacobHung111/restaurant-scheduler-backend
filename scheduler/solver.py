# scheduler/solver.py
import time
from ortools.sat.python import cp_model
from .constants import DAYS_OF_WEEK, ALL_ROLES, SHIFT_TYPES
from .utils import time_to_minutes, calculate_total_weekly_hours


# --------------------------------------
# === OR-Tools Scheduling Core Logic ===
# --------------------------------------
def generate_schedule_with_ortools(
    weekly_needs,
    staff_list,
    unavailability_list,
    shift_definitions,
    shift_preference="PRIORITIZE_FULL_DAYS",
    staff_priority_list=[],
):
    print(
        f"[OR-Tools] Starting generation (Custom Times, Pref: {shift_preference}, Staff Prio: {len(staff_priority_list)})..."
    )
    start_time = time.perf_counter()

    if not isinstance(staff_list, list) or not staff_list:
        return None, ["Error: Staff list is empty or invalid."], 0
    if not isinstance(weekly_needs, dict):
        return None, ["Error: Weekly needs data is invalid."], 0
    if not isinstance(unavailability_list, list):
        unavailability_list = []
    if (
        not isinstance(shift_definitions, dict)
        or not all(st in shift_definitions for st in SHIFT_TYPES)
        or not all(
            isinstance(shift_definitions[st], dict)
            and "start" in shift_definitions[st]
            and "end" in shift_definitions[st]
            for st in SHIFT_TYPES
        )
    ):
        return None, ["Error: Invalid shiftDefinitions structure received."], 0
    try:
        am_end = shift_definitions["HALF_DAY_AM"]["end"]
        pm_start = shift_definitions["HALF_DAY_PM"]["start"]
        full_start = shift_definitions["FULL_DAY"]["start"]
        full_end = shift_definitions["FULL_DAY"]["end"]
        am_start = shift_definitions["HALF_DAY_AM"]["start"]
        pm_end = shift_definitions["HALF_DAY_PM"]["end"]
        if am_end != pm_start:
            return (
                None,
                [
                    f"Error: AM shift end time ({am_end}) must equal PM shift start time ({pm_start})."
                ],
                0,
            )
        if full_start != am_start or full_end != pm_end:
            return (
                None,
                [
                    f"Error: Full day time ({full_start}-{full_end}) must match AM start ({am_start}) and PM end ({pm_end})."
                ],
                0,
            )
    except KeyError:
        return None, ["Error: Incomplete shiftDefinitions data."], 0

    staff_map = {s["id"]: s for s in staff_list if isinstance(s, dict) and "id" in s}
    all_staff_ids = list(staff_map.keys())
    if not all_staff_ids:
        return None, ["Error: Could not extract valid staff IDs from staffList."], 0
    max_possible_shortage = len(all_staff_ids) + 1

    model = cp_model.CpModel()

    assign_vars = {}  # (s_id, d_idx, shift_type, role) -> BoolVar
    shortage_vars = {}  # (d_idx, shift_type, role) -> IntVar >= 0
    min_hour_shortage_tenths = {}  # (s_id) -> IntVar >= 0
    total_weekly_hours_tenths = {}  # (s_id) -> IntVar >= 0

    for s_id in all_staff_ids:
        staff_data = staff_map[s_id]
        possible_roles = staff_data.get("roles", [])
        for d_idx, day in enumerate(DAYS_OF_WEEK):
            for st in SHIFT_TYPES:
                for role in ALL_ROLES:
                    if role in possible_roles:
                        assign_vars[(s_id, d_idx, st, role)] = model.NewBoolVar(
                            f"assign_{s_id}_{day}_{st}_{role}"
                        )

    for d_idx, day in enumerate(DAYS_OF_WEEK):
        for st in SHIFT_TYPES:
            for role in ALL_ROLES:
                shortage_vars[(d_idx, st, role)] = model.NewIntVar(
                    0, max_possible_shortage, f"shortage_{day}_{st}_{role}"
                )

    for s_id, staff_data in staff_map.items():
        weekly_hours_terms = []
        for d_idx, day in enumerate(DAYS_OF_WEEK):
            for st, shift_info in shift_definitions.items():
                shift_duration_tenths = int(shift_info.get("hours", 0) * 10)
                if shift_duration_tenths > 0:
                    vars_for_shift_this_employee = [
                        var
                        for k, var in assign_vars.items()
                        if k[0] == s_id and k[1] == d_idx and k[2] == st
                    ]
                    if vars_for_shift_this_employee:
                        works_this_shift = model.NewBoolVar(f"works_{s_id}_{day}_{st}")
                        model.Add(sum(vars_for_shift_this_employee) >= 1).OnlyEnforceIf(
                            works_this_shift
                        )
                        model.Add(sum(vars_for_shift_this_employee) == 0).OnlyEnforceIf(
                            works_this_shift.Not()
                        )
                        weekly_hours_terms.append(
                            works_this_shift * shift_duration_tenths
                        )
        if weekly_hours_terms:
            total_weekly_hours_tenths[s_id] = model.NewIntVar(
                0, 7 * 24 * 10, f"total_hours_{s_id}"
            )
            model.Add(total_weekly_hours_tenths[s_id] == sum(weekly_hours_terms))
        else:
            total_weekly_hours_tenths[s_id] = model.NewConstant(0)
        min_hours = staff_data.get("minHoursPerWeek")
        min_hours_tenths_target = int(min_hours * 10) if min_hours else 0
        if min_hours_tenths_target > 0:
            shortage_var = model.NewIntVar(
                0, min_hours_tenths_target + 10, f"min_short_{s_id}"
            )
            model.Add(
                shortage_var
                >= min_hours_tenths_target - total_weekly_hours_tenths[s_id]
            )
            min_hour_shortage_tenths[s_id] = shortage_var
        else:
            min_hour_shortage_tenths[s_id] = model.NewConstant(0)

    print("[OR-Tools] Adding HARD constraint: Demand equation...")
    for d_idx, day in enumerate(DAYS_OF_WEEK):
        for st in SHIFT_TYPES:
            for role in ALL_ROLES:
                needed_count = weekly_needs.get(day, {}).get(st, {}).get(role, 0)
                needed_count = max(0, int(needed_count))
                qualified_assign_vars = [
                    var
                    for k, var in assign_vars.items()
                    if k[1] == d_idx and k[2] == st and k[3] == role
                ]
                shortage_var = shortage_vars.get((d_idx, st, role))
                if shortage_var is not None:
                    model.Add(sum(qualified_assign_vars) + shortage_var == needed_count)

    print("[OR-Tools] Adding HARD constraint: Single role per logical shift...")
    for s_id in all_staff_ids:
        for d_idx, day in enumerate(DAYS_OF_WEEK):
            for st in SHIFT_TYPES:
                vars_for_staff_shift = [
                    var
                    for k, var in assign_vars.items()
                    if k[0] == s_id and k[1] == d_idx and k[2] == st
                ]
                if len(vars_for_staff_shift) > 0:
                    model.Add(sum(vars_for_staff_shift) <= 1)

    print("[OR-Tools] Adding HARD constraint: Full/Half day exclusion...")
    for s_id in all_staff_ids:
        for d_idx, day in enumerate(DAYS_OF_WEEK):
            for role in ALL_ROLES:  # Must hold for any role
                var_full = assign_vars.get((s_id, d_idx, "FULL_DAY", role))
                var_am = assign_vars.get((s_id, d_idx, "HALF_DAY_AM", role))
                var_pm = assign_vars.get((s_id, d_idx, "HALF_DAY_PM", role))

                # Cannot work FULL and AM on the same day for the same role
                if var_full is not None and var_am is not None:
                    model.Add(var_full + var_am <= 1)
                # Cannot work FULL and PM on the same day for the same role
                if var_full is not None and var_pm is not None:
                    model.Add(var_full + var_pm <= 1)

    print("[OR-Tools] Adding HARD constraint: Unavailability...")
    for unav in unavailability_list:
        s_id = unav.get("employeeId")
        day = unav.get("dayOfWeek")
        shifts_unav = unav.get("shifts")
        if (
            not s_id
            or s_id not in staff_map
            or day not in DAYS_OF_WEEK
            or not isinstance(shifts_unav, list)
        ):
            continue
        d_idx = DAYS_OF_WEEK.index(day)
        for unav_span in shifts_unav:
            if (
                not isinstance(unav_span, dict)
                or "start" not in unav_span
                or "end" not in unav_span
            ):
                continue
            unav_start_min = time_to_minutes(unav_span["start"])
            unav_end_min = time_to_minutes(unav_span["end"])
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

            for st, shift_info in shift_definitions.items():
                shift_start_min = time_to_minutes(shift_info["start"])
                shift_end_min = time_to_minutes(shift_info["end"])
                if shift_start_min < 0 or shift_end_min < 0:
                    continue

                overlap = (shift_start_min < effective_unav_end_min) and (
                    unav_start_min < shift_end_min
                )
                covers = (unav_start_min <= shift_start_min) and (
                    effective_unav_end_min >= shift_end_min
                )

                if overlap or covers:
                    for role in ALL_ROLES:
                        var = assign_vars.get((s_id, d_idx, st, role))
                        if var is not None:
                            model.Add(var == 0)

    print("[OR-Tools] Adding HARD constraint: Max weekly hours...")
    for s_id, staff_data in staff_map.items():
        max_hours = staff_data.get("maxHoursPerWeek")
        if (
            max_hours is not None
            and isinstance(max_hours, (int, float))
            and max_hours >= 0
        ):
            if s_id in total_weekly_hours_tenths:
                model.Add(total_weekly_hours_tenths[s_id] <= int(max_hours * 10))

    print("[OR-Tools] Defining optimization objectives...")
    objective_terms = []
    PRIORITY_WEIGHTS = {
        "DEMAND_SHORTAGE": 10000,
        "MIN_HOUR_SHORTAGE": 100,
        "SHIFT_PREFERENCE": 10,
        "STAFF_PRIORITY": 1,
    }

    # 1. Minimize Demand Shortage
    total_shortage = sum(shortage_vars.values())
    objective_terms.append(-total_shortage * PRIORITY_WEIGHTS["DEMAND_SHORTAGE"])
    print(
        f"  - Added: Minimize Demand Shortage (weight: {PRIORITY_WEIGHTS['DEMAND_SHORTAGE']})"
    )

    # 2. Minimize Min Weekly Hours Shortage
    total_min_hour_shortage = sum(min_hour_shortage_tenths.values())
    objective_terms.append(
        -total_min_hour_shortage * PRIORITY_WEIGHTS["MIN_HOUR_SHORTAGE"]
    )
    print(
        f"  - Added: Minimize Min Hour Shortage (weight: {PRIORITY_WEIGHTS['MIN_HOUR_SHORTAGE']})"
    )

    # 3. Handle Shift Preference
    if shift_preference == "PRIORITIZE_FULL_DAYS":
        full_day_vars = [var for k, var in assign_vars.items() if k[2] == "FULL_DAY"]
        if full_day_vars:
            total_full_days = model.NewIntVar(
                0, len(full_day_vars) + 1, "total_full_days"
            )
            model.Add(
                total_full_days == sum(full_day_vars)
            )  # Sum of FULL_DAY assignments
            objective_terms.append(
                total_full_days * PRIORITY_WEIGHTS["SHIFT_PREFERENCE"]
            )
            print(
                f"  - Added: Maximize Full Day Assignments (weight {PRIORITY_WEIGHTS['SHIFT_PREFERENCE']})"
            )
    elif shift_preference == "PRIORITIZE_HALF_DAYS":
        half_day_vars = [
            var
            for k, var in assign_vars.items()
            if k[2] == "HALF_DAY_AM" or k[2] == "HALF_DAY_PM"
        ]
        if half_day_vars:
            total_half_days = model.NewIntVar(
                0, len(half_day_vars) + 1, "total_half_days"
            )
            model.Add(total_half_days == sum(half_day_vars))
            objective_terms.append(
                total_half_days * PRIORITY_WEIGHTS["SHIFT_PREFERENCE"]
            )
            print(
                f"  - Added: Maximize Half Day Assignments (weight {PRIORITY_WEIGHTS['SHIFT_PREFERENCE']})"
            )

    # 4. Handle Staff Priority
    if staff_priority_list:
        print(
            f"  - Added: Prioritize Staff Hours based on list order (weight {PRIORITY_WEIGHTS['STAFF_PRIORITY']})"
        )
        staff_priority_objective = []
        max_prio = len(staff_priority_list)
        staff_prio_map = {
            s_id: max_prio - i for i, s_id in enumerate(staff_priority_list)
        }
        default_prio = 0
        for s_id in all_staff_ids:
            priority_score = staff_prio_map.get(s_id, default_prio)
            if priority_score > 0 and s_id in total_weekly_hours_tenths:
                staff_priority_objective.append(
                    total_weekly_hours_tenths[s_id] * priority_score
                )
        if staff_priority_objective:
            objective_terms.append(
                sum(staff_priority_objective) * PRIORITY_WEIGHTS["STAFF_PRIORITY"]
            )

    # Set combined objective
    if objective_terms:
        model.Maximize(sum(objective_terms))
        print("[OR-Tools] Combined objective function set.")
    else:
        print("[OR-Tools] No specific optimization objectives enabled.")

    # --- 6. Create Solver and Solve ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    print(f"[OR-Tools] Starting solver...")
    status = solver.Solve(model)
    end_time = time.perf_counter()
    calculation_time_ms = int((end_time - start_time) * 1000)
    print(
        f"[OR-Tools] Solver finished with status: {solver.StatusName(status)} in {calculation_time_ms} ms"
    )

    # --- 7. Process Results ---
    schedule = None
    warnings = []
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("[OR-Tools] Solution found. Building schedule dictionary...")
        schedule = {}
        for day in DAYS_OF_WEEK:
            schedule[day] = {}
        for st in SHIFT_TYPES:  # Use logical keys
            for day in DAYS_OF_WEEK:
                schedule[day][st] = {}

        for (s_id, d_idx, st, role), var in assign_vars.items():
            if var is not None and solver.Value(var) == 1:
                day = DAYS_OF_WEEK[d_idx]
                if st not in schedule[day]:
                    schedule[day][st] = {}
                if role not in schedule[day][st]:
                    schedule[day][st][role] = []
                if s_id not in schedule[day][st][role]:
                    schedule[day][st][role].append(s_id)

        # Check for shortages
        print("[OR-Tools] Checking for shortages...")
        final_total_shortage = 0
        for (d_idx, st, role), var in shortage_vars.items():
            if var is not None:
                shortage_amount = solver.Value(var)
                if shortage_amount > 0:
                    day = DAYS_OF_WEEK[d_idx]
                    warning_msg = f"Warning: Shortage of {shortage_amount} for {role} on {day} {st}."  # Use st
                    warnings.append(warning_msg)
                    print(warning_msg)
                    final_total_shortage += shortage_amount
        if final_total_shortage > 0:
            print(f"[OR-Tools] Total shortages found: {final_total_shortage}")
        else:
            print("[OR-Tools] No shortages found.")

        # Cleanup empty structures
        for day in list(schedule.keys()):
            for st in list(schedule[day].keys()):
                for role in list(schedule[day][st].keys()):
                    if not schedule[day][st][role]:
                        del schedule[day][st][role]
                if not schedule[day][st]:
                    del schedule[day][st]
            if not schedule[day]:
                del schedule[day]
        print("[OR-Tools] Schedule dictionary built and cleaned.")

        # Post-check for minimum weekly hours
        print("[OR-Tools] Performing post-check for minimum weekly hours...")
        for s_id, staff_data in staff_map.items():
            min_hours = staff_data.get("minHoursPerWeek")
            if (
                min_hours is not None
                and isinstance(min_hours, (int, float))
                and min_hours > 0
            ):
                # Use calculate_total_weekly_hours which now needs shiftDefinitions
                total_weekly_hours = calculate_total_weekly_hours(
                    s_id, schedule, shift_definitions
                )  # Pass definitions
                scheduled_at_all = total_weekly_hours > 0
                tolerance = 0.01
                min_shortage_var = min_hour_shortage_tenths.get(s_id)
                min_shortage_val = (
                    solver.Value(min_shortage_var)
                    if min_shortage_var is not None
                    else 0
                )
                if scheduled_at_all and total_weekly_hours < min_hours - tolerance:
                    warning_msg = f"Warning: Staff {staff_data.get('name', s_id)} scheduled for {total_weekly_hours:.1f}h, below minimum {min_hours}h."
                    # if min_shortage_val > 0: warning_msg += f" (Solver penalty applied for {min_shortage_val/10.0:.1f}h shortfall)" # Optional detail
                    warnings.append(warning_msg)
                    print(warning_msg)

    # Handle other statuses
    elif status == cp_model.INFEASIBLE:
        print("[OR-Tools] Model is infeasible (Hard constraints conflict).")
        warnings.append(
            "Error: Could not generate any schedule due to conflicting hard constraints (e.g., unavailability, max hours)."
        )
    elif status == cp_model.MODEL_INVALID:
        print("[OR-Tools] Model is invalid.")
        warnings.append("Error: The scheduling model definition is invalid.")
    else:
        print(f"[OR-Tools] Solver stopped with status: {solver.StatusName(status)}")
        warnings.append(
            f"Solver stopped without an optimal/feasible solution (Status: {solver.StatusName(status)}). Time limit might be too short or model issues."
        )

    final_schedule = (
        schedule
        if (status == cp_model.OPTIMAL or status == cp_model.FEASIBLE)
        else None
    )
    if final_schedule is not None and not final_schedule:
        print("[OR-Tools] Note: Solver found solution, but schedule is empty.")
    final_schedule = (
        final_schedule if final_schedule is not None else {}
    )  # Return empty dict on failure? Or None?

    return final_schedule, warnings, calculation_time_ms
