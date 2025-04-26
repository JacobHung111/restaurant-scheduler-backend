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
        print("Attempting to get JSON data from request...")
        data = request.get_json()
        if not data:
            print("Error: Request body is empty or not valid JSON.")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Request body is empty or not valid JSON.",
                    }
                ),
                400,
            )

        # --- Extract data including new optimization parameters ---
        staff_list = data.get("staffList")
        unavailability_list = data.get("unavailabilityList")
        weekly_needs = data.get("weeklyNeeds")
        # Get optimization params with defaults
        shift_preference = data.get(
            "shiftPreference", "PRIORITIZE_FULL_DAYS"
        )  # Default to full days
        staff_priority_list = data.get("staffPriority", [])  # Default to empty list

        # --- Basic Input Validation ---
        if (
            not isinstance(staff_list, list)
            or not isinstance(unavailability_list, list)
            or not isinstance(weekly_needs, dict)
            or shift_preference
            not in ["PRIORITIZE_FULL_DAYS", "PRIORITIZE_HALF_DAYS", "NONE"]
            or not isinstance(staff_priority_list, list)
        ):
            print("Error: Missing or invalid type for required data fields.")
            # Provide more specific error message
            errors = []
            if not isinstance(staff_list, list):
                errors.append("staffList (must be an array)")
            if not isinstance(unavailability_list, list):
                errors.append("unavailabilityList (must be an array)")
            if not isinstance(weekly_needs, dict):
                errors.append("weeklyNeeds (must be an object)")
            if shift_preference not in [
                "PRIORITIZE_FULL_DAYS",
                "PRIORITIZE_HALF_DAYS",
                "NONE",
            ]:
                errors.append("Invalid shiftPreference value")
            if not isinstance(staff_priority_list, list):
                errors.append("staffPriority (must be an array)")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Missing or invalid type for fields: {', '.join(errors)}",
                    }
                ),
                400,
            )
        # Optional: Add validation for content of staff_priority_list (e.g., are they valid IDs?)

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

    # --- Call Scheduling Logic with optimization params ---
    try:
        print("Calling generate_schedule_with_ortools ...")
        schedule_result, warnings_list, calculation_time = (
            generate_schedule_with_ortools(
                weekly_needs,
                staff_list,
                unavailability_list,
                shift_preference,
                staff_priority_list,  # Pass new params
            )
        )
        print(
            f"generate_schedule_with_ortools returned. Success: {schedule_result is not None}"
        )

        # --- Handle Solver Results ---
        if schedule_result is not None:
            print(f"Scheduling logic completed in {calculation_time} ms.")
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
        else:  # Solver failed
            print("Scheduling logic failed to find a solution (returned None).")
            # Check if specific infeasibility warning exists from solver
            fail_message = "Could not find a schedule satisfying all constraints or model is invalid."
            if warnings_list and any("Error:" in w for w in warnings_list):
                fail_message = "Could not generate schedule due to hard constraint conflicts or model errors."

            return (
                jsonify(
                    {
                        "success": False,
                        "message": fail_message,
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
