# app.py
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from scheduler.solver import generate_schedule_with_ortools
from scheduler.utils import validate_shift_definitions

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app)
print("Flask app instance created and CORS enabled.")


# --- API Endpoint ---
@app.route("/api/schedule", methods=["POST"])
def handle_schedule_request():
    print(f"\n--- Received request at /api/schedule ({request.method}) ---")
    try:
        data = request.get_json()
        if not data:
            return (
                jsonify({"success": False, "message": "Request body empty/not JSON."}),
                400,
            )

        # --- Extract data ---
        staff_list = data.get("staffList")
        unavailability_list = data.get("unavailabilityList")
        weekly_needs = data.get("weeklyNeeds")
        shift_definitions = data.get("shiftDefinitions")
        shift_preference = data.get("shiftPreference", "PRIORITIZE_FULL_DAYS")
        staff_priority_list = data.get("staffPriority", [])

        # --- Basic Type Validation ---
        if (
            not isinstance(staff_list, list)
            or not isinstance(unavailability_list, list)
            or not isinstance(weekly_needs, dict)
            or not isinstance(shift_definitions, dict)
            or shift_preference
            not in ["PRIORITIZE_FULL_DAYS", "PRIORITIZE_HALF_DAYS", "NONE"]
            or not isinstance(staff_priority_list, list)
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Missing or invalid type for input fields.",
                    }
                ),
                400,
            )

        is_valid_shifts, shift_error_msg = validate_shift_definitions(shift_definitions)
        if not is_valid_shifts:
            print(f"Error: Invalid shift definitions - {shift_error_msg}")
            return jsonify({"success": False, "message": shift_error_msg}), 400

        # *** Validate Staff List Structure and Priority List ***
        if staff_list:
            valid_staff_ids = set()
            for staff in staff_list:
                if (
                    not isinstance(staff, dict)
                    or not staff.get("id")
                    or not isinstance(staff.get("assignedRolesInPriority"), list)
                ):
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "Invalid staff structure in staffList.",
                            }
                        ),
                        400,
                    )
                valid_staff_ids.add(staff.get("id"))
                assigned_roles = staff.get("assignedRolesInPriority")
                if assigned_roles is not None and not isinstance(assigned_roles, list):
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": f"Invalid assignedRolesInPriority for staff {staff.get('id')}",
                            }
                        ),
                        400,
                    )
            # Validate staffPriority list contains valid IDs
            invalid_prio_ids = [
                sid for sid in staff_priority_list if sid not in valid_staff_ids
            ]
            if invalid_prio_ids:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": f"Invalid staff IDs found in staffPriority list: {', '.join(invalid_prio_ids)}",
                        }
                    ),
                    400,
                )

        print(
            f"Received staff: {len(staff_list)}, unav: {len(unavailability_list)}, needs days: {len(weekly_needs)}, "
            f"shiftPref: {shift_preference}, staffPrio: {len(staff_priority_list)}"
        )

    except Exception as e:
        print(f"Error parsing request JSON: {e}")
        traceback.print_exc()
        return (
            jsonify({"success": False, "message": "Error parsing request data."}),
            400,
        )

    # --- Call Scheduling Logic ---
    try:
        print("Calling generate_schedule_with_ortools...")
        schedule_result, warnings_list, calculation_time = (
            generate_schedule_with_ortools(
                weekly_needs,
                staff_list,
                unavailability_list,
                shift_definitions,
                shift_preference,
                staff_priority_list,
            )
        )
        print(
            f"generate_schedule_with_ortools returned. Success: {schedule_result is not None}"
        )

        if schedule_result is not None:
            return (
                jsonify(
                    {
                        "success": True,
                        "schedule": schedule_result,
                        "warnings": warnings_list if warnings_list else [],
                        "calculationTimeMs": calculation_time,
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Could not find a valid schedule.",
                        "warnings": warnings_list if warnings_list else [],
                    }
                ),
                422,
            )

    except Exception as schedule_error:
        print(f"!!! Error during OR-Tools scheduling execution: {schedule_error} !!!")
        traceback.print_exc()
        return (
            jsonify(
                {
                    "success": False,
                    "message": "An internal error occurred during schedule calculation.",
                }
            ),
            500,
        )


# --- Run Server ---
if __name__ == "__main__":
    print("Script is being run directly, starting Flask development server...")
    app.run(host="0.0.0.0", port=5001, debug=True)  # Use port 5001
