#!/usr/bin/env python
import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from users.models import Complaint

# Get the first two complaints
complaints = Complaint.objects.all()[:2]

if len(complaints) >= 2:
    complaints[0].location = 'Mumbai, India'
    complaints[0].save()
    complaints[1].location = 'Delhi, India'
    complaints[1].save()
    print('Updated locations for two complaints')
else:
    print('Not enough complaints to update')