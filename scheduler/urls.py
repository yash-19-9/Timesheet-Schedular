"""
urls.py - App-level URL routing
AI-Based Intelligent Faculty Workload and Scheduling System
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Auth ─────────────────────────────────────────────────────────────────
    path('login/',   views.login_view,   name='login'),
    path('logout/',  views.logout_view,  name='logout'),

    # ── Core pages ────────────────────────────────────────────────────────────
    path('',          views.dashboard,     name='home'),
    path('dashboard/', views.dashboard,    name='dashboard'),
    path('timetable/', views.timetable_view, name='timetable'),
    path('data/',      views.manage_data,  name='manage_data'),

    # ── Excel Upload ──────────────────────────────────────────────────────────
    path('upload/',             views.upload_page,       name='upload_page'),
    path('upload/faculty/',     views.upload_faculty,    name='upload_faculty'),
    path('upload/courses/',     views.upload_courses,    name='upload_courses'),
    path('upload/classrooms/',  views.upload_classrooms, name='upload_classrooms'),

    # ── Optimizer ─────────────────────────────────────────────────────────────
    path('optimize/', views.run_optimization, name='run_optimization'),

    # ── PDF Exports ───────────────────────────────────────────────────────────
    path('export/timetable/',             views.export_timetable_pdf, name='export_timetable_pdf'),
    path('export/workload/',              views.export_workload_pdf,  name='export_workload_pdf'),
    path('export/faculty/<int:faculty_id>/', views.export_faculty_pdf, name='export_faculty_pdf'),

    # ── API ───────────────────────────────────────────────────────────────────
    path('api/workload/',                         views.api_workload_data,            name='api_workload_data'),
    path('api/notifications/',                    views.api_notifications,            name='api_notifications'),
    path('api/notifications/<int:notif_id>/read/', views.mark_notification_read,      name='mark_notification_read'),

    # ── Unavailability & Reassignment ─────────────────────────────────────────
    path('unavailable/<int:entry_id>/',           views.mark_unavailable,             name='mark_unavailable'),
    path('reassign/<int:unavail_id>/',            views.reassign_faculty,             name='reassign_faculty'),

    # ── Notifications ─────────────────────────────────────────────────────────
    path('notifications/',                        views.notifications_page,           name='notifications_page'),
    path('notifications/read-all/',               views.mark_all_notifications_read,  name='mark_all_read'),
]
