"""
optimizer.py - Linear Programming based Timetable Generator
AI-Based Intelligent Faculty Workload and Scheduling System

Uses PuLP (CBC solver) to assign:
  Faculty × Course × Classroom × TimeSlot

Constraints:
  1. No faculty overload (assigned hours ≤ max_hours)
  2. No room double-booking (one class per room per slot)
  3. One class per timeslot per faculty
  4. Faculty-subject matching (faculty can only teach allowed subjects)
  5. Each course gets exactly its required hours

Objective:
  Minimize variance in workload utilization (balance evenly)
"""

import logging
from itertools import product
from pulp import (
    LpProblem, LpVariable, LpMinimize, LpBinary, LpContinuous,
    lpSum, value, PULP_CBC_CMD, LpStatus
)
from django.utils import timezone
from .models import Faculty, Course, Classroom, TimeSlot, TimetableEntry, WorkloadLog, ScheduleVersion

logger = logging.getLogger(__name__)


def run_optimizer(created_by=None):
    """
    Main entry point. Runs LP optimization and saves results to DB.
    Returns (success: bool, message: str, version: ScheduleVersion|None)
    """
    # ── 1. Load active data ──────────────────────────────────────────────────
    faculties = list(Faculty.objects.filter(is_active=True))
    courses   = list(Course.objects.filter(is_active=True))
    classrooms = list(Classroom.objects.filter(is_available=True))
    timeslots  = list(TimeSlot.objects.all())

    if not faculties:
        return False, "No active faculty found. Please upload faculty data.", None
    if not courses:
        return False, "No courses found. Please upload course data.", None
    if not classrooms:
        return False, "No classrooms found. Please upload classroom data.", None
    if not timeslots:
        return False, "No timeslots defined. Please create timeslots via admin.", None

    # ── 2. Create version record ─────────────────────────────────────────────
    last_v = ScheduleVersion.objects.order_by('-version_number').first()
    new_v_num = (last_v.version_number + 1) if last_v else 1
    version = ScheduleVersion.objects.create(
        version_number=new_v_num,
        status='running',
        created_by=created_by,
        description=f"Auto-generated on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    )

    try:
        result = _solve(faculties, courses, classrooms, timeslots, version)
        return result
    except Exception as e:
        version.status = 'failed'
        version.solver_status = str(e)
        version.save()
        logger.exception("Optimizer failed")
        return False, f"Optimization error: {str(e)}", version


def _solve(faculties, courses, classrooms, timeslots, version):
    """Internal LP solver."""

    # Index shortcuts
    F = range(len(faculties))
    C = range(len(courses))
    R = range(len(classrooms))
    T = range(len(timeslots))

    # ── 3. Build LP Problem ──────────────────────────────────────────────────
    prob = LpProblem("FacultyScheduling", LpMinimize)

    # Decision variable: x[f][c][r][t] = 1 if faculty f teaches course c in room r at timeslot t
    x = LpVariable.dicts(
        "x",
        [(f, c, r, t) for f, c, r, t in product(F, C, R, T)],
        cat=LpBinary
    )

    # Auxiliary: workload utilization deviation for each faculty (for balancing)
    deviation = LpVariable.dicts("dev", F, lowBound=0, cat=LpContinuous)

    # Average utilization (constant target - 0.7 = 70% utilization target)
    TARGET_UTIL = 0.7

    # ── 4. Objective: Minimize sum of deviations from target utilization ──────
    prob += lpSum(deviation[f] for f in F), "Balance_Workload"

    # ── 5. Constraints ───────────────────────────────────────────────────────

    # C1: Each course must be assigned exactly hours_required sessions
    for c in C:
        prob += (
            lpSum(x[(f, c, r, t)] for f in F for r in R for t in T)
            == courses[c].hours_required,
            f"Course_Hours_{c}"
        )

    # C2: Faculty workload ≤ max_hours (no overload)
    for f in F:
        fac_hours = lpSum(x[(f, c, r, t)] for c in C for r in R for t in T)
        prob += (fac_hours <= faculties[f].max_hours, f"FacultyMaxHours_{f}")

    # C3: No room double-booking (one class per room per timeslot)
    for r in R:
        for t in T:
            prob += (
                lpSum(x[(f, c, r, t)] for f in F for c in C) <= 1,
                f"RoomDoubleBook_{r}_{t}"
            )

    # C4: One class per faculty per timeslot (no faculty split)
    for f in F:
        for t in T:
            prob += (
                lpSum(x[(f, c, r, t)] for c in C for r in R) <= 1,
                f"FacultySlotConflict_{f}_{t}"
            )

    # C5: Faculty-subject matching constraint
    for f in F:
        for c in C:
            if not faculties[f].can_teach(courses[c].course_name):
                prob += (
                    lpSum(x[(f, c, r, t)] for r in R for t in T) == 0,
                    f"SubjectMatch_{f}_{c}"
                )

    # C6: Deviation constraint for workload balancing
    for f in F:
        fac_hours = lpSum(x[(f, c, r, t)] for c in C for r in R for t in T)
        util = fac_hours / faculties[f].max_hours if faculties[f].max_hours > 0 else fac_hours
        # deviation[f] ≥ util - TARGET  AND  deviation[f] ≥ TARGET - util
        prob += (deviation[f] >= util - TARGET_UTIL, f"DevPos_{f}")
        prob += (deviation[f] >= TARGET_UTIL - util, f"DevNeg_{f}")

    # ── 6. Solve ─────────────────────────────────────────────────────────────
    logger.info("Starting CBC solver...")
    solver = PULP_CBC_CMD(msg=0, timeLimit=120)
    prob.solve(solver)

    solver_status = LpStatus[prob.status]
    version.solver_status = solver_status
    logger.info(f"Solver status: {solver_status}")

    if prob.status not in (1,):  # 1 = Optimal
        version.status = 'failed'
        version.save()
        return False, f"Solver returned status: {solver_status}. Try reducing courses or adjusting hours.", version

    # ── 7. Save results to DB ─────────────────────────────────────────────────
    # Clear previous entries for this version (safety)
    TimetableEntry.objects.filter(schedule_version=version.version_number).delete()
    WorkloadLog.objects.filter(schedule_version=version.version_number).delete()

    assignments = []
    for f, c, r, t in product(F, C, R, T):
        if value(x[(f, c, r, t)]) and round(value(x[(f, c, r, t)])) == 1:
            assignments.append(TimetableEntry(
                faculty=faculties[f],
                course=courses[c],
                classroom=classrooms[r],
                timeslot=timeslots[t],
                schedule_version=version.version_number
            ))

    TimetableEntry.objects.bulk_create(assignments, ignore_conflicts=True)

    # ── 8. Save workload logs ─────────────────────────────────────────────────
    workload_logs = []
    for f in F:
        assigned = sum(
            round(value(x[(f, c, r, t)]))
            for c, r, t in product(C, R, T)
            if value(x[(f, c, r, t)]) is not None
        )
        max_h = faculties[f].max_hours
        util_pct = round((assigned / max_h * 100), 2) if max_h > 0 else 0.0
        workload_logs.append(WorkloadLog(
            faculty=faculties[f],
            schedule_version=version.version_number,
            assigned_hours=assigned,
            max_hours=max_h,
            utilization_percent=util_pct
        ))
        # Update course assigned_faculty
        for c in C:
            total = sum(
                round(value(x[(f, c, r, t)]))
                for r, t in product(R, T)
                if value(x[(f, c, r, t)]) is not None
            )
            if total > 0:
                courses[c].assigned_faculty = faculties[f]
                courses[c].save()

    WorkloadLog.objects.bulk_create(workload_logs, ignore_conflicts=True)

    # ── 9. Mark version active ────────────────────────────────────────────────
    ScheduleVersion.objects.all().update(is_active=False)
    version.status = 'success'
    version.total_assignments = len(assignments)
    version.is_active = True
    version.save()

    logger.info(f"Optimizer complete. {len(assignments)} assignments saved.")
    return True, f"Timetable generated successfully! {len(assignments)} sessions scheduled.", version
