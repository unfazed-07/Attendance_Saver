from app.services.math_engine import attendance_percent, marks_for, slab_plan


def test_sample_course_percentages_and_marks():
    samples = [(49, 41, 84, 3), (47, 44, 94, 5), (60, 53, 88, 4), (60, 52, 87, 4), (49, 44, 90, 5), (46, 41, 89, 4), (61, 51, 84, 3)]
    for delivered, attended, expected_pct, expected_marks in samples:
        percent = attendance_percent(attended, delivered)
        assert percent == expected_pct
        assert marks_for(percent) == expected_marks


def test_aggregate_sample_and_cap():
    assert attendance_percent(326, 372) == 88
    assert marks_for(attendance_percent(326, 372)) == 4
    assert attendance_percent(105, 100) == 100


def test_slab_plan_strict_and_reachability():
    plan = slab_plan(attended=41, delivered=49, remaining=20)
    assert plan[90]["must_attend"] == 22
    assert plan[90]["is_reachable"] is False
    assert plan[75]["is_reachable"] is True
    assert plan[75]["can_miss"] == 9


def test_half_up_rounding():
    assert attendance_percent(17, 20) == 85
    assert attendance_percent(41, 49) == 84
    assert attendance_percent(1, 8) == 13
