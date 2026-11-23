from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
TARGETS = (90, 85, 80, 75)


def ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def attendance_percent(attended: int, delivered: int) -> int:
    if delivered <= 0:
        return 0
    raw = (Decimal(attended) * Decimal(100) / Decimal(delivered)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return min(100, int(raw))


def marks_for(percent: int) -> int:
    if percent >= 90:
        return 5
    if percent >= 85:
        return 4
    if percent >= 80:
        return 3
    if percent >= 75:
        return 2
    return 0


def slab_plan(attended: int, delivered: int, remaining: int, strict: bool = True) -> dict[int, dict[str, int | bool]]:
    plan = {}
    for target in TARGETS:
        total = delivered + remaining
        strict_required = ceil_div(target * total, 100)
        rounded_required = ceil_div((2 * target - 1) * total, 200)
        required = strict_required if strict else rounded_required
        must_attend = max(0, required - attended)
        reachable = must_attend <= remaining
        plan[target] = {
            "marks": marks_for(target),
            "must_attend": must_attend,
            "can_miss": max(0, remaining - must_attend) if reachable else 0,
            "is_reachable": reachable,
            "strict_required": strict_required,
            "rounded_required": rounded_required,
        }
    return plan


def course_projection(row: dict[str, object], remaining: int, strict: bool = True) -> dict[str, object]:
    delivered = int(row["total_delivered"])
    attended = int(row["total_attended"]) + int(row.get("duty_leave", 0)) + int(row.get("first_week_bonus", 0))
    percent = attendance_percent(attended, delivered)
    return {
        **row,
        "counted_attended": attended,
        "current_pct": percent,
        "current_marks": marks_for(percent),
        "status_badge": "REAPPEAR" if percent < 75 else ("BORDERLINE" if percent < 85 else "SAFE"),
        "remaining_classes": remaining,
        "slabs": slab_plan(attended, delivered, remaining, strict),
    }
