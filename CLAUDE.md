# Restaurant Schedule Backend - Project Context

Flask REST API for restaurant staff scheduling optimization using Google OR-Tools constraint programming.

## Tech Stack
- **Flask 3.1.0** - Web framework with single POST endpoint `/api/schedule`
- **Google OR-Tools 9.12.4544** - CP-SAT solver for constraint satisfaction
- **Flask-CORS 5.0.1** - Cross-origin support for frontend integration
- **Gunicorn 21.2.0** - Production WSGI server
- **AWS Elastic Beanstalk** - Deployment target

## Project Structure
```
application.py          # Flask app entry point & API endpoint
scheduler/
  ├── solver.py        # OR-Tools constraint programming engine  
  ├── utils.py         # Time calculations & validation utilities
  └── constants.py     # Business constants (days, shifts, roles)
requirements.txt       # Python dependencies
Procfile              # AWS Elastic Beanstalk configuration
```

## Core Concepts

### Business Domain
- **Shifts**: HALF_DAY_AM (11:00-16:00), HALF_DAY_PM (16:00-21:00)
- **Roles**: Server, Cashier, Expo (defined in `constants.py`)
- **Schedule**: Weekly (Monday-Sunday) staff assignments
- **Constraints**: Staff availability, min/max hours, role preferences
- **Shift Preferences**: PRIORITIZE_FULL_DAYS, PRIORITIZE_HALF_DAYS, NONE

### Constraint Programming Model
- **Decision Variables**: Boolean assignments (staff, day, shift, role)
- **Hard Constraints**: Availability, max hours, single role per shift
- **Optimization Weights**: Demand shortage (10,000) > min hour shortage (2,000) > shift preference (100) > staff priority (20) > role preference (10)
- **Solver**: CP-SAT with 180-second timeout, handles infeasible scenarios
- **Precision**: Hours stored as tenths (multiply by 10) for integer variables

### API Pattern
- Single endpoint: `POST /api/schedule`
- Input: Staff list, availability, weekly needs, shift definitions, preferences
- Output: Schedule assignments, warnings array, calculation time in ms
- Error handling: 400 (validation), 422 (infeasible), 500 (internal)
- **Required fields**: staffList, unavailabilityList, weeklyNeeds, shiftDefinitions

## Development Guidelines

### Code Patterns
- **Validation**: Multi-layer (JSON → types → business rules → constraints)
- **Error handling**: Try-catch with descriptive messages, print to console
- **Time format**: "HH:MM" strings, convert to minutes with `time_to_minutes()`
- **Logging**: Extensive console logging for debugging constraint programming
- **Data structures**: Use dictionaries with tuple keys for CP variables

### Flask Conventions
- **CORS**: Specific origin allowlist (no wildcards in production)
- **Health check**: Simple `/` endpoint returning `{"status": "ok"}`
- **JSON responses**: Consistent error format with HTTP status codes
- **Request processing**: JSON-only API with comprehensive validation
- **App name**: Use `application` variable (AWS EB requirement)

### OR-Tools Conventions
- **Variable naming**: Descriptive with context (e.g., `assign_staff1_Monday_AM_Server`)
- **Constraint grouping**: Hard constraints first, then optimization objectives
- **Result processing**: Clean up empty schedule structures with nested loops
- **Performance**: Monitor `calculationTimeMs` for optimization time
- **Status handling**: Check OPTIMAL or FEASIBLE before processing results

## Key Files

### `application.py`
- Flask app with CORS configuration for specific origins
- Single POST endpoint with comprehensive input validation
- Health check endpoint for monitoring

### `scheduler/solver.py`
- 490-line constraint programming implementation
- Dynamic role/staff detection from input
- Multi-objective optimization with configurable weights
- Post-processing with warning generation

### `scheduler/utils.py` & `constants.py`
- Time parsing, validation, and calculation utilities
- Business domain constants and default configurations
- Helper functions for schedule analysis

## Development Commands
```bash
# Local development
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python application.py

# AWS deployment
eb init -p python-3.8 restaurant-schedule-backend
eb create dev-env
eb deploy
```

## Important Notes & Constraints
- **Stateless API**: No database persistence, all data in request
- **Single-threaded**: OR-Tools solver is CPU-intensive, avoid concurrent requests
- **CORS origins**: `restaurant-scheduler.jacobhung.dpdns.org`, `restaurant-scheduler-web.vercel.app`
- **Solver timeout**: 180 seconds maximum (`solver.parameters.max_time_in_seconds`)
- **Error scenarios**: Infeasible problems return HTTP 422 with explanation
- **Memory precision**: Hours multiplied by 10 for integer constraint variables
- **Time validation**: All times must be valid "HH:MM" format with proper ranges
- **Role dynamics**: Active roles detected from input data, not fixed constants
- **Shift consistency**: AM end time must equal PM start time for full-day logic
- **Variable naming**: Follow pattern `{purpose}_{staff}_{day}_{shift}_{role}`

## Testing & Debugging
- **Local test**: Use curl with JSON payload to test `/api/schedule`
- **Constraint debugging**: Check console logs for OR-Tools constraint violations
- **Performance monitoring**: Watch `calculationTimeMs` in responses
- **Validation errors**: HTTP 400 with specific field error messages
- **Infeasibility**: HTTP 422 when constraints cannot be satisfied