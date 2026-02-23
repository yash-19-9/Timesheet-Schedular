"""
models.py - AI-Based Intelligent Faculty Workload and Scheduling System

Database Schema:
- Faculty: Stores faculty details linked to Django User
- Course: Subjects/courses to be scheduled
- Classroom: Available rooms
- TimeSlot: Days and periods (time grid)
- TimetableEntry: Final scheduled assignment (Faculty + Course + Room + Slot)
- WorkloadLog: Tracks actual hours assigned per faculty
"""

from django.db import models
from django.contrib.auth.models import User


class Faculty(models.Model):
    """
    Represents a faculty member.
    Linked to Django's User model for authentication.
    max_hours: maximum teaching hours allowed per week
    subjects: comma-separated subjects the faculty can teach
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=150)
    employee_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    subjects = models.TextField(help_text="Comma-separated list of subjects this faculty can teach")
    max_hours = models.PositiveIntegerField(default=20, help_text="Max teaching hours per week")
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Faculty"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.department})"

    def get_subjects_list(self):
        return [s.strip() for s in self.subjects.split(',') if s.strip()]

    def can_teach(self, subject):
        return subject.strip().lower() in [s.lower() for s in self.get_subjects_list()]


class Course(models.Model):
    """
    Represents a course/subject to be scheduled.
    hours_required: total weekly hours needed for this course
    assigned_faculty: the faculty assigned (can be null before optimization)
    """
    course_name = models.CharField(max_length=200)
    course_code = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    semester = models.PositiveIntegerField(default=1)
    hours_required = models.PositiveIntegerField(default=4, help_text="Weekly hours required")
    assigned_faculty = models.ForeignKey(
        Faculty, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['course_name']

    def __str__(self):
        return f"{self.course_code} - {self.course_name}" if self.course_code else self.course_name


class Classroom(models.Model):
    """
    Represents a physical classroom/lab.
    capacity: number of students it can accommodate
    room_type: lecture hall, lab, seminar room, etc.
    """
    ROOM_TYPE_CHOICES = [
        ('lecture', 'Lecture Hall'),
        ('lab', 'Computer Lab'),
        ('seminar', 'Seminar Room'),
        ('tutorial', 'Tutorial Room'),
    ]

    room_name = models.CharField(max_length=100, unique=True)
    building = models.CharField(max_length=50, blank=True)
    capacity = models.PositiveIntegerField(default=60)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES, default='lecture')
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['room_name']

    def __str__(self):
        return f"{self.room_name} (Cap: {self.capacity})"


class TimeSlot(models.Model):
    """
    Represents a time slot in the weekly timetable.
    day: Monday-Saturday
    period: 1-8 (each ~1 hour)
    start_time / end_time: actual clock times
    """
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
    ]

    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    period = models.PositiveIntegerField(help_text="Period number (1-8)")
    start_time = models.TimeField()
    end_time = models.TimeField()
    label = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ('day', 'period')
        ordering = ['day', 'period']

    def __str__(self):
        return f"{self.day} - Period {self.period} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"


class TimetableEntry(models.Model):
    """
    Core scheduling result produced by LP Optimizer.
    Each entry = one class session:
    - Which faculty teaches
    - Which course
    - In which room
    - At which timeslot
    Uniqueness constraints prevent double-booking.
    """
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='timetable_entries')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='timetable_entries')
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='timetable_entries')
    timeslot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='timetable_entries')
    generated_at = models.DateTimeField(auto_now_add=True)
    schedule_version = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)

    class Meta:
        # Prevent double-booking: one faculty per slot, one room per slot
        unique_together = [
            ('faculty', 'timeslot', 'schedule_version'),
            ('classroom', 'timeslot', 'schedule_version'),
        ]
        ordering = ['timeslot__day', 'timeslot__period']

    def __str__(self):
        return f"{self.faculty.name} | {self.course.course_name} | {self.classroom.room_name} | {self.timeslot}"


class WorkloadLog(models.Model):
    """
    Tracks workload distribution per faculty per schedule version.
    Used for dashboard charts and fairness metrics.
    """
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='workload_logs')
    schedule_version = models.PositiveIntegerField(default=1)
    assigned_hours = models.PositiveIntegerField(default=0)
    max_hours = models.PositiveIntegerField(default=0)
    utilization_percent = models.FloatField(default=0.0)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('faculty', 'schedule_version')
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.faculty.name} - v{self.schedule_version} - {self.assigned_hours}h/{self.max_hours}h"


class ScheduleVersion(models.Model):
    """
    Tracks each run of the LP optimizer.
    Allows keeping history of generated timetables.
    """
    version_number = models.PositiveIntegerField(unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('running', 'Running'), ('success', 'Success'), ('failed', 'Failed')],
        default='pending'
    )
    solver_status = models.CharField(max_length=50, blank=True)
    total_assignments = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=False, help_text="Currently displayed timetable")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']

    def __str__(self):
        return f"Schedule v{self.version_number} [{self.status}]"


class FacultyUnavailability(models.Model):
    """
    Faculty raises a 'not free' flag on a specific timetable entry.
    Admin can then reassign the session to another faculty.
    """
    STATUS_CHOICES = [
        ('pending',    'Pending Review'),
        ('reassigned', 'Reassigned'),
        ('dismissed',  'Dismissed'),
    ]

    faculty = models.ForeignKey(
        Faculty, on_delete=models.CASCADE, related_name='unavailability_requests'
    )
    timetable_entry = models.ForeignKey(
        TimetableEntry, on_delete=models.CASCADE, related_name='unavailability_flags'
    )
    reason = models.TextField(blank=True, help_text="Optional reason for unavailability")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reassigned_to = models.ForeignKey(
        Faculty, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reassigned_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.faculty.name} - NOT FREE - {self.timetable_entry} [{self.status}]"


class Notification(models.Model):
    """
    In-app notification delivered to a user.
    Polled by the frontend every 15 seconds for Chrome browser notifications.
    """
    NOTIF_TYPES = [
        ('unavailability_request', 'Unavailability Request'),
        ('reassignment_done',      'Reassignment Done'),
        ('general',                'General'),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications'
    )
    sender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_notifications'
    )
    title = models.CharField(max_length=200, default='Notification')
    message = models.TextField()
    notif_type = models.CharField(max_length=30, choices=NOTIF_TYPES, default='general')
    is_read = models.BooleanField(default=False)
    related_entry = models.ForeignKey(
        TimetableEntry, on_delete=models.SET_NULL, null=True, blank=True
    )
    related_unavailability = models.ForeignKey(
        FacultyUnavailability, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notif_type}] → {self.recipient.username}: {self.title}"
