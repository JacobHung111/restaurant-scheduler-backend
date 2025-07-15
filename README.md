# Restaurant Staff Scheduling Backend

This Flask-based backend provides a powerful and flexible solution for generating weekly staff schedules for a restaurant. It uses Google's OR-Tools to solve the complex scheduling problem as a Constraint Satisfaction Problem (CSP), balancing operational needs with staff preferences and availability.

The application is designed to be deployed on AWS Elastic Beanstalk and serves a corresponding frontend application.

## Key Features

- **Automated Schedule Generation:** Creates optimized weekly schedules based on defined needs.
- **Constraint-Based Solving:** Utilizes Google OR-Tools to handle various constraints, including:
  - Staff availability and unavailability.
  - Minimum and maximum weekly work hours per staff member.
  - Required number of staff for different roles, shifts, and days.
- **Prioritization & Preferences:**
  - **Staff Priority:** Allows prioritizing certain staff members to be assigned more hours.
  - **Role Priority:** Assigns staff to their most proficient roles first.
  - **Shift Preference:** Can be configured to prioritize giving staff full-day shifts or half-day shifts.
- **Dynamic Configuration:** Shift times, roles, and weekly needs can be fully configured via the API on each request.
- **Warning System:** Returns warnings for any shortages or rule violations (e.g., a staff member being scheduled for fewer than their minimum hours).
- **Performance Metrics:** Reports the time taken for the schedule calculation.

## Technologies Used

- **Backend:** Python, Flask
- **Scheduling Engine:** Google OR-Tools
- **Deployment:** Gunicorn, AWS Elastic Beanstalk
- **Core Libraries:**
  - `Flask`: For the web framework and API endpoints.
  - `Flask-Cors`: To handle Cross-Origin Resource Sharing (CORS).
  - `ortools`: For the core constraint satisfaction programming.
  - `gunicorn`: As the production WSGI server.

## API Endpoint

### `POST /api/schedule`

This is the primary endpoint for generating a schedule.

**Request Body:**

The request body must be a JSON object with the following structure:

```json
{
  "staffList": [
    {
      "id": "staff1",
      "name": "Alice",
      "minHoursPerWeek": 10,
      "maxHoursPerWeek": 20,
      "assignedRolesInPriority": ["Server", "Cashier"]
    }
  ],
  "unavailabilityList": [
    {
      "employeeId": "staff1",
      "dayOfWeek": "Monday",
      "shifts": [{ "start": "00:00", "end": "23:59" }]
    }
  ],
  "weeklyNeeds": {
    "Monday": {
      "HALF_DAY_AM": { "Server": 2, "Cashier": 1 },
      "HALF_DAY_PM": { "Server": 2, "Cashier": 1 }
    }
  },
  "shiftDefinitions": {
    "HALF_DAY_AM": { "start": "11:00", "end": "16:00", "hours": 5.0 },
    "HALF_DAY_PM": { "start": "16:00", "end": "21:00", "hours": 5.0 }
  },
  "shiftPreference": "PRIORITIZE_FULL_DAYS", // or "PRIORITIZE_HALF_DAYS", "NONE"
  "staffPriority": ["staff1"] // List of staff IDs in order of priority
}
```

**Success Response (200 OK):**

```json
{
  "success": true,
  "schedule": {
    "Monday": {
      "HALF_DAY_AM": {
        "Server": ["staff1", "staff2"]
      }
    }
  },
  "warnings": [
    "Warning: Staff Bob scheduled for 8h, below minimum 10h."
  ],
  "calculationTimeMs": 520
}
```

**Error Responses:**

- **400 Bad Request:** If the request body is missing, not valid JSON, or contains invalid data types.
- **422 Unprocessable Entity:** If a valid schedule cannot be generated from the provided data.
- **500 Internal Server Error:** If an unexpected error occurs during the scheduling process.

## Setup and Deployment on AWS Elastic Beanstalk

This application is configured for deployment on AWS Elastic Beanstalk with a Python environment.

### 1. Prerequisites

- An AWS account.
- The AWS EB CLI installed and configured.

### 2. Project Structure

The repository contains the necessary files for deployment:

- `application.py`: The Flask application entry point.
- `requirements.txt`: A list of all Python dependencies.
- `Procfile`: Specifies the command to run the application on the server (`web: gunicorn ...`).
- `.elasticbeanstalk/`: Directory for Elastic Beanstalk environment configuration (managed by the EB CLI).

### 3. Deployment Steps

1.  **Initialize the EB Application:**
    If you haven't already, initialize an Elastic Beanstalk application in the project root.
    ```bash
    eb init -p python-3.8 restaurant-schedule-backend --region your-aws-region
    ```

2.  **Create an Environment:**
    Create a new environment to host the application.
    ```bash
    eb create dev-env
    ```

3.  **Deploy Changes:**
    After making changes to the code, deploy them using the EB CLI:
    ```bash
    eb deploy
    ```

The EB CLI will automatically package the application, upload it to Elastic Beanstalk, and provision the necessary resources. The `Procfile` tells Elastic Beanstalk to use `gunicorn` to serve the Flask application, which is more robust for production than the standard Flask development server.