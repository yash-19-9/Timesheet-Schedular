"""
views.py - All application views
AI-Based Intelligent Faculty Workload and Scheduling System

Views:
  - login_view / logout_view
  - dashboard (Admin: full workload charts; Faculty: personal schedule)
  - upload_faculty / upload_courses / upload_classrooms (Excel)
  - run_optimizer (triggers LP solver)
  - timetable_view (display full generated timetable)
  - faculty_schedule_view (personal schedule for logged-in faculty)
  - export_timetable_pdf / export_workload_pdf / export_faculty_pdf
  - manage_data (list of faculty, courses, rooms)
"""

import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from .models import (
    Faculty, Course, Classroom, TimeSlot, TimetableEntry,
    WorkloadLog, ScheduleVersion, FacultyUnavailability, Notification
)
from .excel_upload import parse_faculty_excel, parse_courses_excel, parse_classrooms_excel
from .optimizer import run_optimizer
from .pdf_generator import generate_timetable_pdf, generate_workload_pdf, generate_faculty_schedule_pdf

logger = logging.getLogger(__name__)


# ─── Helper: Admin check ──────────────────────────────────────────────────────
def is_admin(user):
    return user.is_staff or user.is_superuser


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

def login_view(request):
    """Role-based login: Admin → full dashboard; Faculty → personal schedule."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid credentials. Please try again.")

    return render(request, 'scheduler/login.html')


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def dashboard(request):
    """
    Admin: Shows workload distribution charts, system stats, version history.
    Faculty: Shows their own workload and quick schedule preview.
    """
    active_version = ScheduleVersion.objects.filter(is_active=True).first()
    version_number = active_version.version_number if active_version else None

    if is_admin(request.user):
        # ── Admin Dashboard Data ───────────────────────────────────────────
        logs = WorkloadLog.objects.filter(
            schedule_version=version_number
        ).select_related('faculty').order_by('-utilization_percent') if version_number else []

        # Chart.js data
        chart_labels = [log.faculty.name for log in logs]
        chart_assigned = [log.assigned_hours for log in logs]
        chart_max = [log.max_hours for log in logs]
        chart_util = [log.utilization_percent for log in logs]

        # Stats cards
        total_faculty = Faculty.objects.filter(is_active=True).count()
        total_courses = Course.objects.filter(is_active=True).count()
        total_rooms = Classroom.objects.filter(is_available=True).count()
        total_slots = TimetableEntry.objects.filter(
            schedule_version=version_number).count() if version_number else 0

        versions = ScheduleVersion.objects.all()[:10]

        context = {
            'role': 'admin',
            'active_version': active_version,
            'versions': versions,
            'logs': logs,
            'chart_labels': json.dumps(chart_labels),
            'chart_assigned': json.dumps(chart_assigned),
            'chart_max': json.dumps(chart_max),
            'chart_util': json.dumps(chart_util),
            'total_faculty': total_faculty,
            'total_courses': total_courses,
            'total_rooms': total_rooms,
            'total_slots': total_slots,
        }
    else:
        # ── Faculty Dashboard Data ─────────────────────────────────────────
        try:
            faculty = Faculty.objects.get(user=request.user)
        except Faculty.DoesNotExist:
            messages.warning(request, "Your faculty profile is not set up. Contact admin.")
            return render(request, 'scheduler/dashboard.html', {'role': 'faculty', 'faculty': None})

        workload = WorkloadLog.objects.filter(
            faculty=faculty, schedule_version=version_number
        ).first() if version_number else None

        recent_entries = TimetableEntry.objects.filter(
            faculty=faculty, schedule_version=version_number
        ).select_related('course', 'classroom', 'timeslot').order_by(
            'timeslot__day', 'timeslot__period'
        )[:10] if version_number else []

        context = {
            'role': 'faculty',
            'faculty': faculty,
            'workload': workload,
            'recent_entries': recent_entries,
            'active_version': active_version,
        }

    return render(request, 'scheduler/dashboard.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEL UPLOAD VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def upload_page(request):
    """Landing page for all Excel uploads."""
    if not is_admin(request.user):
        messages.error(request, "Access denied. Admin only.")
        return redirect('dashboard')
    return render(request, 'scheduler/upload.html')


@login_required
def upload_faculty(request):
    """Handle faculty Excel upload."""
    if not is_admin(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select an Excel file.")
            return redirect('upload_page')

        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Invalid file format. Please upload .xlsx or .xls")
            return redirect('upload_page')

        try:
            created, skipped, errors = parse_faculty_excel(excel_file)
            if errors:
                for err in errors[:5]:  # show max 5 errors
                    messages.warning(request, err)
            messages.success(
                request, f"Faculty upload complete: {created} added/updated, {skipped} skipped."
            )
        except Exception as e:
            messages.error(request, f"Upload failed: {str(e)}")

    return redirect('upload_page')


@login_required
def upload_courses(request):
    """Handle courses Excel upload."""
    if not is_admin(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select an Excel file.")
            return redirect('upload_page')

        try:
            created, skipped, errors = parse_courses_excel(excel_file)
            if errors:
                for err in errors[:5]:
                    messages.warning(request, err)
            messages.success(
                request, f"Courses upload complete: {created} added/updated, {skipped} skipped."
            )
        except Exception as e:
            messages.error(request, f"Upload failed: {str(e)}")

    return redirect('upload_page')


@login_required
def upload_classrooms(request):
    """Handle classrooms Excel upload."""
    if not is_admin(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select an Excel file.")
            return redirect('upload_page')

        try:
            created, skipped, errors = parse_classrooms_excel(excel_file)
            if errors:
                for err in errors[:5]:
                    messages.warning(request, err)
            messages.success(
                request, f"Classrooms upload complete: {created} added/updated, {skipped} skipped."
            )
        except Exception as e:
            messages.error(request, f"Upload failed: {str(e)}")

    return redirect('upload_page')


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIMIZER VIEW
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def run_optimization(request):
    """Trigger the LP optimizer to generate a new timetable."""
    if not is_admin(request.user):
        messages.error(request, "Access denied. Admin only.")
        return redirect('dashboard')

    if request.method == 'POST':
        messages.info(request, "Optimization started. This may take a moment...")
        success, msg, version = run_optimizer(created_by=request.user)

        if success:
            messages.success(request, f"✅ {msg}")
        else:
            messages.error(request, f"❌ {msg}")

    return redirect('timetable')


# ═══════════════════════════════════════════════════════════════════════════════
# TIMETABLE VIEW
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def timetable_view(request):
    """
    Display the full timetable in a grid format.
    Admin sees all; Faculty sees own schedule highlighted.
    """
    version_id = request.GET.get('version')
    if version_id:
        version = get_object_or_404(ScheduleVersion, version_number=version_id)
        version_number = version.version_number
    else:
        version = ScheduleVersion.objects.filter(is_active=True).first()
        version_number = version.version_number if version else None

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    periods = list(TimeSlot.objects.values_list('period', flat=True).distinct().order_by('period'))
    timeslots_meta = {
        ts.period: {'start': ts.start_time.strftime('%H:%M'), 'end': ts.end_time.strftime('%H:%M')}
        for ts in TimeSlot.objects.filter(day='Monday')
    }

    entries = TimetableEntry.objects.filter(
        schedule_version=version_number
    ).select_related('faculty', 'course', 'classroom', 'timeslot') if version_number else []

    # Build timetable grid: {day: {period: [entries]}}
    grid = {day: {period: [] for period in periods} for day in days}
    for entry in entries:
        d = entry.timeslot.day
        p = entry.timeslot.period
        if d in grid and p in grid[d]:
            grid[d][p].append(entry)

    # For faculty view, get current faculty
    current_faculty = None
    if not is_admin(request.user):
        try:
            current_faculty = Faculty.objects.get(user=request.user)
        except Faculty.DoesNotExist:
            pass

    versions = ScheduleVersion.objects.all()[:10]

    context = {
        'grid': grid,
        'days': days,
        'periods': periods,
        'timeslots_meta': timeslots_meta,
        'version': version,
        'versions': versions,
        'current_faculty': current_faculty,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'scheduler/timetable.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MANAGEMENT VIEW
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def manage_data(request):
    """Display all faculty, courses, and classrooms for admin review."""
    if not is_admin(request.user):
        return redirect('dashboard')

    context = {
        'faculties': Faculty.objects.all().order_by('name'),
        'courses': Course.objects.all().order_by('course_name'),
        'classrooms': Classroom.objects.all().order_by('room_name'),
        'timeslots': TimeSlot.objects.all().order_by('day', 'period'),
    }
    return render(request, 'scheduler/manage_data.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def export_timetable_pdf(request):
    """Export the full timetable as PDF."""
    version_id = request.GET.get('version')
    buffer = generate_timetable_pdf(version_number=int(version_id) if version_id else None)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="timetable_v{version_id or "active"}.pdf"'
    return response


@login_required
def export_workload_pdf(request):
    """Export workload summary as PDF."""
    if not is_admin(request.user):
        return redirect('dashboard')

    version_id = request.GET.get('version')
    buffer = generate_workload_pdf(version_number=int(version_id) if version_id else None)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="workload_summary_v{version_id or "active"}.pdf"'
    return response


@login_required
def export_faculty_pdf(request, faculty_id):
    """Export individual faculty schedule as PDF."""
    version_id = request.GET.get('version')
    buffer = generate_faculty_schedule_pdf(
        faculty_id=faculty_id,
        version_number=int(version_id) if version_id else None
    )

    response = HttpResponse(buffer, content_type='application/pdf')
    faculty = get_object_or_404(Faculty, id=faculty_id)
    response['Content-Disposition'] = f'attachment; filename="{faculty.name}_schedule.pdf"'
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# API / AJAX VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def api_workload_data(request):
    """JSON endpoint for Chart.js workload chart re-rendering."""
    version_id = request.GET.get('version')
    logs = WorkloadLog.objects.filter(
        schedule_version=version_id
    ).select_related('faculty') if version_id else []

    data = {
        'labels': [log.faculty.name for log in logs],
        'assigned': [log.assigned_hours for log in logs],
        'max_hours': [log.max_hours for log in logs],
        'utilization': [log.utilization_percent for log in logs],
    }
    return JsonResponse(data)


# ═══════════════════════════════════════════════════════════════════════════════
# UNAVAILABILITY & NOTIFICATION VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def mark_unavailable(request, entry_id):
    """
    Faculty marks themselves as NOT FREE for a specific timetable entry.
    Creates a FacultyUnavailability record and notifies all admin users.
    """
    entry = get_object_or_404(TimetableEntry, id=entry_id)

    # Verify it's the faculty's own session
    try:
        faculty = Faculty.objects.get(user=request.user)
    except Faculty.DoesNotExist:
        messages.error(request, "Faculty profile not found.")
        return redirect('timetable')

    if entry.faculty != faculty:
        messages.error(request, "You can only mark your own sessions.")
        return redirect('timetable')

    # Avoid duplicate pending requests
    existing = FacultyUnavailability.objects.filter(
        faculty=faculty, timetable_entry=entry, status='pending'
    ).exists()
    if existing:
        messages.warning(request, "You already have a pending request for this slot.")
        return redirect('timetable')

    reason = request.POST.get('reason', '').strip()

    # Create unavailability record
    unavail = FacultyUnavailability.objects.create(
        faculty=faculty,
        timetable_entry=entry,
        reason=reason,
        status='pending',
    )

    # Notify all admin/staff users
    admins = User.objects.filter(is_staff=True)
    slot_str = f"{entry.timeslot.day} Period {entry.timeslot.period}"
    notif_title = f"🚫 Faculty Not Available — {faculty.name}"
    notif_msg = (
        f"{faculty.name} is not free for {entry.course.course_name} "
        f"({slot_str}) in {entry.classroom.room_name}. "
        f"Reason: {reason or 'Not specified'}. Please reassign."
    )
    for admin_user in admins:
        Notification.objects.create(
            recipient=admin_user,
            sender=request.user,
            title=notif_title,
            message=notif_msg,
            notif_type='unavailability_request',
            related_entry=entry,
            related_unavailability=unavail,
        )

    messages.success(
        request,
        f"✅ Unavailability reported for {slot_str}. Admin will reassign your session."
    )
    return redirect('timetable')


@login_required
def reassign_faculty(request, unavail_id):
    """
    Admin view: reassign a timetable entry to a different faculty.
    GET  → shows form with available faculty options
    POST → saves new assignment, creates notifications for both faculty members
    """
    if not is_admin(request.user):
        messages.error(request, "Access denied. Admin only.")
        return redirect('dashboard')

    unavail = get_object_or_404(FacultyUnavailability, id=unavail_id)
    entry = unavail.timetable_entry

    if request.method == 'POST':
        new_faculty_id = request.POST.get('new_faculty_id')
        new_faculty = get_object_or_404(Faculty, id=new_faculty_id)

        # Save old faculty for notification
        old_faculty = entry.faculty

        # Update the timetable entry
        entry.faculty = new_faculty
        entry.save()

        # Mark unavailability as resolved
        from django.utils import timezone
        unavail.status = 'reassigned'
        unavail.reassigned_to = new_faculty
        unavail.resolved_at = timezone.now()
        unavail.save()

        slot_str = f"{entry.timeslot.day} Period {entry.timeslot.period}"

        # Notify original faculty
        if old_faculty.user:
            Notification.objects.create(
                recipient=old_faculty.user,
                sender=request.user,
                title=f"✅ Your slot was reassigned",
                message=(
                    f"Your {entry.course.course_name} session on {slot_str} "
                    f"has been reassigned to {new_faculty.name}. You are free that slot."
                ),
                notif_type='reassignment_done',
                related_entry=entry,
                related_unavailability=unavail,
            )

        # Notify new faculty
        if new_faculty.user:
            Notification.objects.create(
                recipient=new_faculty.user,
                sender=request.user,
                title=f"📋 New class assigned to you",
                message=(
                    f"You have been assigned to teach {entry.course.course_name} "
                    f"({slot_str}) in {entry.classroom.room_name}. "
                    f"Previously held by {old_faculty.name}."
                ),
                notif_type='reassignment_done',
                related_entry=entry,
                related_unavailability=unavail,
            )

        messages.success(
            request,
            f"✅ Reassigned {entry.course.course_name} ({slot_str}) to {new_faculty.name}."
        )
        return redirect('notifications_page')

    # GET: show list of other available faculty
    # Exclude the original faculty and those already busy in this slot
    busy_faculty_ids = TimetableEntry.objects.filter(
        timeslot=entry.timeslot,
        schedule_version=entry.schedule_version
    ).exclude(id=entry.id).values_list('faculty_id', flat=True)

    available_faculty = Faculty.objects.filter(
        is_active=True
    ).exclude(
        id=entry.faculty_id
    ).exclude(
        id__in=busy_faculty_ids
    )

    context = {
        'unavail': unavail,
        'entry': entry,
        'available_faculty': available_faculty,
        'is_admin': True,
    }
    return render(request, 'scheduler/reassign.html', context)


@login_required
def api_notifications(request):
    """
    JSON API polled every 15 seconds by the frontend for Chrome notifications.
    Returns unread notifications for the current user.
    Optional ?since=<id> to only get notifications newer than a given ID.
    """
    since_id = request.GET.get('since', 0)
    notifs = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        id__gt=since_id
    ).order_by('-created_at')[:20]

    data = {
        'unread_count': Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count(),
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.notif_type,
                'created_at': n.created_at.strftime('%d %b %Y, %H:%M'),
                'related_unavailability_id': n.related_unavailability_id,
            }
            for n in notifs
        ],
    }
    return JsonResponse(data)


@login_required
@require_POST
def mark_notification_read(request, notif_id):
    """Mark a single notification as read."""
    notif = get_object_or_404(Notification, id=notif_id, recipient=request.user)
    notif.is_read = True
    notif.save()
    return JsonResponse({'status': 'ok'})


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user."""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect('notifications_page')


@login_required
def notifications_page(request):
    """Full notifications history page."""
    base_qs = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender').order_by('-created_at')

    # Count BEFORE slicing (Django can't filter a sliced queryset)
    unread_count = base_qs.filter(is_read=False).count()
    notifications = base_qs[:50]

    # Pending unavailability requests (admin only)
    pending_requests = []
    if is_admin(request.user):
        pending_requests = FacultyUnavailability.objects.filter(
            status='pending'
        ).select_related('faculty', 'timetable_entry__course', 'timetable_entry__timeslot')

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'pending_requests': pending_requests,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'scheduler/notifications.html', context)
