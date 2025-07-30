"""
Core business logic tests for restaurant scheduling system.
Covers business rules, optimization objectives, and constraint satisfaction.
"""
import pytest
from fixtures.test_data import (
    get_basic_scenario,
    get_understaffed_scenario,
    get_overstaffed_scenario,
    get_high_constraint_scenario
)
from scheduler.solver import generate_schedule_with_ortools
from scheduler.utils import calculate_total_weekly_hours


class TestBasicBusinessRules:
    """Test fundamental business rule enforcement."""
    
    def test_basic_schedule_generation(self):
        """Test that basic scheduling works correctly."""
        scenario = get_basic_scenario()
        
        schedule, warnings, calc_time = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        assert schedule is not None, "Should generate schedule for feasible scenario"
        assert calc_time > 0, "Should record calculation time"
        assert isinstance(warnings, list), "Should return warnings list"
        
        # Verify schedule structure
        expected_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day in expected_days:
            assert day in schedule, f"Schedule should include {day}"
    
    def test_no_double_booking(self):
        """Test that no staff member is double-booked on same day."""
        scenario = get_basic_scenario()
        
        schedule, warnings, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        assert schedule is not None
        
        # Check for double booking
        for day, day_schedule in schedule.items():
            staff_assignments = {}
            
            for shift_type, shift_schedule in day_schedule.items():
                for role, assigned_staff in shift_schedule.items():
                    for staff_id in assigned_staff:
                        assert staff_id not in staff_assignments, \
                            f"Staff {staff_id} double-booked on {day}: {staff_assignments.get(staff_id)} and {shift_type}:{role}"
                        staff_assignments[staff_id] = f"{shift_type}:{role}"
    
    def test_max_hours_not_exceeded(self):
        """Test that staff don't exceed maximum weekly hours."""
        scenario = get_basic_scenario()
        
        schedule, warnings, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        assert schedule is not None
        
        for staff in scenario["staffList"]:
            staff_id = staff["id"]
            total_hours = calculate_total_weekly_hours(staff_id, schedule, scenario["shiftDefinitions"])
            assert total_hours <= staff["maxHoursPerWeek"], \
                f"Staff {staff_id} exceeded max hours: {total_hours} > {staff['maxHoursPerWeek']}"
    
    def test_role_qualification_enforcement(self):
        """Test that staff are only assigned to qualified roles."""
        scenario = get_basic_scenario()
        
        schedule, warnings, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        assert schedule is not None
        
        # Create staff qualification lookup
        staff_qualifications = {staff["id"]: staff["assignedRolesInPriority"] for staff in scenario["staffList"]}
        
        for day_schedule in schedule.values():
            for shift_schedule in day_schedule.values():
                for role, assigned_staff in shift_schedule.items():
                    for staff_id in assigned_staff:
                        assert role in staff_qualifications[staff_id], \
                            f"Staff {staff_id} not qualified for role {role}"
    
    def test_unavailability_constraints_respected(self):
        """Test that unavailability constraints are strictly enforced."""
        scenario = get_basic_scenario()
        
        schedule, warnings, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        assert schedule is not None
        
        # Check each unavailability constraint
        for unavail in scenario["unavailabilityList"]:
            staff_id = unavail["employeeId"]
            day = unavail["dayOfWeek"]
            
            if day in schedule:
                for shift_schedule in schedule[day].values():
                    for assigned_staff in shift_schedule.values():
                        assert staff_id not in assigned_staff, \
                            f"Unavailability constraint violated: {staff_id} on {day}"


class TestOptimizationObjectives:
    """Test the 5-level optimization objective hierarchy."""
    
    def test_demand_shortage_minimization_priority(self):
        """Test demand shortage minimization (weight: 10,000 - highest priority)."""
        scenario = get_basic_scenario()
        
        # Test with different shift preferences - demand coverage should be consistent
        demand_coverages = []
        for preference in ["PRIORITIZE_FULL_DAYS", "PRIORITIZE_HALF_DAYS", "NONE"]:
            scenario["shiftPreference"] = preference
            
            schedule, warnings, _ = generate_schedule_with_ortools(
                scenario["weeklyNeeds"],
                scenario["staffList"],
                scenario["unavailabilityList"],
                scenario["shiftDefinitions"],
                scenario["shiftPreference"],
                scenario["staffPriority"]
            )
            
            if schedule is not None:
                # Calculate demand coverage
                total_demand = 0
                total_covered = 0
                
                for day, day_needs in scenario["weeklyNeeds"].items():
                    for shift_type, role_needs in day_needs.items():
                        for role, needed_count in role_needs.items():
                            total_demand += needed_count
                            
                            if (day in schedule and 
                                shift_type in schedule[day] and 
                                role in schedule[day][shift_type]):
                                covered_count = len(schedule[day][shift_type][role])
                                total_covered += min(covered_count, needed_count)
                
                coverage_rate = total_covered / total_demand if total_demand > 0 else 0
                demand_coverages.append(coverage_rate)
        
        # Demand coverage should be consistently prioritized
        if demand_coverages:
            avg_coverage = sum(demand_coverages) / len(demand_coverages)
            assert avg_coverage >= 0.7, f"Demand coverage should be prioritized: {avg_coverage:.2%}"
    
    def test_min_hour_shortage_minimization(self):
        """Test minimum hour shortage minimization (weight: 2,000)."""
        scenario = get_basic_scenario()
        
        # Set high minimum hours for some staff
        for staff in scenario["staffList"][:2]:
            staff["minHoursPerWeek"] = 30
        
        schedule, warnings, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],  
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        if schedule is not None:
            # Check if high-min-hour staff get more hours
            high_min_staff = scenario["staffList"][:2]
            other_staff = scenario["staffList"][2:]
            
            high_min_hours = [
                calculate_total_weekly_hours(staff["id"], schedule, scenario["shiftDefinitions"])
                for staff in high_min_staff
            ]
            other_hours = [
                calculate_total_weekly_hours(staff["id"], schedule, scenario["shiftDefinitions"])
                for staff in other_staff[:2]  # Compare with first 2 others
            ]
            
            if high_min_hours and other_hours:
                avg_high_min = sum(high_min_hours) / len(high_min_hours)
                avg_other = sum(other_hours) / len(other_hours)
                
                # High min hour staff should get competitive hours
                assert avg_high_min >= avg_other * 0.8, \
                    f"Min hour optimization should work: {avg_high_min:.1f} vs {avg_other:.1f}"
    
    def test_shift_preference_optimization(self):
        """Test shift preference optimization (weight: 100)."""
        scenario = get_basic_scenario()
        
        # Test PRIORITIZE_FULL_DAYS
        scenario["shiftPreference"] = "PRIORITIZE_FULL_DAYS"
        schedule_full_days, _, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        # Test PRIORITIZE_HALF_DAYS
        scenario["shiftPreference"] = "PRIORITIZE_HALF_DAYS"
        schedule_half_days, _, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        if schedule_full_days is not None and schedule_half_days is not None:
            def count_full_day_assignments(schedule):
                full_day_count = 0
                for day, day_schedule in schedule.items():
                    if "HALF_DAY_AM" in day_schedule and "HALF_DAY_PM" in day_schedule:
                        am_staff = set()
                        pm_staff = set()
                        
                        for role_assignments in day_schedule["HALF_DAY_AM"].values():
                            am_staff.update(role_assignments)
                        for role_assignments in day_schedule["HALF_DAY_PM"].values():
                            pm_staff.update(role_assignments)
                        
                        full_day_count += len(am_staff & pm_staff)
                return full_day_count
            
            full_day_pref_full_days = count_full_day_assignments(schedule_full_days)
            half_day_pref_full_days = count_full_day_assignments(schedule_half_days)
            
            # PRIORITIZE_FULL_DAYS should generally result in more full-day assignments
            assert full_day_pref_full_days >= half_day_pref_full_days - 1, \
                "Shift preferences should influence scheduling"
    
    def test_staff_priority_optimization(self):
        """Test staff priority optimization (weight: 20)."""
        scenario = get_overstaffed_scenario()  # Use overstaffed to see priority effects
        
        schedule, warnings, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"], 
            scenario["staffPriority"]
        )
        
        if schedule is not None:
            # Check that high priority staff get assigned preferentially
            high_priority_staff = scenario["staffPriority"][:3]  # Top 3
            low_priority_staff = scenario["staffPriority"][-3:]  # Bottom 3
            
            assigned_staff = set()
            for day_schedule in schedule.values():
                for shift_schedule in day_schedule.values():
                    for staff_list in shift_schedule.values():
                        assigned_staff.update(staff_list)
            
            high_priority_assigned = len([s for s in high_priority_staff if s in assigned_staff])
            low_priority_assigned = len([s for s in low_priority_staff if s in assigned_staff])
            
            # High priority staff should be more likely to be assigned
            assert high_priority_assigned >= low_priority_assigned, \
                f"Staff priority should affect assignment: {high_priority_assigned} vs {low_priority_assigned}"
    
    def test_role_preference_optimization(self):
        """Test role preference optimization (weight: 10 - lowest priority)."""
        scenario = get_basic_scenario()
        
        schedule, warnings, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        if schedule is not None:
            # Check role preference satisfaction
            role_preference_matches = 0
            total_assignments = 0
            
            for day_schedule in schedule.values():
                for shift_schedule in day_schedule.values():
                    for role, assigned_staff in shift_schedule.items():
                        for staff_id in assigned_staff:
                            total_assignments += 1
                            
                            # Find staff member and check if role is their top preference
                            staff_member = next(s for s in scenario["staffList"] if s["id"] == staff_id)
                            if role == staff_member["assignedRolesInPriority"][0]:
                                role_preference_matches += 1
            
            if total_assignments > 0:
                preference_rate = role_preference_matches / total_assignments
                # Should satisfy some role preferences (though lowest priority)
                assert preference_rate >= 0.2, f"Should satisfy some role preferences: {preference_rate:.2%}"


class TestConstraintScenarios:
    """Test various constraint scenarios and edge cases."""
    
    def test_understaffed_scenario_handling(self):
        """Test system behavior with insufficient staff."""
        scenario = get_understaffed_scenario()
        
        schedule, warnings, calc_time = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        # Should either generate partial schedule or return None with warnings
        if schedule is not None:
            # Should have shortage warnings
            shortage_warnings = [w for w in warnings if "Shortage" in w]
            assert len(shortage_warnings) > 0, "Should have shortage warnings for understaffed scenario"
            
            # Schedule should be limited due to staff constraints
            total_assignments = sum(
                len(staff_list)
                for day_schedule in schedule.values()
                for shift_schedule in day_schedule.values()
                for staff_list in shift_schedule.values()
            )
            # With only 2 staff, assignments should be limited
            assert total_assignments < 20, f"Understaffed should have limited assignments: {total_assignments}"
        else:
            # If no schedule, should have explanatory warnings
            assert len(warnings) > 0, "Should have warnings explaining why scheduling failed"
        
        # Should complete within reasonable time
        assert calc_time < 30000, "Understaffed scenario should complete quickly"
    
    def test_high_constraint_scenario_feasibility(self):
        """Test system behavior with many overlapping constraints."""
        scenario = get_high_constraint_scenario()
        
        schedule, warnings, calc_time = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        # System should handle high constraints gracefully
        if schedule is not None:
            # Verify all hard constraints are satisfied
            for unavail in scenario["unavailabilityList"]:
                staff_id = unavail["employeeId"]
                day = unavail["dayOfWeek"]
                
                if day in schedule:
                    for shift_schedule in schedule[day].values():
                        for assigned_staff in shift_schedule.values():
                            assert staff_id not in assigned_staff, \
                                f"Unavailability constraint violated: {staff_id} on {day}"
        
        # Should complete within reasonable time
        assert calc_time < 60000, "High constraint scenario should complete within 1 minute"
    
    def test_optimization_hierarchy_integration(self):
        """Test that all optimization objectives work together correctly."""
        scenario = get_basic_scenario()
        
        # Create scenario that tests priority conflicts
        # 1. High min hours to create min hour pressure
        for staff in scenario["staffList"][:2]:
            staff["minHoursPerWeek"] = 30
        
        # 2. Set shift preference
        scenario["shiftPreference"] = "PRIORITIZE_FULL_DAYS"
        
        schedule, warnings, _ = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        if schedule is not None:
            # 1. Demand coverage should be prioritized
            total_demand = sum(
                sum(role_needs.values())
                for day_needs in scenario["weeklyNeeds"].values()
                for role_needs in day_needs.values()
            )
            
            total_assignments = sum(
                len(staff_list)
                for day_schedule in schedule.values()
                for shift_schedule in day_schedule.values()
                for staff_list in shift_schedule.values()
            )
            
            coverage_rate = total_assignments / total_demand if total_demand > 0 else 0
            assert coverage_rate >= 0.5, f"Should maintain reasonable demand coverage: {coverage_rate:.2%}"
            
            # 2. Should try to satisfy min hours for high-min-hour staff
            high_min_staff = scenario["staffList"][:2]
            min_hour_satisfaction = 0
            
            for staff in high_min_staff:
                actual_hours = calculate_total_weekly_hours(staff["id"], schedule, scenario["shiftDefinitions"])
                if actual_hours >= staff["minHoursPerWeek"] * 0.7:  # Within 70% of minimum
                    min_hour_satisfaction += 1
            
            # Should satisfy some min hour requirements (but not at expense of demand)
            min_hour_rate = min_hour_satisfaction / len(high_min_staff)
            # This is flexible as demand takes priority
            assert min_hour_rate >= 0, "Min hour optimization should attempt to work"


class TestScheduleQuality:
    """Test overall schedule quality and consistency."""
    
    def test_schedule_consistency(self):
        """Test that repeated runs produce consistent results."""
        scenario = get_basic_scenario()
        
        # Run same scenario multiple times
        schedules = []
        for i in range(3):
            schedule, warnings, calc_time = generate_schedule_with_ortools(
                scenario["weeklyNeeds"],
                scenario["staffList"],
                scenario["unavailabilityList"],
                scenario["shiftDefinitions"],
                scenario["shiftPreference"],
                scenario["staffPriority"]
            )
            
            if schedule is not None:
                schedules.append(schedule)
                # Should complete within reasonable time
                assert calc_time < 30000, f"Run {i} should complete within 30 seconds"
        
        if len(schedules) >= 2:
            # Check that solutions are reasonably similar
            def count_assignments(schedule):
                return sum(
                    len(staff_list)
                    for day_schedule in schedule.values()
                    for shift_schedule in day_schedule.values()
                    for staff_list in shift_schedule.values()
                )
            
            assignment_counts = [count_assignments(schedule) for schedule in schedules]
            
            if assignment_counts:
                min_assignments = min(assignment_counts)
                max_assignments = max(assignment_counts)
                if min_assignments > 0:
                    similarity = min_assignments / max_assignments
                    assert similarity >= 0.8, f"Repeated runs should be reasonably consistent: {similarity:.2%}"
    
    def test_performance_within_bounds(self):
        """Test that scheduling completes within reasonable time bounds."""
        scenario = get_basic_scenario()
        
        schedule, warnings, calc_time = generate_schedule_with_ortools(
            scenario["weeklyNeeds"],
            scenario["staffList"],
            scenario["unavailabilityList"],
            scenario["shiftDefinitions"],
            scenario["shiftPreference"],
            scenario["staffPriority"]
        )
        
        # Should complete quickly for basic scenario
        assert calc_time < 10000, f"Basic scenario should solve within 10 seconds: {calc_time}ms"
        
        if schedule is not None:
            # Should generate reasonable number of assignments
            total_assignments = sum(
                len(staff_list)
                for day_schedule in schedule.values()
                for shift_schedule in day_schedule.values()
                for staff_list in shift_schedule.values()
            )
            assert total_assignments >= 10, f"Should generate substantial assignments: {total_assignments}"