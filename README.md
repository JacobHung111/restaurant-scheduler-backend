# Restaurant Schedule Generator Backend

A production-ready Flask REST API for restaurant staff scheduling optimization using Google OR-Tools constraint programming, featuring comprehensive testing validation and performance benchmarks.

## Features

- **Advanced Constraint Programming:** Uses Google OR-Tools CP-SAT solver with 5-level optimization hierarchy
- **Fixed Hard Constraints:** The solver _must_ satisfy these conditions:
  - **Staff Availability:** Respects unavailability periods including cross-day shifts
  - **Max Weekly Hours:** Employees never exceed their maximum weekly hour limit
  - **Role Qualification:** Staff only assigned to roles they're qualified for
  - **No Double Booking:** Single role per shift per employee
- **5-Level Optimization Hierarchy:** Prioritized optimization objectives (validated through comprehensive testing):
  1. **Demand Shortage Minimization** (weight: 10,000) - Fulfill staffing needs first
  2. **Min Hour Shortage Minimization** (weight: 2,000) - Meet staff minimum hour requirements
  3. **Shift Preference Optimization** (weight: 100) - Full-day vs half-day preferences
  4. **Staff Priority Optimization** (weight: 20) - Prioritize specific staff members
  5. **Role Preference Optimization** (weight: 10) - Assign preferred roles when possible
- **Comprehensive Testing:** 44 tests covering all business logic, API validation, and performance bounds
- **Performance Validated:** Real benchmarks from testing (basic scenarios <10s, complex <60s)
- **Production Ready:** CORS configuration, error handling, health monitoring, AWS deployment ready

## Technology Stack

- **Python 3.8+** - Core runtime environment
- **Flask 3.1.0** - Web framework with single POST endpoint
- **Google OR-Tools 9.12.4544** - CP-SAT constraint programming solver
- **Flask-CORS 5.0.1** - Cross-origin resource sharing support
- **Gunicorn 21.2.0** - Production WSGI server
- **pytest 7.4.3** - Testing framework with 44 comprehensive tests
- **psutil** - System monitoring for performance testing
- **AWS Elastic Beanstalk** - Cloud deployment platform

## Project Structure

```
restaurant_schedule_backend/
├── application.py          # Flask app entry point & API endpoint
├── scheduler/              # Core scheduling logic package
│   ├── solver.py          # OR-Tools constraint programming engine (490 lines)
│   ├── utils.py           # Time calculations & validation utilities
│   └── constants.py       # Business constants (days, shifts, roles)
├── tests/                 # Comprehensive test suite (44 tests in 4 files)
│   ├── conftest.py       # Shared test configuration and fixtures
│   ├── fixtures/
│   │   └── test_data.py  # Simplified realistic test data
│   ├── test_api.py       # API endpoints, validation, CORS (20 tests)
│   └── test_core_business.py # Business logic, optimization (24 tests)
├── requirements.txt       # Python dependencies
├── Procfile              # AWS Elastic Beanstalk configuration
├── CLAUDE.md             # AI context documentation
└── README.md             # User/developer documentation (this file)
```

## Quick Start

### Installation

1. **Clone and setup environment:**
   ```bash
   git clone <repository-url>
   cd restaurant_schedule_backend
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run development server:**
   ```bash
   python application.py
   ```
   Server starts at `http://127.0.0.1:5000` with auto-reload enabled.

### Testing

Run the comprehensive test suite (44 tests in ~8.35 seconds):
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_api.py              # API validation tests
pytest tests/test_core_business.py    # Business logic tests

# Verbose output with detailed results
pytest -v

# Quick summary with short traceback
pytest --tb=short
```

## API Documentation

### Health Check: `GET /`
Simple health monitoring endpoint:
```json
{
  "status": "ok"
}
```

### Schedule Generation: `POST /api/schedule`

**Request Format:**
- **Content-Type:** `application/json`
- **Required Fields:** `staffList`, `unavailabilityList`, `weeklyNeeds`, `shiftDefinitions`
- **Optional Fields:** `shiftPreference` (default: "PRIORITIZE_FULL_DAYS"), `staffPriority` (default: [])

**Data Structures:**
```typescript
interface StaffMember {
  id: string;
  name: string;
  assignedRolesInPriority: string[]; // e.g., ["Server", "Cashier", "Expo"]
  minHoursPerWeek: number;
  maxHoursPerWeek: number;
}

interface Unavailability {
  employeeId: string;
  dayOfWeek: string; // "Monday", "Tuesday", etc.
  shifts: { start: string; end: string }[]; // HH:MM format, supports cross-day
}

interface WeeklyNeeds {
  [day: string]: {
    [shift: string]: {
      [role: string]: number; // Number of staff needed
    };
  };
}

interface ShiftDefinitions {
  [shiftName: string]: {
    start: string; // HH:MM format
    end: string;   // HH:MM format (can be next day)
    hours: number; // Total hours for the shift
  };
}
```

**Example Request:**
```json
{
  "staffList": [
    {
      "id": "alice-mgr-001",
      "name": "Manager Alice",
      "assignedRolesInPriority": ["Server", "Cashier", "Expo"],
      "minHoursPerWeek": 30,
      "maxHoursPerWeek": 40
    }
  ],
  "unavailabilityList": [
    {
      "employeeId": "alice-mgr-001",
      "dayOfWeek": "Sunday",
      "shifts": [{"start": "00:00", "end": "23:59"}]
    }
  ],
  "weeklyNeeds": {
    "Monday": {
      "HALF_DAY_AM": {"Server": 1, "Cashier": 1},
      "HALF_DAY_PM": {"Server": 2, "Cashier": 1, "Expo": 1}
    }
  },
  "shiftDefinitions": {
    "HALF_DAY_AM": {"start": "12:00", "end": "19:00", "hours": 7},
    "HALF_DAY_PM": {"start": "19:00", "end": "02:00", "hours": 7}
  },
  "shiftPreference": "PRIORITIZE_FULL_DAYS",
  "staffPriority": ["alice-mgr-001", "bob-srv-002"]
}
```

**Response Formats:**

**Success (200 OK):**
```json
{
  "success": true,
  "schedule": {
    "Monday": {
      "HALF_DAY_AM": {
        "Server": ["alice-mgr-001"],
        "Cashier": ["bob-srv-002"]
      },
      "HALF_DAY_PM": {
        "Server": ["alice-mgr-001", "carol-srv-003"],
        "Cashier": ["bob-srv-002"],
        "Expo": ["dave-exp-004"]
      }
    }
  },
  "warnings": ["Shortage on Tuesday HALF_DAY_PM: Server (needed: 2, assigned: 1)"],
  "calculationTimeMs": 1247
}
```

**Validation Error (400 Bad Request):**
```json
{
  "success": false,
  "message": "Missing required field: staffList"
}
```

**Infeasible Constraints (422 Unprocessable Entity):**
```json
{
  "success": false,
  "message": "Could not find a feasible schedule. Check staff availability and constraints."
}
```

## Business Logic

### Shift System
- **HALF_DAY_AM**: 12:00-19:00 (7 hours)
- **HALF_DAY_PM**: 19:00-02:00 (7 hours, crosses midnight)
- **Full Day**: Staff working both AM and PM shifts (14 hours total)

### Optimization Priorities
The system uses a weighted optimization approach where higher weights take absolute priority:

1. **Demand Coverage (10,000)**: Fill required positions first
2. **Minimum Hours (2,000)**: Meet staff minimum hour requirements  
3. **Shift Preferences (100)**: Respect full-day vs half-day preferences
4. **Staff Priority (20)**: Prioritize preferred staff members
5. **Role Preferences (10)**: Assign preferred roles when possible

### Constraint Validation
- **Hard Constraints**: Never violated (availability, max hours, qualifications)
- **Soft Constraints**: Optimized based on weights and priorities
- **Warning System**: Reports when soft constraints cannot be fully satisfied

## Performance Benchmarks

Performance characteristics validated through comprehensive testing:

- **Basic Scenarios (5 staff, 1 week)**: 1-3 seconds typical, <10 seconds maximum
- **Understaffed Scenarios**: <30 seconds with automatic shortage detection
- **High Constraint Scenarios**: <60 seconds with complex unavailability patterns
- **Large Requests (15+ staff)**: <60 seconds for moderate complexity
- **CPU Usage**: Intensive during solving phase (inherent to constraint programming)
- **Memory Usage**: 20-40 MB per process (comparable to typical web applications)

### Performance Optimization
- **Solver Timeout**: 180-second maximum prevents runaway processes
- **Efficient Data Structures**: Optimized for OR-Tools constraint programming
- **Single-threaded Design**: Prevents resource conflicts in CPU-intensive operations
- **Stateless Architecture**: No database overhead, scales horizontally

## Development Workflow

### Code Quality Standards
- **Multi-layer Validation**: JSON → Types → Business Rules → Constraints
- **Comprehensive Error Handling**: Descriptive messages for all failure modes
- **Extensive Logging**: Console logging for debugging constraint programming
- **Type Safety**: Consistent data structures and validation
- **Testing Coverage**: 100% core logic coverage with realistic scenarios

### Development Commands
```bash
# Development server with auto-reload
python application.py

# Run full test suite (44 tests)
pytest

# Run specific test categories
pytest tests/test_api.py          # API validation
pytest tests/test_core_business.py # Business logic

# Verbose testing with detailed output
pytest -v

# Performance testing (monitor CPU usage)
pytest --tb=short
```

### Contributing Guidelines
1. **Write Tests First**: All new features must include comprehensive tests
2. **Follow Patterns**: Use existing validation and error handling patterns
3. **Performance Awareness**: Consider CPU usage impact of changes
4. **Realistic Testing**: Use business-realistic test scenarios, not artificial edge cases
5. **Documentation**: Update both CLAUDE.md (AI context) and README.md (user docs)

## Deployment

### AWS Elastic Beanstalk
Ready for deployment with included `Procfile`:
```bash
# Initialize deployment
eb init -p python-3.8 restaurant-schedule-backend

# Create environment
eb create dev-env

# Deploy updates
eb deploy
```

### Production Considerations
- **CORS Configuration**: Configured for specific allowed origins
- **Error Monitoring**: Comprehensive HTTP status codes and error messages
- **Health Monitoring**: `/` endpoint for load balancer health checks
- **Resource Limits**: 180-second solver timeout prevents resource exhaustion
- **Horizontal Scaling**: Stateless design supports multiple instances
- **Security**: Input validation and sanitization at all layers

### Environment Variables
- **FLASK_ENV**: Set to `production` for production deployments
- **CORS_ORIGINS**: Comma-separated list of allowed origins
- **MAX_SOLVE_TIME**: Override default 180-second solver timeout if needed

## Troubleshooting

### Common Issues
- **High CPU Usage**: Expected during constraint solving, typically 1-60 seconds
- **Timeout Errors**: Increase complexity handling or reduce request scope
- **Infeasible Schedules**: Review staff availability vs. demand requirements
- **CORS Errors**: Ensure client origin is in allowed origins list

### Debug Information
- **Calculation Time**: Returned in `calculationTimeMs` for performance monitoring
- **Warnings Array**: Non-blocking issues like staffing shortages
- **Console Logs**: Extensive logging for constraint programming debugging
- **HTTP Status Codes**: Specific codes for different error types (400, 422, 500)

### Performance Monitoring
- **Response Times**: Monitor `calculationTimeMs` in API responses
- **Resource Usage**: Track CPU and memory usage during peak usage
- **Error Rates**: Monitor 422 responses for constraint feasibility issues
- **Health Checks**: Use `/` endpoint for service monitoring
