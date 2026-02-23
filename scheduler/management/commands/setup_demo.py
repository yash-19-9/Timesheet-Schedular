"""
management/commands/setup_demo.py
Management command to create demo data for hackathon demonstration.

Usage: python manage.py setup_demo
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import time
from scheduler.models import Faculty, Course, Classroom, TimeSlot


class Command(BaseCommand):
    help = 'Set up demo data for the AI Faculty Scheduling System'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Setting up demo data...\n')

        # ── 1. Admin User ──────────────────────────────────────────────────
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@college.edu', 'admin123')
            self.stdout.write('  ✅ Admin user created: admin / admin123')
        else:
            self.stdout.write('  ℹ️  Admin user already exists')

        # ── 2. Faculty ────────────────────────────────────────────────────
        faculty_data = [
            {'name': 'Dr. Anjali Sharma',    'subjects': 'Mathematics,Statistics',          'max_hours': 18, 'dept': 'Science',    'eid': 'F001'},
            {'name': 'Prof. Ravi Kumar',     'subjects': 'Physics,Engineering Mechanics',   'max_hours': 20, 'dept': 'Engineering','eid': 'F002'},
            {'name': 'Dr. Priya Menon',      'subjects': 'Computer Science,Data Structures','max_hours': 16, 'dept': 'IT',         'eid': 'F003'},
            {'name': 'Mr. Suresh Patil',     'subjects': 'Chemistry,Environmental Science', 'max_hours': 20, 'dept': 'Science',    'eid': 'F004'},
            {'name': 'Dr. Fatima Sheikh',    'subjects': 'English,Communication Skills',    'max_hours': 14, 'dept': 'Humanities', 'eid': 'F005'},
            {'name': 'Prof. Arjun Nair',     'subjects': 'Electronics,VLSI Design',         'max_hours': 18, 'dept': 'Engineering','eid': 'F006'},
        ]

        for fd in faculty_data:
            username = fd['name'].lower().replace(' ', '_').replace('.', '')
            user, _ = User.objects.get_or_create(username=username)
            user.set_password('faculty123')
            user.first_name = fd['name'].split()[0] if fd['name'] else ''
            user.save()
            f, created = Faculty.objects.update_or_create(
                employee_id=fd['eid'],
                defaults={
                    'user': user,
                    'name': fd['name'],
                    'subjects': fd['subjects'],
                    'max_hours': fd['max_hours'],
                    'department': fd['dept'],
                    'is_active': True,
                }
            )
            status = 'created' if created else 'updated'
            self.stdout.write(f'  ✅ Faculty {status}: {fd["name"]} (username: {username}, pass: faculty123)')

        # ── 3. Courses ────────────────────────────────────────────────────
        courses_data = [
            {'name': 'Mathematics',           'code': 'MATH101', 'hours': 4, 'dept': 'Science',    'sem': 1},
            {'name': 'Physics',               'code': 'PHY101',  'hours': 3, 'dept': 'Engineering','sem': 1},
            {'name': 'Computer Science',      'code': 'CS101',   'hours': 4, 'dept': 'IT',         'sem': 1},
            {'name': 'Data Structures',       'code': 'CS201',   'hours': 4, 'dept': 'IT',         'sem': 2},
            {'name': 'Chemistry',             'code': 'CHEM101', 'hours': 3, 'dept': 'Science',    'sem': 1},
            {'name': 'English',               'code': 'ENG101',  'hours': 2, 'dept': 'Humanities', 'sem': 1},
            {'name': 'Statistics',            'code': 'STAT101', 'hours': 3, 'dept': 'Science',    'sem': 2},
            {'name': 'Electronics',           'code': 'ELE201',  'hours': 4, 'dept': 'Engineering','sem': 2},
        ]

        for cd in courses_data:
            Course.objects.update_or_create(
                course_code=cd['code'],
                defaults={
                    'course_name': cd['name'],
                    'hours_required': cd['hours'],
                    'department': cd['dept'],
                    'semester': cd['sem'],
                    'is_active': True,
                }
            )
        self.stdout.write(f'  ✅ {len(courses_data)} courses created/updated')

        # ── 4. Classrooms ─────────────────────────────────────────────────
        rooms_data = [
            {'name': 'Room 101', 'cap': 60, 'bldg': 'Block A', 'type': 'lecture'},
            {'name': 'Room 102', 'cap': 60, 'bldg': 'Block A', 'type': 'lecture'},
            {'name': 'Room 201', 'cap': 80, 'bldg': 'Block B', 'type': 'lecture'},
            {'name': 'Lab 001',  'cap': 30, 'bldg': 'Block C', 'type': 'lab'},
            {'name': 'Lab 002',  'cap': 30, 'bldg': 'Block C', 'type': 'lab'},
            {'name': 'Seminar A','cap': 40, 'bldg': 'Block D', 'type': 'seminar'},
        ]

        for rd in rooms_data:
            Classroom.objects.update_or_create(
                room_name=rd['name'],
                defaults={
                    'capacity': rd['cap'],
                    'building': rd['bldg'],
                    'room_type': rd['type'],
                    'is_available': True,
                }
            )
        self.stdout.write(f'  ✅ {len(rooms_data)} classrooms created/updated')

        # ── 5. Time Slots (Mon–Sat, 8 periods) ───────────────────────────
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        periods = [
            (1, time(8,  0), time(9,  0),  'Period 1'),
            (2, time(9,  0), time(10, 0),  'Period 2'),
            (3, time(10, 0), time(11, 0),  'Period 3'),
            (4, time(11, 0), time(12, 0),  'Period 4'),
            (5, time(13, 0), time(14, 0),  'Period 5'),
            (6, time(14, 0), time(15, 0),  'Period 6'),
            (7, time(15, 0), time(16, 0),  'Period 7'),
            (8, time(16, 0), time(17, 0),  'Period 8'),
        ]

        slot_count = 0
        for day in days:
            for period_num, start, end, label in periods:
                _, created = TimeSlot.objects.get_or_create(
                    day=day, period=period_num,
                    defaults={'start_time': start, 'end_time': end, 'label': label}
                )
                if created:
                    slot_count += 1
        self.stdout.write(f'  ✅ {slot_count} timeslots created ({len(days)} days × {len(periods)} periods)')

        self.stdout.write(self.style.SUCCESS('\n✅ Demo setup complete! Run the optimizer from the dashboard.'))
        self.stdout.write('\n📋 Login credentials:')
        self.stdout.write('  Admin:   admin / admin123  → http://127.0.0.1:8000/dashboard/')
        self.stdout.write('  Faculty: dr._anjali_sharma / faculty123')
        self.stdout.write('  Faculty: prof._ravi_kumar  / faculty123')
