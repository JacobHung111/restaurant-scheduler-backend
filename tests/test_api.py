"""
Comprehensive API tests for restaurant scheduling system.
Covers all HTTP endpoints, validation, error handling, and CORS.
"""
import pytest
import json
from fixtures.test_data import (
    get_basic_scenario,
    get_understaffed_scenario,
    INVALID_STAFF_EXAMPLES,
    INVALID_UNAVAILABILITY_EXAMPLES,
    INVALID_WEEKLY_NEEDS_EXAMPLES,
    STANDARD_SHIFT_DEFINITIONS
)


class TestAPIEndpoints:
    """Test core API endpoint functionality."""
    
    def test_health_check_endpoint(self, client):
        """Test health check endpoint returns OK."""
        response = client.get('/')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data == {"status": "ok", "service": "restaurant-schedule-backend"}
    
    def test_valid_schedule_request(self, client):
        """Test successful schedule generation."""
        scenario = get_basic_scenario()
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert 'schedule' in data
        assert 'calculationTimeMs' in data
        assert 'warnings' in data
        assert isinstance(data['schedule'], dict)
        assert data['calculationTimeMs'] > 0
    
    def test_schedule_structure_validation(self, client):
        """Test that returned schedule has correct structure."""
        scenario = get_basic_scenario()
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        schedule = data['schedule']
        
        # Check day structure
        expected_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day in expected_days:
            assert day in schedule
            
            # Check shift structure
            day_schedule = schedule[day]
            for shift_type in ["HALF_DAY_AM", "HALF_DAY_PM"]:
                if shift_type in day_schedule:
                    shift_schedule = day_schedule[shift_type]
                    
                    # Check role structure
                    for role, assigned_staff in shift_schedule.items():
                        assert isinstance(assigned_staff, list)
                        # Verify all assigned staff exist in staff list
                        staff_ids = [s["id"] for s in scenario["staffList"]]
                        for staff_id in assigned_staff:
                            assert staff_id in staff_ids
    
    def test_cors_headers(self, client):
        """Test CORS headers are set correctly."""
        scenario = get_basic_scenario()
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert 'Access-Control-Allow-Origin' in response.headers
        # Check that CORS allows expected origins
        cors_origin = response.headers.get('Access-Control-Allow-Origin')
        expected_origins = [
            'restaurant-scheduler.jacobhung.dpdns.org',
            'restaurant-scheduler-web.vercel.app'
        ]
        # Should allow at least one expected origin or wildcard
        assert any(origin in cors_origin for origin in expected_origins) or cors_origin == '*'


class TestInputValidation:
    """Test input validation and error handling."""
    
    def test_missing_required_fields(self, client):
        """Test error handling for missing required fields."""
        required_fields = ["staffList", "unavailabilityList", "weeklyNeeds", "shiftDefinitions"]
        
        for field in required_fields:
            scenario = get_basic_scenario()
            del scenario[field]  # Remove required field
            
            response = client.post('/api/schedule',
                                 data=json.dumps(scenario),
                                 content_type='application/json')
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'error' in data or 'message' in data
    
    def test_invalid_json_format(self, client):
        """Test error handling for malformed JSON."""
        invalid_json = '{"invalid": json format}'
        
        response = client.post('/api/schedule',
                             data=invalid_json,
                             content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
    
    def test_empty_staff_list(self, client):
        """Test handling of empty staff list."""
        scenario = get_basic_scenario()
        scenario["staffList"] = []
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        # Should either succeed with empty schedule or return 422
        assert response.status_code in [200, 422]
        
        data = response.get_json()
        if response.status_code == 200:
            # Empty staff should result in empty schedule
            schedule = data['schedule']
            total_assignments = sum(
                len(staff_list)
                for day_schedule in schedule.values()
                for shift_schedule in day_schedule.values()
                for staff_list in shift_schedule.values()
            )
            assert total_assignments == 0
    
    def test_invalid_time_format(self, client):
        """Test handling of invalid time formats."""
        scenario = get_basic_scenario()
        scenario["shiftDefinitions"]["HALF_DAY_AM"]["start"] = "25:00"  # Invalid hour
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
    
    @pytest.mark.parametrize("invalid_staff", INVALID_STAFF_EXAMPLES)
    def test_invalid_staff_data(self, client, invalid_staff):
        """Test handling of various invalid staff data."""
        scenario = get_basic_scenario()
        scenario["staffList"] = [invalid_staff]
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        # Should handle gracefully - either work around or fail gracefully
        assert response.status_code in [200, 400, 422]
        
        data = response.get_json()
        if response.status_code != 200:
            assert data['success'] is False
    
    @pytest.mark.parametrize("invalid_unavail", INVALID_UNAVAILABILITY_EXAMPLES)
    def test_invalid_unavailability_data(self, client, invalid_unavail):
        """Test handling of invalid unavailability data."""
        scenario = get_basic_scenario()
        scenario["unavailabilityList"] = [invalid_unavail]
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]
    
    @pytest.mark.parametrize("invalid_needs", INVALID_WEEKLY_NEEDS_EXAMPLES)
    def test_invalid_weekly_needs(self, client, invalid_needs):
        """Test handling of invalid weekly needs."""
        scenario = get_basic_scenario()
        scenario["weeklyNeeds"] = invalid_needs
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert response.status_code in [200, 400, 422]


class TestConstraintScenarios:
    """Test various constraint and business scenarios."""
    
    def test_understaffed_scenario(self, client):
        """Test API handling of understaffed scenarios."""
        scenario = get_understaffed_scenario()
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        # Should handle gracefully - either 200 with warnings or 422
        assert response.status_code in [200, 422]
        
        data = response.get_json()
        if response.status_code == 200:
            # Should have shortage warnings
            warnings = data.get('warnings', [])
            shortage_warnings = [w for w in warnings if 'Shortage' in w]
            assert len(shortage_warnings) > 0
        else:
            # Should explain why scheduling failed
            assert data['success'] is False
            assert 'message' in data
    
    def test_infeasible_constraints(self, client):
        """Test handling of impossible constraint combinations."""
        scenario = get_basic_scenario()
        
        # Create impossible scenario - staff wants min hours but unavailable all week
        staff_id = scenario["staffList"][0]["id"]
        scenario["staffList"][0]["minHoursPerWeek"] = 40
        scenario["unavailabilityList"] = [
            {
                "employeeId": staff_id,
                "dayOfWeek": day,
                "shifts": [{"start": "00:00", "end": "23:59"}]
            }
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        ]
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        # Should either succeed with warnings or return 422
        assert response.status_code in [200, 422]
        
        data = response.get_json()
        if response.status_code == 200:
            # Should have warnings about unmet constraints
            assert len(data.get('warnings', [])) > 0
    
    def test_large_request_handling(self, client):
        """Test handling of reasonably large requests."""
        scenario = get_basic_scenario()
        
        # Expand to moderate size
        extra_staff = [
            {
                "name": f"Staff {i}",
                "assignedRolesInPriority": ["Server"],
                "minHoursPerWeek": 10,
                "maxHoursPerWeek": 20,
                "id": f"staff-{i:03d}"
            }
            for i in range(10)  # Add 10 more staff
        ]
        scenario["staffList"].extend(extra_staff)
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        # Should complete within reasonable time
        assert data['calculationTimeMs'] < 60000  # Less than 1 minute


class TestShiftPreferences:
    """Test shift preference handling."""
    
    @pytest.mark.parametrize("preference", [
        "PRIORITIZE_FULL_DAYS",
        "PRIORITIZE_HALF_DAYS", 
        "NONE"
    ])
    def test_shift_preferences(self, client, preference):
        """Test that all shift preferences work."""
        scenario = get_basic_scenario()
        scenario["shiftPreference"] = preference
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Should generate reasonable schedule
        schedule = data['schedule']
        total_assignments = sum(
            len(staff_list)
            for day_schedule in schedule.values()
            for shift_schedule in day_schedule.values()
            for staff_list in shift_schedule.values()
        )
        assert total_assignments > 0


class TestStaffPriority:
    """Test staff priority handling."""
    
    def test_staff_priority_ordering(self, client):
        """Test that staff priority affects scheduling."""
        scenario = get_basic_scenario()
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # High priority staff should get some assignments
        schedule = data['schedule']
        high_priority_staff = scenario["staffPriority"][:2]
        
        assigned_staff = set()
        for day_schedule in schedule.values():
            for shift_schedule in day_schedule.values():
                for staff_list in shift_schedule.values():
                    assigned_staff.update(staff_list)
        
        # At least one high priority staff should be assigned
        high_priority_assigned = len([s for s in high_priority_staff if s in assigned_staff])
        assert high_priority_assigned > 0
    
    def test_empty_staff_priority(self, client):
        """Test handling of empty staff priority list."""
        scenario = get_basic_scenario()
        scenario["staffPriority"] = []
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True


class TestUnavailabilityConstraints:
    """Test unavailability constraint handling."""
    
    def test_unavailability_respected(self, client):
        """Test that unavailability constraints are respected."""
        scenario = get_basic_scenario()
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        schedule = data['schedule']
        
        # Check that unavailability constraints are respected
        for unavail in scenario["unavailabilityList"]:
            staff_id = unavail["employeeId"]
            day = unavail["dayOfWeek"]
            
            if day in schedule:
                for shift_schedule in schedule[day].values():
                    for staff_list in shift_schedule.values():
                        assert staff_id not in staff_list, f"Unavailability violated: {staff_id} on {day}"
    
    def test_cross_day_unavailability(self, client):
        """Test handling of cross-day unavailability periods."""
        scenario = get_basic_scenario()
        scenario["unavailabilityList"] = [
            {
                "employeeId": "alice-mgr-001",
                "dayOfWeek": "Friday",
                "shifts": [{"start": "23:00", "end": "03:00"}]  # Cross-day period
            }
        ]
        
        response = client.post('/api/schedule',
                             data=json.dumps(scenario),
                             content_type='application/json')
        
        # Should handle cross-day periods gracefully
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True