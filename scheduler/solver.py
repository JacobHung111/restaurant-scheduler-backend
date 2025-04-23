# scheduler/solver.py
import time
from ortools.sat.python import cp_model
from .constants import DAYS_OF_WEEK, SHIFTS, ALL_ROLES
from .utils import time_to_minutes, calculate_total_weekly_hours

# --------------------------------------
# === OR-Tools Scheduling Core Logic ===
# --------------------------------------
def generate_schedule_with_ortools(weekly_needs, staff_list, unavailability_list):
    print("[OR-Tools] Starting schedule generation...")
    start_time = time.perf_counter()

    # 1. Data preprocessing and validation
    if not isinstance(staff_list, list) or not staff_list:
        return None, ["Error: Staff list is empty or invalid."], 0
    if not isinstance(weekly_needs, dict):
        return None, ["Error: Weekly needs data is invalid."], 0
    if not isinstance(unavailability_list, list):
        unavailability_list = [] # Treat invalid as empty

    staff_map = {s['id']: s for s in staff_list if isinstance(s, dict) and 'id' in s}
    all_staff_ids = list(staff_map.keys())
    if not all_staff_ids:
         return None, ["Error: Could not extract valid staff IDs from staffList."], 0
    max_possible_shortage = len(all_staff_ids) + 1 # Theoretical max shortage per slot

    # --- Create CP-SAT model ---
    model = cp_model.CpModel()

    # --- Define core variables (Assignment + Shortage) ---
    assign_vars = {} # (s_id, d_idx, sk, role) -> BoolVar
    shortage_vars = {} # (d_idx, sk, role) -> IntVar (non-negative)

    # Create assign_vars first
    for s_id in all_staff_ids:
        staff_data = staff_map[s_id]
        possible_roles = staff_data.get('roles', [])
        for d_idx, day in enumerate(DAYS_OF_WEEK):
            for sk in SHIFTS.keys():
                for role in ALL_ROLES:
                    if role in possible_roles:
                        assign_vars[(s_id, d_idx, sk, role)] = model.NewBoolVar(f'assign_{s_id}_{day}_{sk}_{role}')

    # Create shortage_vars
    for d_idx, day in enumerate(DAYS_OF_WEEK):
        for sk in SHIFTS.keys():
            for role in ALL_ROLES:
                shortage_key = (d_idx, sk, role)
                shortage_vars[shortage_key] = model.NewIntVar(0, max_possible_shortage, f'shortage_{day}_{sk}_{role}')

    # --- Add Constraints ---

    # Constraint 1: Demand Satisfaction (linked with shortage)
    print("[OR-Tools] Adding demand satisfaction constraints (with shortage)...")
    for d_idx, day in enumerate(DAYS_OF_WEEK):
        for sk in SHIFTS.keys():
            for role in ALL_ROLES:
                # Get needed count, default to 0
                needed_count = weekly_needs.get(day, {}).get(sk, {}).get(role, 0)
                try: needed_count = int(needed_count)
                except (ValueError, TypeError): needed_count = 0
                if needed_count < 0: needed_count = 0 # Treat negative as zero

                # Get all assign_vars for this specific slot and role
                qualified_assign_vars = [var for k, var in assign_vars.items() if k[1] == d_idx and k[2] == sk and k[3] == role]

                # Get the corresponding shortage variable
                shortage_var = shortage_vars.get((d_idx, sk, role))

                if shortage_var is not None:
                    # Constraint: sum(assigned) + shortage == needed
                    model.Add(sum(qualified_assign_vars) + shortage_var == needed_count)
                # No 'else' needed, as shortage_var should always exist now

    # Constraint 2: Employee works at most one role per shift
    print("[OR-Tools] Adding single assignment constraint per shift...")
    for s_id in all_staff_ids:
        for d_idx, day in enumerate(DAYS_OF_WEEK):
            for sk in SHIFTS.keys():
                vars_for_staff_shift = [var for k, var in assign_vars.items() if k[0] == s_id and k[1] == d_idx and k[2] == sk]
                if len(vars_for_staff_shift) > 0: model.Add(sum(vars_for_staff_shift) <= 1)

    # Constraint 3: Unavailability
    print("[OR-Tools] Adding unavailability constraints...")
    for unav in unavailability_list:
        s_id = unav.get('employeeId'); day = unav.get('dayOfWeek'); shifts_unav = unav.get('shifts')
        if not s_id or s_id not in staff_map or day not in DAYS_OF_WEEK or not isinstance(shifts_unav, list): continue
        d_idx = DAYS_OF_WEEK.index(day)
        for unav_span in shifts_unav:
            if not isinstance(unav_span, dict) or 'start' not in unav_span or 'end' not in unav_span: continue
            unav_start_min = time_to_minutes(unav_span['start']); unav_end_min = time_to_minutes(unav_span['end'])
            effective_unav_end_min = 24 * 60 if (unav_end_min <= unav_start_min and not (unav_start_min == 0 and unav_end_min == 0)) else unav_end_min
            if effective_unav_end_min == 0 and unav_start_min == 0: continue
            for sk, shift_info in SHIFTS.items():
                shift_start_min = time_to_minutes(shift_info['start']); shift_end_min = time_to_minutes(shift_info['end'])
                overlap = (shift_start_min < effective_unav_end_min) and (unav_start_min < shift_end_min)
                covers = (unav_start_min <= shift_start_min) and (effective_unav_end_min >= shift_end_min)
                if overlap or covers:
                    for role in ALL_ROLES:
                         var = assign_vars.get((s_id, d_idx, sk, role))
                         if var is not None: model.Add(var == 0)

    # Constraint 4: Max Weekly Hours
    print("[OR-Tools] Adding max weekly hours constraints...")
    for s_id, staff_data in staff_map.items():
        max_hours = staff_data.get('maxHoursPerWeek')
        # Ensure max_hours is a valid number before adding constraint
        if max_hours is not None and isinstance(max_hours, (int, float)) and max_hours >= 0:
            weekly_hours_terms = []
            for d_idx, day in enumerate(DAYS_OF_WEEK):
                for sk, shift_info in SHIFTS.items():
                    # Use integer representation of hours (e.g., tenths of an hour) for CP-SAT
                    shift_duration_tenths = int(shift_info.get('hours', 0) * 10)
                    if shift_duration_tenths > 0:
                        # Sum variables for all roles this person could work in this shift
                        vars_for_shift_this_employee = [var for k, var in assign_vars.items() if k[0] == s_id and k[1] == d_idx and k[2] == sk]

                        # If there are potential assignments for this employee in this shift
                        if vars_for_shift_this_employee:
                            # Intermediate variable: does the employee work this shift (in any role)?
                            works_this_shift = model.NewBoolVar(f'works_{s_id}_{day}_{sk}')
                            # Link works_this_shift to the sum of assign_vars for this shift
                            # works_this_shift is true if sum >= 1
                            model.Add(sum(vars_for_shift_this_employee) >= 1).OnlyEnforceIf(works_this_shift)
                            # works_this_shift is false if sum == 0
                            model.Add(sum(vars_for_shift_this_employee) == 0).OnlyEnforceIf(works_this_shift.Not())
                            # Add the term to the weekly hours sum
                            weekly_hours_terms.append(works_this_shift * shift_duration_tenths)

            if weekly_hours_terms:
                 # Constraint: total weekly hours (in tenths) <= max_hours (in tenths)
                 model.Add(sum(weekly_hours_terms) <= int(max_hours * 10))


    # --- Optimization Objectives ---
    print("[OR-Tools] Defining optimization objectives...")
    # Objective 1: Minimize total shortage (high penalty)
    total_shortage = model.NewIntVar(0, max_possible_shortage * len(DAYS_OF_WEEK) * len(SHIFTS) * len(ALL_ROLES), 'total_shortage')
    model.Add(total_shortage == sum(shortage_vars.values()))

    # Objective 2: Maximize full days (lower weight)
    full_day_bonuses = []
    for s_id in all_staff_ids:
         staff_roles = staff_map[s_id].get('roles', [])
         for d_idx, day in enumerate(DAYS_OF_WEEK):
              for role in staff_roles:
                    if role in ALL_ROLES:
                        var_am = assign_vars.get((s_id, d_idx, "11:00-16:00", role))
                        var_pm = assign_vars.get((s_id, d_idx, "16:00-21:00", role))
                        if var_am is not None and var_pm is not None:
                            works_full_day_role = model.NewBoolVar(f'full_day_{s_id}_{day}_{role}')
                            model.AddBoolAnd([var_am, var_pm]).OnlyEnforceIf(works_full_day_role)
                            model.Add(works_full_day_role <= var_am)
                            model.Add(works_full_day_role <= var_pm)
                            full_day_bonuses.append(works_full_day_role)

    total_full_days = model.NewIntVar(0, len(full_day_bonuses) + 1, 'total_full_days') # Adjust upper bound if needed
    if full_day_bonuses:
        model.Add(total_full_days == sum(full_day_bonuses))
    else:
        model.Add(total_full_days == 0)

    # Combine objectives: Maximize (Bonus * weight1 - Penalty * weight2)
    # Ensure penalty weight is significantly higher than bonus weight
    penalty_weight = 100 # High penalty for each unit of shortage
    full_day_weight = 1  # Smaller bonus for each full day worked
    model.Maximize(total_full_days * full_day_weight - total_shortage * penalty_weight)


    # --- Create Solver and Solve ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0 # Time limit
    print(f"[OR-Tools] Starting solver (max time: {solver.parameters.max_time_in_seconds}s)...")
    status = solver.Solve(model)
    end_time = time.perf_counter()
    calculation_time_ms = int((end_time - start_time) * 1000)
    print(f"[OR-Tools] Solver finished with status: {solver.StatusName(status)} in {calculation_time_ms} ms")

    # --- Process Results ---
    schedule = None
    warnings = []
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("[OR-Tools] Solution found. Building schedule dictionary...")
        schedule = {}
        # Initialize structure
        for day in DAYS_OF_WEEK:
            schedule[day] = {}
            for sk in SHIFTS.keys():
                 schedule[day][sk] = {}

        # Populate based on assign_vars
        for (s_id, d_idx, sk, role), var in assign_vars.items():
            if var is not None and solver.Value(var) == 1:
                day = DAYS_OF_WEEK[d_idx]
                if role not in schedule[day][sk]: schedule[day][sk][role] = []
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
        if final_total_shortage > 0: print(f"[OR-Tools] Total shortages found: {final_total_shortage}")
        else: print("[OR-Tools] No shortages found.")

        # Cleanup empty structures
        for day in list(schedule.keys()):
            for sk in list(schedule[day].keys()):
                for role in list(schedule[day][sk].keys()):
                    if not schedule[day][sk][role]: del schedule[day][sk][role]
                if not schedule[day][sk]: del schedule[day][sk]
            if not schedule[day]: del schedule[day]
        print("[OR-Tools] Schedule dictionary built and cleaned.")

        # Post-check for minimum weekly hours
        print("[OR-Tools] Performing post-check for minimum weekly hours...")
        for s_id, staff_data in staff_map.items():
            min_hours = staff_data.get('minHoursPerWeek')
            if min_hours is not None and isinstance(min_hours, (int, float)) and min_hours > 0:
                # Use helper function defined above
                total_weekly_hours = calculate_total_weekly_hours(s_id, schedule)
                scheduled_at_all = total_weekly_hours > 0
                tolerance = 0.01 # Tolerance for float comparison
                if scheduled_at_all and total_weekly_hours < min_hours - tolerance:
                    warning_msg = f"Warning: Staff {staff_data.get('name', s_id)} total weekly hours {total_weekly_hours:.1f}h is below minimum {min_hours}h."
                    warnings.append(warning_msg)
                    print(warning_msg)

    # Handle other statuses
    elif status == cp_model.INFEASIBLE:
        print("[OR-Tools] Model is infeasible (Hard constraints conflict).")
        warnings.append("Error: Could not generate any schedule due to conflicting hard constraints (e.g., unavailability, max hours).")
    elif status == cp_model.MODEL_INVALID:
         print("[OR-Tools] Model is invalid.")
         warnings.append("Error: The scheduling model definition is invalid.")
    else:
         print(f"[OR-Tools] Solver stopped with status: {solver.StatusName(status)}")
         warnings.append(f"Solver stopped without an optimal/feasible solution (Status: {solver.StatusName(status)}). Time limit might be too short or model issues.")

    # Determine final schedule object (can be empty dict if feasible but no assignments)
    final_schedule = schedule if (status == cp_model.OPTIMAL or status == cp_model.FEASIBLE) else None
    if final_schedule is not None and not final_schedule:
        print("[OR-Tools] Note: Solver found a solution, but the resulting schedule is empty.")
        final_schedule = {} # Return empty dict for feasible empty schedule

    return final_schedule, warnings, calculation_time_ms