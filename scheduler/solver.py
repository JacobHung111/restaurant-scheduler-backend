# scheduler/solver.py
import time
from ortools.sat.python import cp_model
from .constants import DAYS_OF_WEEK, SHIFTS, ALL_ROLES
from .utils import time_to_minutes, calculate_total_weekly_hours


# --------------------------------------
# === OR-Tools Scheduling Core Logic ===
# --------------------------------------
def generate_schedule_with_ortools(
    weekly_needs,
    staff_list,
    unavailability_list,
    shift_preference="PRIORITIZE_FULL_DAYS",
    staff_priority_list=[],
):
    """
    Generates schedule using OR-Tools.
    Hard Constraints: Max hours, Unavailability, Single Role per Shift, Role Skill.
    Soft Constraints/Goals (prioritized):
    1. Minimize Demand Shortage (Implicit High Priority)
    2. Minimize Min Weekly Hours Shortage (Implicit Medium Priority)
    3. Handle Shift Preference (Full/Half/None) (Configurable Weight)
    4. Handle Staff Priority (Configurable Weight)
    """
    print(
        f"[OR-Tools] Starting generation (Preference: {shift_preference}, Staff Priority: {len(staff_priority_list)} defined)..."
    )
    start_time = time.perf_counter()

    # 1. Data preprocessing and validation
    if not isinstance(staff_list, list) or not staff_list:
        return None, ["Error: Staff list is empty or invalid."], 0
    if not isinstance(weekly_needs, dict):
        return None, ["Error: Weekly needs data is invalid."], 0
    if not isinstance(unavailability_list, list):
        unavailability_list = []

    staff_map = {s["id"]: s for s in staff_list if isinstance(s, dict) and "id" in s}
    all_staff_ids = list(staff_map.keys())
    if not all_staff_ids:
        return None, ["Error: Could not extract valid staff IDs from staffList."], 0
    max_possible_shortage = len(all_staff_ids) + 1

    model = cp_model.CpModel()

    # --- 3. Define Core Variables ---
    assign_vars = {}  # (s_id, d_idx, sk, role) -> BoolVar
    shortage_vars = {}  # (d_idx, sk, role) -> IntVar >= 0
    min_hour_shortage_tenths = {}  # (s_id) -> IntVar >= 0
    total_weekly_hours_tenths = {}  # (s_id) -> IntVar >= 0

    # Create assign_vars
    for s_id in all_staff_ids:
        staff_data = staff_map[s_id]
        possible_roles = staff_data.get("roles", [])
        for d_idx, day in enumerate(DAYS_OF_WEEK):
            for sk in SHIFTS.keys():
                for role in ALL_ROLES:
                    if role in possible_roles:
                        assign_vars[(s_id, d_idx, sk, role)] = model.NewBoolVar(
                            f"assign_{s_id}_{day}_{sk}_{role}"
                        )

    # Create shortage_vars
    for d_idx, day in enumerate(DAYS_OF_WEEK):
        for sk in SHIFTS.keys():
            for role in ALL_ROLES:
                shortage_vars[(d_idx, sk, role)] = model.NewIntVar(
                    0, max_possible_shortage, f"shortage_{day}_{sk}_{role}"
                )

    # Create total_weekly_hours_tenths and min_hour_shortage_tenths vars
    for s_id, staff_data in staff_map.items():
        weekly_hours_terms = []
        for d_idx, day in enumerate(DAYS_OF_WEEK):
            for sk, shift_info in SHIFTS.items():
                shift_duration_tenths = int(shift_info.get("hours", 0) * 10)
                if shift_duration_tenths > 0:
                    vars_for_shift_this_employee = [
                        var
                        for k, var in assign_vars.items()
                        if k[0] == s_id and k[1] == d_idx and k[2] == sk
                    ]
                    if vars_for_shift_this_employee:
                        works_this_shift = model.NewBoolVar(f"works_{s_id}_{day}_{sk}")
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
        if (
            min_hours is not None
            and isinstance(min_hours, (int, float))
            and min_hours > 0
        ):
            min_hours_tenths_target = int(min_hours * 10)
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

    # --- 4. Add Hard Constraints ---

    # HC1: Demand Equation (sum + shortage = need)
    print("[OR-Tools] Adding HARD constraint: Demand equation...")
    for d_idx, day in enumerate(DAYS_OF_WEEK):
        for sk in SHIFTS.keys():
            for role in ALL_ROLES:
                needed_count = weekly_needs.get(day, {}).get(sk, {}).get(role, 0)
                needed_count = max(0, int(needed_count))
                qualified_assign_vars = [
                    var
                    for k, var in assign_vars.items()
                    if k[1] == d_idx and k[2] == sk and k[3] == role
                ]
                shortage_var = shortage_vars.get((d_idx, sk, role))
                if shortage_var is not None:
                    model.Add(sum(qualified_assign_vars) + shortage_var == needed_count)

    # HC2: Single Role per Shift
    print("[OR-Tools] Adding HARD constraint: Single role per shift...")
    for s_id in all_staff_ids:
        for d_idx, day in enumerate(DAYS_OF_WEEK):
            for sk in SHIFTS.keys():
                vars_for_staff_shift = [
                    var
                    for k, var in assign_vars.items()
                    if k[0] == s_id and k[1] == d_idx and k[2] == sk
                ]
                if len(vars_for_staff_shift) > 0:
                    model.Add(sum(vars_for_staff_shift) <= 1)

    # HC3: Unavailability
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
            for sk, shift_info in SHIFTS.items():
                shift_start_min = time_to_minutes(shift_info["start"])
                shift_end_min = time_to_minutes(shift_info["end"])
                overlap = (shift_start_min < effective_unav_end_min) and (
                    unav_start_min < shift_end_min
                )
                covers = (unav_start_min <= shift_start_min) and (
                    effective_unav_end_min >= shift_end_min
                )
                if overlap or covers:
                    for role in ALL_ROLES:
                        var = assign_vars.get((s_id, d_idx, sk, role))
                        if var is not None:
                            model.Add(var == 0)

    # HC4: Max Weekly Hours
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

    # --- 5. Define Optimization Objective based on Configuration ---
    print("[OR-Tools] Defining optimization objectives...")
    objective_terms = []

    # Define weights for different objectives (adjust these values for tuning)
    # Make sure demand shortage has the highest penalty
    WEIGHT_DEMAND_SHORTAGE = 10000
    WEIGHT_MIN_HOUR_SHORTAGE = 100
    WEIGHT_SHIFT_PREFERENCE = 10
    WEIGHT_STAFF_PRIORITY = 1

    # Objective 1: Minimize Demand Shortage (always highest priority)
    total_shortage = sum(shortage_vars.values())
    objective_terms.append(-total_shortage * WEIGHT_DEMAND_SHORTAGE)
    print(f"  - Added: Minimize Demand Shortage (weight: {WEIGHT_DEMAND_SHORTAGE})")

    # Objective 2: Minimize Min Weekly Hours Shortage (next priority)
    total_min_hour_shortage = sum(min_hour_shortage_tenths.values())
    objective_terms.append(-total_min_hour_shortage * WEIGHT_MIN_HOUR_SHORTAGE)
    print(f"  - Added: Minimize Min Hour Shortage (weight: {WEIGHT_MIN_HOUR_SHORTAGE})")

    # Objective 3: Handle Shift Preference
    if shift_preference == "PRIORITIZE_FULL_DAYS":
        full_day_bonuses = []
        for s_id in all_staff_ids:
            staff_roles = staff_map[s_id].get("roles", [])
            for d_idx, day in enumerate(DAYS_OF_WEEK):
                for role in staff_roles:
                    if role in ALL_ROLES:
                        var_am = assign_vars.get((s_id, d_idx, "11:00-16:00", role))
                        var_pm = assign_vars.get((s_id, d_idx, "16:00-21:00", role))
                        if var_am is not None and var_pm is not None:
                            works_full_day_role = model.NewBoolVar(
                                f"full_day_{s_id}_{day}_{role}"
                            )
                            model.AddBoolAnd([var_am, var_pm]).OnlyEnforceIf(
                                works_full_day_role
                            )
                            model.Add(works_full_day_role <= var_am)
                            model.Add(works_full_day_role <= var_pm)
                            full_day_bonuses.append(works_full_day_role)
        if full_day_bonuses:
            total_full_days = model.NewIntVar(
                0, len(full_day_bonuses) + 1, "total_full_days"
            )
            model.Add(total_full_days == sum(full_day_bonuses))
            objective_terms.append(total_full_days * WEIGHT_SHIFT_PREFERENCE)
            print(f"  - Added: Maximize Full Days (weight {WEIGHT_SHIFT_PREFERENCE})")

    elif shift_preference == "PRIORITIZE_HALF_DAYS":
        half_day_indicators = []
        for s_id in all_staff_ids:
            for d_idx in range(len(DAYS_OF_WEEK)):
                works_am_vars = [
                    assign_vars.get((s_id, d_idx, "11:00-16:00", r))
                    for r in staff_map[s_id].get("roles", [])
                    if assign_vars.get((s_id, d_idx, "11:00-16:00", r))
                ]
                works_pm_vars = [
                    assign_vars.get((s_id, d_idx, "16:00-21:00", r))
                    for r in staff_map[s_id].get("roles", [])
                    if assign_vars.get((s_id, d_idx, "16:00-21:00", r))
                ]

                works_am = model.NewBoolVar(f"works_am_{s_id}_{d_idx}")
                model.Add(sum(works_am_vars) >= 1).OnlyEnforceIf(works_am)
                model.Add(sum(works_am_vars) == 0).OnlyEnforceIf(works_am.Not())

                works_pm = model.NewBoolVar(f"works_pm_{s_id}_{d_idx}")
                model.Add(sum(works_pm_vars) >= 1).OnlyEnforceIf(works_pm)
                model.Add(sum(works_pm_vars) == 0).OnlyEnforceIf(works_pm.Not())

                works_half_day = model.NewBoolVar(f"half_day_{s_id}_{d_idx}")
                model.Add(works_am + works_pm == 1).OnlyEnforceIf(
                    works_half_day
                )  # Exactly one shift
                model.Add(works_am + works_pm != 1).OnlyEnforceIf(works_half_day.Not())
                half_day_indicators.append(works_half_day)
        if half_day_indicators:
            total_half_days = model.NewIntVar(
                0, len(half_day_indicators) + 1, "total_half_days"
            )
            model.Add(total_half_days == sum(half_day_indicators))
            objective_terms.append(
                total_half_days * WEIGHT_SHIFT_PREFERENCE
            )  # Maximize half days
            print(f"  - Added: Maximize Half Days (weight {WEIGHT_SHIFT_PREFERENCE})")

    # Objective 4: Handle Staff Priority (Lower Priority)
    if staff_priority_list and isinstance(staff_priority_list, list):
        print(
            f"  - Added: Prioritize Staff based on list order (weight {WEIGHT_STAFF_PRIORITY})"
        )
        staff_priority_objective = []
        # Higher score for staff earlier in the list
        max_prio_score = len(staff_priority_list)
        staff_prio_map = {
            s_id: max_prio_score - i for i, s_id in enumerate(staff_priority_list)
        }
        default_prio_score = 0  # Staff not in the list get zero priority score

        for s_id in all_staff_ids:
            priority_score = staff_prio_map.get(s_id, default_prio_score)
            if priority_score > 0 and s_id in total_weekly_hours_tenths:
                # Maximize weighted hours for higher priority staff
                staff_priority_objective.append(
                    total_weekly_hours_tenths[s_id] * priority_score
                )

        if staff_priority_objective:
            # Add the weighted sum to the objective, multiplied by the overall staff priority weight
            objective_terms.append(
                sum(staff_priority_objective) * WEIGHT_STAFF_PRIORITY
            )

    # --- Set the combined objective ---
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
        for sk in SHIFTS.keys():
            for day in DAYS_OF_WEEK:
                schedule[day][sk] = {}

        for (s_id, d_idx, sk, role), var in assign_vars.items():
            if var is not None and solver.Value(var) == 1:
                day = DAYS_OF_WEEK[d_idx]
                if sk not in schedule[day]:
                    schedule[day][sk] = {}
                if role not in schedule[day][sk]:
                    schedule[day][sk][role] = []
                if s_id not in schedule[day][sk][role]:
                    schedule[day][sk][role].append(s_id)

        # Check for shortages and add warnings
        print("[OR-Tools] Checking for shortages...")
        final_total_shortage = 0
        for (d_idx, sk, role), var in shortage_vars.items():
            if var is not None:
                shortage_amount = solver.Value(var)
                if shortage_amount > 0:
                    day = DAYS_OF_WEEK[d_idx]
                    warning_msg = f"Warning: Shortage of {shortage_amount} for {role} on {day} {sk}."
                    warnings.append(warning_msg)
                    print(warning_msg)
                    final_total_shortage += shortage_amount
        if final_total_shortage > 0:
            print(f"[OR-Tools] Total shortages found: {final_total_shortage}")
        else:
            print("[OR-Tools] No shortages found.")

        # Cleanup empty structures
        for day in list(schedule.keys()):
            for sk in list(schedule[day].keys()):
                for role in list(schedule[day][sk].keys()):
                    if not schedule[day][sk][role]:
                        del schedule[day][sk][role]
                if not schedule[day][sk]:
                    del schedule[day][sk]
            if not schedule[day]:
                del schedule[day]
        print("[OR-Tools] Schedule dictionary built and cleaned.")

        # Post-check for minimum weekly hours (uses helper)
        print("[OR-Tools] Performing post-check for minimum weekly hours...")
        for s_id, staff_data in staff_map.items():
            min_hours = staff_data.get("minHoursPerWeek")
            if (
                min_hours is not None
                and isinstance(min_hours, (int, float))
                and min_hours > 0
            ):
                total_weekly_hours = calculate_total_weekly_hours(s_id, schedule)
                scheduled_at_all = total_weekly_hours > 0
                tolerance = 0.01
                min_shortage_var = min_hour_shortage_tenths.get(s_id)
                min_shortage_val = (
                    solver.Value(min_shortage_var)
                    if min_shortage_var is not None
                    else 0
                )
                # Add warning only if solver indicated a shortage for this specific goal (if implemented as hard check before)
                # OR simply check the calculated hours like before
                if scheduled_at_all and total_weekly_hours < min_hours - tolerance:
                    warning_msg = f"Warning: Staff {staff_data.get('name', s_id)} scheduled for {total_weekly_hours:.1f}h, below minimum {min_hours}h."
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
        print(
            "[OR-Tools] Note: Solver found a solution, but the resulting schedule is empty."
        )
        final_schedule = {}

    return final_schedule, warnings, calculation_time_ms
