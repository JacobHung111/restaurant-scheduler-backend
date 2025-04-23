# Restaurant Schedule Generator Backend

This project provides a backend service built with Python, Flask, and Google OR-Tools to generate weekly staff schedules based on defined needs, staff availability, and various constraints. It prioritizes creating full-day shifts while minimizing unmet needs.

## Features

- **Automated Scheduling:** Uses Google OR-Tools CP-SAT solver to find optimal or feasible schedules.
- **Constraint Handling:** Considers:
  - Weekly staff needs per shift and role.
  - Staff availability (unavailability periods).
  - Maximum weekly work hours per employee.
  - Staff role qualifications.
  - Ensures an employee works at most one role per shift.
- **Optimization:**
  - **Soft Demand:** Treats meeting exact demand as a high-priority goal rather than a hard constraint, allowing schedule generation even when short-staffed (reports shortages).
  - **Full-Day Preference:** Maximizes the number of full-day shifts (consecutive morning and evening shifts) assigned to the same employee for the same role.
- **API Endpoint:** Provides a `/api/schedule` endpoint to receive scheduling requests and return results via JSON.
- **Data Management:** Includes API functionality (though not implemented in the backend itself, expected via frontend interaction or separate scripts) to import/export:
  - Staff List (`staff_list.json`)
  - Unavailability Records (`unavailability_list.json`)
  - Weekly Needs (`weekly_needs.json`)

## Technology Stack

- **Backend:** Python 3.7+
- **Framework:** Flask
- **CORS Handling:** Flask-CORS
- **Scheduling Solver:** Google OR-Tools (CP-SAT)

## Project Structure

```
schedule_backend/
├── venv/              # Virtual environment folder
├── app.py             # Main Flask application (routing, API handling)
├── requirements.txt   # Python dependencies
├── scheduler/         # Core scheduling logic package
│   ├── __init__.py    # Marks scheduler as a Python package
│   ├── constants.py   # Defines constants (DAYS_OF_WEEK, SHIFTS, ALL_ROLES)
│   ├── utils.py       # Helper functions (time conversion, hour calculation, etc.)
│   └── solver.py      # Contains the OR-Tools scheduling function
└── README.md          # This file
```

## Setup and Installation

1.  **Clone the repository (if applicable):**

    ```bash
    git clone https://github.com/JacobHung111/restaurant-scheduler-backend.git
    cd schedule_backend
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    _(If `requirements.txt` doesn't exist yet, run `pip install Flask Flask-Cors ortools` first, then `pip freeze > requirements.txt`)_

## Running the Development Server

1.  **Ensure the virtual environment is activated.**
2.  **Run the Flask application:**
    ```bash
    python app.py
    ```
3.  The server will start, typically listening on `http://127.0.0.1:5001` (or `http://0.0.0.0:5001`). Check the console output for the exact address. The `debug=True` flag enables auto-reloading on code changes.

## API Usage

### Endpoint: `/api/schedule`

- **Method:** `POST`
- **Content-Type:** `application/json`
- **Request Body:** A JSON object containing the following keys:

  - `staffList`: (Array of Objects) List of staff members. Each object should have:
    - `id`: (String) Unique identifier (auto-generated if added via a potential frontend).
    - `name`: (String) Employee's name.
    - `roles`: (Array of Strings) List of roles the employee can perform (e.g., `["Server", "Cashier"]`). Must match roles in `scheduler.constants.ALL_ROLES`.
    - `minHoursPerWeek`: (Number, optional) Minimum weekly hours target.
    - `maxHoursPerWeek`: (Number, optional) Maximum weekly hours constraint.
  - `unavailabilityList`: (Array of Objects) List of unavailability records. Each object should have:
    - `employeeId`: (String) The ID of the staff member.
    - `dayOfWeek`: (String) The day of the week (e.g., `"Monday"`). Must match days in `scheduler.constants.DAYS_OF_WEEK`.
    - `shifts`: (Array of Objects) List of unavailable time slots for that day. Each object should have:
      - `start`: (String) Start time in "HH:MM" format.
      - `end`: (String) End time in "HH:MM" format (use "23:59" for end of day if needed).
  - `weeklyNeeds`: (Object) Defines staffing needs. Keys are days of the week (e.g., `"Monday"`). Values are objects where keys are shift keys (e.g., `"11:00-16:00"`) and values are objects defining role counts (e.g., `{"Server": 2, "Cashier": 1}`). Needs are only required for shifts/roles that need staff.

- **Success Response (200 OK):**
  ```json
  {
    "success": true,
    "schedule": {
      "Monday": {
        "11:00-16:00": {
          "Server": ["S123", "S456"],
          "Cashier": ["S789"]
        }
        // ... other shifts/days ...
      }
    },
    "warnings": [
      "Warning: Shortage of 1 for Server on Tuesday 16:00-21:00.",
      "Warning: Staff Alice total weekly hours 8.0h is below minimum 10h."
    ],
    "calculationTimeMs": 150
  }
  ```
- **Failure Response (e.g., 422 Unprocessable Entity for INFEASIBLE):**
  ```json
  {
    "success": false,
    "message": "Could not find a schedule satisfying all constraints or model is invalid.",
    "warnings": [
      "Error: Could not satisfy hard constraints (check unavailability, max hours)."
    ]
  }
  ```
- **Client Error Response (e.g., 400 Bad Request):**
  ```json
  {
      "success": False,
      "message": "Missing or invalid type for fields: staffList (must be an array)"
  }
  ```

## Future Improvements / TODOs

- Add constraints for consecutive work days, minimum rest time, etc.
- Add persistent data storage (e.g., a database) instead of relying solely on request data.
- Implement user authentication/authorization if needed.
- Consider asynchronous task processing for very long scheduling calculations.
- Refine the role assignment logic in the results processing if edge cases arise.
