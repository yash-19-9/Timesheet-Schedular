"""
Project-level URL configuration
AI-Based Intelligent Faculty Workload and Scheduling System
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('scheduler.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom admin site headers
admin.site.site_header = "Faculty Scheduling System - Admin"
admin.site.site_title = "Faculty Scheduling Admin"
admin.site.index_title = "Welcome to the Scheduling Admin Panel"
