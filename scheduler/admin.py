"""
admin.py - Register all models for Django Admin panel
"""

from django.contrib import admin
from .models import Faculty, Course, Classroom, TimeSlot, TimetableEntry, WorkloadLog, ScheduleVersion


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ['name', 'employee_id', 'department', 'subjects', 'max_hours', 'is_active']
    list_filter = ['department', 'is_active']
    search_fields = ['name', 'employee_id', 'subjects']
    list_editable = ['max_hours', 'is_active']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['course_code', 'course_name', 'department', 'semester', 'hours_required', 'assigned_faculty']
    list_filter = ['department', 'semester']
    search_fields = ['course_name', 'course_code']
    list_editable = ['hours_required']


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ['room_name', 'building', 'capacity', 'room_type', 'is_available']
    list_filter = ['room_type', 'is_available', 'building']
    list_editable = ['is_available']


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['day', 'period', 'start_time', 'end_time', 'label']
    list_filter = ['day']
    ordering = ['day', 'period']


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ['faculty', 'course', 'classroom', 'timeslot', 'schedule_version', 'generated_at']
    list_filter = ['schedule_version', 'faculty', 'timeslot__day']
    search_fields = ['faculty__name', 'course__course_name']


@admin.register(WorkloadLog)
class WorkloadLogAdmin(admin.ModelAdmin):
    list_display = ['faculty', 'schedule_version', 'assigned_hours', 'max_hours', 'utilization_percent']
    list_filter = ['schedule_version']


@admin.register(ScheduleVersion)
class ScheduleVersionAdmin(admin.ModelAdmin):
    list_display = ['version_number', 'status', 'total_assignments', 'is_active', 'created_at']
    list_filter = ['status', 'is_active']
    actions = ['mark_active']

    def mark_active(self, request, queryset):
        ScheduleVersion.objects.all().update(is_active=False)
        queryset.update(is_active=True)
        self.message_user(request, "Selected schedule version marked as active.")
    mark_active.short_description = "Set as active timetable"
