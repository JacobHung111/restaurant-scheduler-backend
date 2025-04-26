# Restaurant Schedule Generator Backend

This project provides a backend service built with Python, Flask, and Google OR-Tools to generate weekly staff schedules. It handles fixed constraints and allows configuration of optimization priorities via API parameters.

## Features

- **Automated Scheduling:** Uses Google OR-Tools CP-SAT solver to find optimal or feasible schedules satisfying constraints and optimizing goals.
- **Fixed Hard Constraints:** The solver _must_ satisfy these conditions:
  - **Staff Availability:** Respects defined unavailability periods.
  - **Max Weekly Hours:** Employees do not exceed their maximum weekly hour limit.
  - **Role Qualification:** Employees are only assigned roles they are qualified for.
  - **Single Role per Shift:** An employee works at most one role during any given shift block (11:00-16:00 or 16:00-21:00).
- **Optimization Goals / Soft Constraints (Prioritized):** The solver _tries its best_ to achieve these, respecting priorities:
  1.  **(Highest Priority) Minimize Demand Shortage:** Tries to fulfill the `weeklyNeeds` as closely as possible. Allows generating schedules even when short-staffed, reporting the specific shortages.
  2.  **(Medium Priority) Minimize Minimum Weekly Hours Shortage:** Tries to ensure employees who are scheduled meet their `minHoursPerWeek` target. Reports warnings if unmet.
  3.  **(Configurable) Shift Preference:** Allows prioritizing full-day shifts, half-day shifts, or having no shift length preference.
  4.  **(Configurable) Staff Priority:** Allows prioritizing scheduling certain employees based on an ordered list.
- **API Endpoint:** Provides a `/api/schedule` endpoint to receive scheduling requests (including optimization preferences) and return results via JSON.
- **Data Management:** Assumes data (staff, unavailability, needs) is provided via the API request. Includes frontend functionality (in the separate React project) for importing/exporting this data as JSON files.

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
│   └── solver.py      # Contains the OR-Tools scheduling function (generate_schedule_with_ortools)
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

1.  **Ensure the virtual environment is activated.** (`(venv)` should be visible in the terminal prompt).
2.  **Run the Flask application:**
    ```bash
    python app.py
    ```
3.  The server will start, typically listening on `http://127.0.0.1:5001` (or `http://0.0.0.0:5001`). Check the console output for the exact address. `debug=True` enables auto-reloading.

## API Usage

### Endpoint: `/api/schedule`

- **Method:** `POST`
- **Content-Type:** `application/json`
- **Request Body:** A JSON object containing:

  - `staffList`: (Array) List of staff objects (See `StaffMember` interface below).
  - `unavailabilityList`: (Array) List of unavailability objects (See `Unavailability` interface below).
  - `weeklyNeeds`: (Object) Defines staffing needs per day, shift, and role (See `WeeklyNeeds` structure below).
  - `shiftPreference`: (String, Optional) How to prioritize shift lengths. Defaults to `"PRIORITIZE_FULL_DAYS"`. Options:
    - `"PRIORITIZE_FULL_DAYS"`: Tries to assign the same person to both morning and evening shifts.
    - `"PRIORITIZE_HALF_DAYS"`: Tries to assign staff to only one shift per day if possible.
    - `"NONE"`: No specific preference for shift length.
  - `staffPriority`: (Array of Strings, Optional) An ordered list of employee IDs. Employees earlier in the list will be given higher priority when assigning shifts (lower priority goal). Defaults to `[]`.

- **Data Structures:**

  ```typescript // Using TypeScript interfaces for clarity
  interface StaffMember {
    id: string;
    name: string;
    roles: string[]; // e.g., ["Server", "Cashier", "Expo"]
    minHoursPerWeek?: number | null;
    maxHoursPerWeek?: number | null;
  }

  interface Unavailability {
    employeeId: string;
    dayOfWeek: string; // e.g., "Monday"
    shifts: { start: string; end: string }[]; // e.g., [{"start": "11:00", "end": "16:00"}]
  }

  interface WeeklyNeeds {
    // e.g., "Monday": { "11:00-16:00": { "Server": 1, "Cashier": 1 } }
    [day: string]: {
      [shift: string]: {
        [role: string]: number;
      };
    };
  }

  interface Schedule {
    // e.g., "Monday": { "11:00-16:00": { "Server": ["s1"], "Cashier": ["s3"] } }
    [day: string]: {
      [shift: string]: {
        [role: string]: string[]; // Array of assigned employee IDs
      };
    };
  }
  ```

- **Success Response (200 OK):**
  ```json
  {
    "success": true,
    "schedule": {
      /* Schedule object structure as above */
    },
    "calculationTimeMs": 150
  }
  ```
- **Failure Response (e.g., 422 Unprocessable Entity):** Returned if hard constraints conflict (infeasible) or the model is invalid.
  ```json
  {
    "success": false,
    "message": "Could not find a schedule satisfying all constraints or model is invalid."
  }
  ```
- **Client Error Response (e.g., 400 Bad Request):** Returned for invalid input data format.
  ```json
  {
    "success": false,
    "message": "Missing or invalid type for fields: staffList (must be an array)"
  }
  ```

## Future Improvements / TODOs

- Implement more sophisticated optimization goals (e.g., workload balancing).
- Add more granular hard/soft constraint configuration if needed.
- Add constraints for consecutive work days, minimum rest time, etc.
- Improve data validation on API requests.
- Add persistent data storage (database).
- Implement user authentication/authorization.
- Consider asynchronous task processing for potentially long calculations.
- Add unit and integration tests for the solver logic.
