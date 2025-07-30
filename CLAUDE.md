# Restaurant Schedule Backend - AI Project Context

Flask REST API for restaurant staff scheduling optimization using Google OR-Tools constraint programming with comprehensive testing validation.

## Tech Stack
- **Flask 3.1.0** - Web framework with single POST endpoint `/api/schedule`
- **Google OR-Tools 9.12.4544** - CP-SAT solver for constraint satisfaction
- **Flask-CORS 5.0.1** - Cross-origin support for frontend integration
- **Gunicorn 21.2.0** - Production WSGI server
- **pytest 8.3.4** - Testing framework with comprehensive coverage
- **AWS Elastic Beanstalk** - Deployment target

## Project Structure
```
application.py          # Flask app entry point & API endpoint
scheduler/
  ├── solver.py        # OR-Tools constraint programming engine  
  ├── utils.py         # Time calculations & validation utilities
  └── constants.py     # Business constants (days, shifts, roles)
tests/                  # Comprehensive testing framework (44 tests)
  ├── conftest.py      # Shared test configuration & fixtures
  ├── fixtures/
  │   └── test_data.py # Simplified realistic test scenarios
  ├── test_api.py      # API endpoints, validation, CORS, error handling
  └── test_core_business.py # Business logic & optimization objectives
requirements.txt       # Python dependencies
Procfile              # AWS Elastic Beanstalk configuration
```

## Core Concepts

### Business Domain
- **Shifts**: HALF_DAY_AM (12:00-19:00), HALF_DAY_PM (19:00-02:00) - 7 hours each
- **Roles**: Server, Cashier, Expo (dynamically detected from input)
- **Schedule**: Weekly (Monday-Sunday) staff assignments with cross-day support
- **Constraints**: Staff availability, min/max hours, role qualifications, no double-booking
- **Shift Preferences**: PRIORITIZE_FULL_DAYS, PRIORITIZE_HALF_DAYS, NONE

### Constraint Programming Model
- **Decision Variables**: Boolean assignments (staff, day, shift, role)
- **Hard Constraints**: Availability (strict), max hours, single role per shift, role qualifications
- **5-Level Optimization Hierarchy** (validated through comprehensive testing):
  1. **Demand Shortage Minimization** (weight: 10,000) - Highest priority
  2. **Min Hour Shortage Minimization** (weight: 2,000) - Staff satisfaction
  3. **Shift Preference Optimization** (weight: 100) - Full vs half days
  4. **Staff Priority Optimization** (weight: 20) - Management preferences
  5. **Role Preference Optimization** (weight: 10) - Individual preferences
- **Solver**: CP-SAT with 180-second timeout, handles infeasible scenarios gracefully
- **Precision**: Hours stored as tenths (multiply by 10) for integer constraint variables
- **Cross-day Time Handling**: PM shifts ending after midnight (19:00-02:00)

### API Pattern
- **Single endpoint**: `POST /api/schedule`
- **Input validation**: Multi-layer (JSON → types → business rules → constraints)
- **Output structure**: Schedule assignments, warnings array, calculation time in ms
- **Error handling**: 400 (validation), 422 (infeasible), 500 (internal) with descriptive messages
- **Required fields**: staffList, unavailabilityList, weeklyNeeds, shiftDefinitions
- **CORS configuration**: Specific origin allowlist for production security

## Testing Framework

### Comprehensive Test Suite (44 tests in 4 files)
- **test_api.py** (20 tests): API endpoints, validation, CORS, error handling
- **test_core_business.py** (24 tests): Business logic, optimization objectives, constraints
- **conftest.py**: Shared fixtures and test configuration
- **fixtures/test_data.py**: Realistic test scenarios with minimal complexity

### Test Coverage
- **API Endpoints**: Health check, schedule generation, validation, CORS headers
- **Input Validation**: Missing fields, invalid JSON, malformed data, edge cases
- **Business Rules**: No double-booking, max hours, role qualifications, unavailability
- **Optimization Objectives**: All 5 levels of optimization hierarchy validation
- **Constraint Scenarios**: Understaffed, overstaffed, high constraints, infeasible cases
- **Performance Validation**: Execution time bounds and consistency
- **Error Handling**: Graceful failure modes and descriptive error messages

### Test Data Patterns
```python
# Minimal staff set covering all constraint types
MINIMAL_STAFF = [
    {"name": "Manager Alice", "assignedRolesInPriority": ["Server", "Cashier", "Expo"]},  # Multi-role
    {"name": "Server Bob", "assignedRolesInPriority": ["Server"]},  # Single role
    {"name": "Cashier Carol", "assignedRolesInPriority": ["Cashier", "Server"]},  # Role preference
    {"name": "Expo Dave", "assignedRolesInPriority": ["Expo", "Server"]},  # Critical role
    {"name": "Part-time Eve", "assignedRolesInPriority": ["Server", "Cashier"]}  # Low hours
]
```

### Performance Benchmarks (Validated by Testing)
- **Basic scenarios**: <10 seconds (typical: 1-3 seconds)
- **Understaffed scenarios**: <30 seconds
- **High constraint scenarios**: <60 seconds
- **Large requests** (15+ staff): <60 seconds
- **Memory usage**: ~20-40MB per process during solving
- **CPU usage**: High during solving (expected for constraint programming)

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

# Testing
pytest tests/ -v                    # Run all tests with verbose output
pytest tests/test_api.py -v         # Run API tests only
pytest tests/test_core_business.py -v  # Run business logic tests only

# AWS deployment
eb init -p python-3.8 restaurant-schedule-backend
eb create dev-env
eb deploy
```

## Quality Standards & Validation

### Testing Validation (Automated)
- **Business Rule Enforcement**: No double-booking, role qualifications, max hours
- **Optimization Hierarchy**: All 5 levels validated with weight priorities
- **Constraint Satisfaction**: Unavailability, staff limits, time boundaries
- **API Compliance**: CORS, validation, error handling, response structure
- **Performance Bounds**: Execution time limits for different scenario complexities
- **Error Handling**: Graceful degradation and descriptive error messages

### Code Quality Patterns (Validated by Testing)
- **Validation layers**: JSON structure → data types → business rules → constraints
- **Error handling**: Comprehensive try-catch with contextual error messages
- **Time precision**: Cross-day calculations with minute-level accuracy
- **Constraint naming**: Descriptive variable names for debugging
- **Result processing**: Clean empty structures, validate constraint satisfaction

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
- **Testing coverage**: 44 tests covering all functionality, simplified for 8.35s runtime
- **CPU usage**: High during constraint solving is expected and normal

## Testing & Debugging
- **Comprehensive testing**: Run `pytest tests/ -v` for full validation (44 tests)
- **API testing**: Use test scenarios from `tests/fixtures/test_data.py`
- **Constraint debugging**: Check console logs for OR-Tools constraint violations
- **Performance monitoring**: Watch `calculationTimeMs` in responses
- **Validation errors**: HTTP 400 with specific field error messages
- **Infeasibility**: HTTP 422 when constraints cannot be satisfied
- **Test data**: Realistic scenarios covering all constraint types and edge cases