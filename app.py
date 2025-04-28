# app.py
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from scheduler.solver import generate_schedule_with_ortools

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
                jsonify(
                    {
                        "success": False,
                        "message": "Request body is empty or not valid JSON.",
                    }
                ),
                400,
            )

        staff_list = data.get("staffList")
        unavailability_list = data.get("unavailabilityList")
        weekly_needs = data.get("weeklyNeeds")
        # *** Get shift definitions and optimization params ***
        shift_definitions = data.get("shiftDefinitions")
        shift_preference = data.get("shiftPreference", "PRIORITIZE_FULL_DAYS")
        staff_priority_list = data.get("staffPriority", [])

        # --- Validation (Add validation for shiftDefinitions) ---
        if (
            not isinstance(staff_list, list)
            or not isinstance(unavailability_list, list)
            or not isinstance(weekly_needs, dict)
            or not isinstance(shift_definitions, dict)
            or shift_preference
            not in ["PRIORITIZE_FULL_DAYS", "PRIORITIZE_HALF_DAYS", "NONE"]
            or not isinstance(staff_priority_list, list)
        ):
            print("Error: Missing or invalid type for required data fields.")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Missing or invalid type for input fields.",
                    }
                ),
                400,
            )
        # *** Add validation for shiftDefinitions content (AM End == PM Start etc.) ***
        try:
            if (
                shift_definitions["HALF_DAY_AM"]["end"]
                != shift_definitions["HALF_DAY_PM"]["start"]
            ):
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Invalid shift definition: AM end time must equal PM start time.",
                        }
                    ),
                    400,
                )
            # Add more checks if needed (valid times, start < end)
        except (KeyError, TypeError):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid or incomplete shift definition structure.",
                    }
                ),
                400,
            )

        print(
            f"Received staff: {len(staff_list)}, unav: {len(unavailability_list)}, needs days: {len(weekly_needs)}, "
            f"shiftPref: {shift_preference}, staffPrio: {len(staff_priority_list)}"
        )
        # print("Shift Definitions:", shift_definitions) # Debug log

    except Exception as e:
        print(f"Error parsing request JSON: {e}")
        traceback.print_exc()
        return (
            jsonify({"success": False, "message": "Error parsing request data."}),
            400,
        )

    # --- Call Scheduling Logic ---
    try:
        print("Calling generate_schedule_with_ortools (V7)...")
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
            f"generate_schedule_with_ortools (V7) returned. Success: {schedule_result is not None}"
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
                        "message": "Could not find a valid schedule based on constraints.",
                        "warnings": warnings_list if warnings_list else [],
                    }
                ),
                422,
            )

    except Exception as schedule_error:
        print(
            f"!!! Error during OR-Tools V7 scheduling execution: {schedule_error} !!!"
        )
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
