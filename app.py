# app.py (Main Application File)
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from scheduler.solver import generate_schedule_with_ortools

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app)
print("Flask app instance created and CORS enabled.")

# --- API Endpoint ---
@app.route('/api/schedule', methods=['POST'])
def handle_schedule_request():
    """Handles POST requests to generate the weekly schedule."""
    # Use print for basic backend logging
    print(f"\n--- Received request at /api/schedule ({request.method}) ---")
    try:
        print("Attempting to get JSON data from request...")
        data = request.get_json()
        if not data:
             print("Error: Request body is empty or not valid JSON.")
             # Return JSON error response with 400 status code
             return jsonify({"success": False, "message": "Request body is empty or not valid JSON."}), 400

        # --- Basic Input Validation ---
        staff_list = data.get('staffList')
        unavailability_list = data.get('unavailabilityList')
        weekly_needs = data.get('weeklyNeeds')
        # Check if required fields exist and have the correct basic type
        if not isinstance(staff_list, list) or \
           not isinstance(unavailability_list, list) or \
           not isinstance(weekly_needs, dict):
             print("Error: Missing or invalid type for required data fields.")
             missing_or_invalid = []
             if not isinstance(staff_list, list): missing_or_invalid.append("staffList (must be an array)")
             if not isinstance(unavailability_list, list): missing_or_invalid.append("unavailabilityList (must be an array)")
             if not isinstance(weekly_needs, dict): missing_or_invalid.append("weeklyNeeds (must be an object)")
             return jsonify({"success": False, "message": f"Missing or invalid type for fields: {', '.join(missing_or_invalid)}"}), 400
        print(f"Received staff: {len(staff_list)}, unavailability: {len(unavailability_list)}, needs days: {len(weekly_needs)}")
        # Add more specific data validation within each list/dict if necessary

    except Exception as e:
        print(f"Error parsing request JSON: {e}")
        traceback.print_exc() # Print detailed error to backend console
        return jsonify({"success": False, "message": "Error parsing request data."}), 400

    # --- Call Scheduling Logic ---
    try:
        print("Calling generate_schedule_with_ortools (V4.1)...")
        # Call the imported function
        schedule_result, warnings_list, calculation_time = generate_schedule_with_ortools(
            weekly_needs, staff_list, unavailability_list
        )
        print(f"generate_schedule_with_ortools (V4.1) returned. Success: {schedule_result is not None}")

        # --- Handle Solver Results ---
        # Case 1: Solver found a solution (OPTIMAL or FEASIBLE)
        if schedule_result is not None:
            print(f"Scheduling logic completed in {calculation_time} ms.")
            # Return success with the schedule (might be empty) and any warnings
            return jsonify({
                "success": True,
                "schedule": schedule_result,
                "warnings": warnings_list if warnings_list else [], # Ensure it's always a list
                "calculationTimeMs": calculation_time
            }), 200 # HTTP 200 OK

        # Case 2: Solver failed (INFEASIBLE, MODEL_INVALID, UNKNOWN, etc.)
        else:
            print("Scheduling logic failed to find a solution (returned None).")
            # Return failure status, include warnings which might explain why
            return jsonify({
                "success": False,
                "message": "Could not find a schedule satisfying all constraints or model is invalid.",
                "warnings": warnings_list if warnings_list else []
            }), 422 # HTTP 422 Unprocessable Entity - Request ok, but cannot process due to constraints

    except Exception as schedule_error:
        # Catch any unexpected errors during the scheduling call itself
        print(f"!!! Error during OR-Tools V4.1 scheduling execution: {schedule_error} !!!")
        traceback.print_exc()
        # Return a generic server error
        return jsonify({"success": False, "message": "An internal error occurred during schedule calculation."}), 500


# --- Run Server ---
if __name__ == '__main__':
    print("Script is being run directly, starting Flask development server...")
    # Use port 5001 to avoid common conflicts
    # debug=True enables auto-reloading and detailed error pages (disable in production)
    # host='0.0.0.0' makes the server accessible on your local network
    app.run(host='0.0.0.0', port=5001, debug=True)