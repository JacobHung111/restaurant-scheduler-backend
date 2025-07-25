# application.py
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from scheduler.solver import generate_schedule_with_ortools
from scheduler.utils import validate_shift_definitions

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)
logger = logging.getLogger(__name__)

# --- Flask application Setup ---
application = Flask(__name__)

# Security and performance configuration
application.config.update(
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max request size
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

CORS(
    application,
    origins=[
        "https://restaurant-scheduler.jacobhung.dpdns.org",
        "https://restaurant-scheduler-web.vercel.app/",
        "http://localhost:5173",  # Local development
        "http://127.0.0.1:5173",  # Local development (alternative)
        "http://localhost:3000",  # Common frontend port
        "http://127.0.0.1:3000",  # Common frontend port (alternative)
    ],
)
logger.info("Flask application instance created and CORS enabled.")


# --- Security Headers Middleware ---
@application.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Production environment only
    # if not application.debug:
    #     response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    #     response.headers['Content-Security-Policy'] = "default-src 'self'"

    return response


# --- Global Error Handlers ---
@application.errorhandler(HTTPException)
def handle_http_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    return (
        jsonify(
            {
                "success": False,
                "error": e.name,
                "message": e.description,
                "code": e.code,
            }
        ),
        e.code,
    )


@application.errorhandler(Exception)
def handle_generic_exception(e):
    """Handle unexpected exceptions."""
    if isinstance(e, HTTPException):
        return e

    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    return (
        jsonify(
            {
                "success": False,
                "error": "Internal Server Error",
                "message": "An unexpected error occurred.",
            }
        ),
        500,
    )


@application.route("/")
def health_check():
    return jsonify({"status": "ok", "service": "restaurant-schedule-backend"}), 200


# --- API Endpoint ---
@application.route("/api/schedule", methods=["POST"])
def handle_schedule_request():
    request_id = id(request)
    logger.info(f"[{request_id}] Received schedule request from {request.remote_addr}")
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

        logger.info(
            f"[{request_id}] Validated input - Staff: {len(staff_list)}, "
            f"Unavailability: {len(unavailability_list)}, Needs days: {len(weekly_needs)}, "
            f"Shift preference: {shift_preference}, Staff priority: {len(staff_priority_list)}"
        )

    except Exception as e:
        logger.error(f"[{request_id}] Error parsing request JSON: {e}", exc_info=True)
        return (
            jsonify({"success": False, "message": "Error parsing request data."}),
            400,
        )

    # --- Call Scheduling Logic ---
    try:
        logger.info(f"[{request_id}] Starting OR-Tools scheduling...")
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
        logger.info(
            f"[{request_id}] OR-Tools completed in {calculation_time}ms. "
            f"Success: {schedule_result is not None}, Warnings: {len(warnings_list or [])}"
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
        logger.error(
            f"[{request_id}] OR-Tools scheduling error: {schedule_error}", exc_info=True
        )
        return (
            jsonify(
                {
                    "success": False,
                    "message": "An internal error occurred during schedule calculation.",
                }
            ),
            500,
        )


# --- Application Entry Point ---
if __name__ == "__main__":
    logger.info("Starting Flask development server...")
    application.run(debug=True, host="0.0.0.0", port=5000)
