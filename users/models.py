from django.db import models
import uuid
from django.utils import timezone

class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.email
    
    class Meta:
        app_label = 'users'

class Complaint(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='complaints')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    department = models.CharField(max_length=50, default='General')
    priority = models.CharField(max_length=20, choices=[
        ('high', 'High Priority'),
        ('medium', 'Medium Priority'),
        ('low', 'Low Priority'),
    ], default='medium')
    summary = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.title} - {self.user.email}"

    class Meta:
        app_label = 'users'
        ordering = ['-created_at']


class SupervisorRegistration(models.Model):
    """Permanent registration of supervisors"""
    STATUS_CHOICES = [
        ('pending', 'Pending Admin Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('blocked', 'Blocked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    department = models.CharField(max_length=100, default='General')
    phone = models.CharField(max_length=15, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    registered_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'users'
        ordering = ['-registered_at']
    def __str__(self):
        return f"{self.email} - {self.status}"


class SupervisorLoginRequest(models.Model):
    """Temporary login request for each session"""
    STATUS_CHOICES = [
        ('pending', 'Waiting for Admin Approval'),
        ('approved', 'Approved - Can Login'),
        ('rejected', 'Rejected'),
        ('expired', 'Request Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supervisor = models.ForeignKey(SupervisorRegistration, on_delete=models.CASCADE, related_name='login_requests')
    approval_token = models.CharField(max_length=255, unique=True)
    session_token = models.CharField(max_length=255, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    ip_address = models.CharField(max_length=45, blank=True)
    device_info = models.CharField(max_length=255, blank=True)
    
    class Meta:
        app_label = 'users'
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.supervisor.email} - {self.status}"
    
    def is_valid(self):
        """Check if request is still valid"""
        if self.status != 'approved':
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            self.status = 'expired'
            self.save()
            return False
        return True