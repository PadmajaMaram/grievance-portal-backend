
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import hashlib
import uuid
from .models import (
    User,
    Complaint,
    SupervisorRegistration,
    SupervisorLoginRequest,
)
import json
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


def complaint_to_dict(complaint):
    return {
        "id": complaint.id,
        "title": complaint.title,
        "description": complaint.description,
        "department": complaint.department,
        "priority": complaint.priority,
        "summary": complaint.summary,
        "status": complaint.status,
        "created_at": complaint.created_at.isoformat(),
        "updated_at": complaint.updated_at.isoformat(),
        "attachments": complaint.attachments,
    }


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def analyze_complaint(complaint_text):
    """
    Simple NLP analysis for complaint categorization, priority, and summary.
    In a real system, this would use OpenAI API or advanced ML models.
    """
    text = complaint_text.lower()
    
    # Category identification based on keywords
    categories = {
        'Water': ['water', 'leak', 'pipe', 'drain', 'flood', 'sewage', 'plumbing'],
        'Electricity': ['electric', 'power', 'light', 'outage', 'voltage', 'cable', 'bulb'],
        'Roads': ['road', 'pothole', 'street', 'traffic', 'pavement', 'construction'],
        'Sanitation': ['garbage', 'waste', 'trash', 'clean', 'hygiene', 'sewage'],
        'Public Safety': ['crime', 'police', 'safety', 'emergency', 'accident', 'fire'],
    }
    
    category = 'Others'
    for cat, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            category = cat
            break
    
    # Priority based on keywords
    high_keywords = ['urgent', 'emergency', 'danger', 'broken', 'no water', 'no power', 'flood', 'fire', 'accident']
    medium_keywords = ['problem', 'issue', 'not working', 'delay', 'noise', 'dirty']
    
    if any(keyword in text for keyword in high_keywords):
        priority = 'high'
    elif any(keyword in text for keyword in medium_keywords):
        priority = 'medium'
    else:
        priority = 'low'
    
    # Simple summary: first sentence or truncated text
    sentences = complaint_text.split('.')
    summary = sentences[0].strip() if sentences[0] else complaint_text[:100] + '...'
    
    return {
        'category': category,
        'priority': priority.capitalize() + ' Priority',  # But in model it's 'high', 'medium', 'low'
        'summary': summary
    }


def supervisor_request_to_dict(request_obj):
    return {
        "id": str(request_obj.id),
        "email": request_obj.supervisor.email,
        "status": request_obj.status,
        "requested_at": request_obj.requested_at.isoformat(),
        "approved_at": request_obj.approved_at.isoformat() if request_obj.approved_at else None,
        "expires_at": request_obj.expires_at.isoformat() if request_obj.expires_at else None,
    }


def send_admin_notification(request_obj):
    recipients = getattr(settings, "ADMIN_EMAILS", [settings.EMAIL_HOST_USER])
    subject = f"Supervisor Access Request: {request_obj.supervisor.email}"
    message = f"A supervisor has requested access to the portal.\n\n"
    message += f"Supervisor Email: {request_obj.supervisor.email}\n"
    message += f"Request ID: {request_obj.id}\n"
    message += f"Requested At: {request_obj.requested_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    message += "Please approve or reject this request from the admin dashboard."
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=True,
    )


def send_supervisor_decision_notification(request_obj, approved):
    subject = (
        f"Supervisor Access Approved - {request_obj.supervisor.email}"
        if approved
        else f"Supervisor Access Rejected - {request_obj.supervisor.email}"
    )
    decision_text = "approved" if approved else "rejected"
    message = f"Your supervisor access request has been {decision_text}.\n\n"
    message += f"Supervisor Email: {request_obj.supervisor.email}\n"
    if approved:
        message += f"Your access is valid until {request_obj.expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC.\n"
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[request_obj.supervisor.email],
        fail_silently=True,
    )


@csrf_exempt
def login_user(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return JsonResponse({
                    "status": "error",
                    "message": "Email and password are required"
                })

            try:
                user = User.objects.get(email=email)
                if user.password == password:
                    return JsonResponse({
                        "status": "success",
                        "message": "Login successful",
                        "name": user.name
                    })
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid credentials"
                })
            except User.DoesNotExist:
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid credentials"
                })
        except json.JSONDecodeError:
            return JsonResponse({
                "status": "error",
                "message": "Invalid JSON"
            })

    return JsonResponse({"message": "Only POST allowed"})


@csrf_exempt
def signup_user(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            name = data.get("name")
            email = data.get("email")
            password = data.get("password")

            if not name or not email or not password:
                return JsonResponse({
                    "status": "error",
                    "message": "All fields are required"
                })

            if User.objects.filter(email=email).exists():
                return JsonResponse({
                    "status": "error",
                    "message": "Email already exists"
                })

            user = User.objects.create(
                name=name,
                email=email,
                password=password
            )

            return JsonResponse({
                "status": "success",
                "message": "Account created successfully",
                "name": user.name
            })
        except json.JSONDecodeError:
            return JsonResponse({
                "status": "error",
                "message": "Invalid JSON"
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e)
            })

    return JsonResponse({"message": "Only POST allowed"})


@csrf_exempt
def supervisor_request_access(request):
    if request.method != "POST":
        return JsonResponse({"message": "Only POST allowed"})

    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return JsonResponse({
                "status": "error",
                "message": "Email and password are required to request access"
            })

        password_hash = hash_password(password)
        supervisor, created = SupervisorRegistration.objects.get_or_create(
            email=email,
            defaults={
                "password_hash": password_hash,
                "department": "General",
                "status": "pending",
            },
        )

        if not created and supervisor.password_hash != password_hash:
            supervisor.password_hash = password_hash
            supervisor.save(update_fields=["password_hash"])

        existing_request = SupervisorLoginRequest.objects.filter(
            supervisor=supervisor,
            status="pending",
        ).order_by("-requested_at").first()

        if existing_request and existing_request.expires_at and existing_request.expires_at > timezone.now():
            return JsonResponse({
                "status": "success",
                "message": "A supervisor request is already pending approval. Please wait for admin response.",
                "request_id": str(existing_request.id),
            })

        login_request = SupervisorLoginRequest.objects.create(
            supervisor=supervisor,
            approval_token=uuid.uuid4().hex,
            status="pending",
            expires_at=timezone.now() + timedelta(hours=2),
            ip_address=request.META.get("REMOTE_ADDR", ""),
            device_info=request.META.get("HTTP_USER_AGENT", ""),
        )

        send_admin_notification(login_request)

        return JsonResponse({
            "status": "success",
            "message": "Your request has been sent to admin for approval.",
            "request_id": str(login_request.id),
        })
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON"
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        })


@csrf_exempt
def supervisor_login(request):
    if request.method != "POST":
        return JsonResponse({"message": "Only POST allowed"})

    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return JsonResponse({
                "status": "error",
                "message": "Email and password are required"
            })

        try:
            supervisor = SupervisorRegistration.objects.get(email=email)
        except SupervisorRegistration.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Invalid credentials"
            })

        if supervisor.password_hash != hash_password(password):
            return JsonResponse({
                "status": "error",
                "message": "Invalid credentials"
            })

        login_request = SupervisorLoginRequest.objects.filter(
            supervisor=supervisor,
            status="approved",
        ).order_by("-approved_at").first()

        if not login_request:
            return JsonResponse({
                "status": "error",
                "message": "Access not approved yet. Please send a request and wait for admin approval."
            })

        if not login_request.is_valid():
            return JsonResponse({
                "status": "error",
                "message": "Your approved access request has expired. Please request access again."
            })

        return JsonResponse({
            "status": "success",
            "message": "Login successful",
            "session_token": login_request.session_token,
        })
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON"
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        })


@csrf_exempt
def supervisor_logout(request):
    if request.method != "POST":
        return JsonResponse({"message": "Only POST allowed"})

    try:
        data = json.loads(request.body)
        session_token = data.get("session_token", "")

        if session_token:
            try:
                login_request = SupervisorLoginRequest.objects.get(
                    session_token=session_token,
                    status="approved",
                )
                login_request.status = "expired"
                login_request.save(update_fields=["status"])
            except SupervisorLoginRequest.DoesNotExist:
                pass

        return JsonResponse({
            "status": "success",
            "message": "Logged out successfully"
        })
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON"
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        })


def admin_supervisor_requests(request):
    if request.method != "GET":
        return JsonResponse({"message": "Only GET allowed"})

    requests = SupervisorLoginRequest.objects.order_by("-requested_at")
    return JsonResponse({
        "status": "success",
        "requests": [supervisor_request_to_dict(r) for r in requests],
    })


@csrf_exempt
def admin_review_supervisor_request(request, request_id):
    if request.method != "POST":
        return JsonResponse({"message": "Only POST allowed"})

    try:
        data = json.loads(request.body)
        action = data.get("action")

        if action not in ["approve", "reject"]:
            return JsonResponse({
                "status": "error",
                "message": "Action must be approve or reject"
            })

        try:
            login_request = SupervisorLoginRequest.objects.get(id=request_id)
        except SupervisorLoginRequest.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Supervisor request not found"
            }, status=404)

        if login_request.status != "pending":
            return JsonResponse({
                "status": "error",
                "message": "This request has already been processed"
            })

        if action == "approve":
            login_request.status = "approved"
            login_request.session_token = uuid.uuid4().hex
            login_request.approved_at = timezone.now()
            login_request.expires_at = timezone.now() + timedelta(hours=1)
            login_request.save(update_fields=["status", "session_token", "approved_at", "expires_at"])
            send_supervisor_decision_notification(login_request, approved=True)
            message = "Supervisor access request approved."
        else:
            login_request.status = "rejected"
            login_request.approved_at = timezone.now()
            login_request.session_token = ""
            login_request.save(update_fields=["status", "approved_at", "session_token"])
            send_supervisor_decision_notification(login_request, approved=False)
            message = "Supervisor access request rejected."

        return JsonResponse({
            "status": "success",
            "message": message,
        })
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON"
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        })


@csrf_exempt
def create_complaint(request):
    if request.method == "GET":
        user_email = request.GET.get("user_email")
        department = request.GET.get("department")

        if user_email:
            try:
                user = User.objects.get(email=user_email)
            except User.DoesNotExist:
                return JsonResponse({
                    "status": "error",
                    "message": "User not found"
                }, status=404)
            complaints = Complaint.objects.filter(user=user)
        else:
            complaints = Complaint.objects.all()

        if department:
            complaints = complaints.filter(department__iexact=department)

        complaints = complaints.order_by("-created_at")
        return JsonResponse({
            "status": "success",
            "complaints": [complaint_to_dict(c) for c in complaints]
        })

    if request.method == "POST":
        try:
            title = request.POST.get("title")
            description = request.POST.get("description")
            department = request.POST.get("department", "General")
            user_email = request.POST.get("user_email")

            if not title or not description or not user_email:
                return JsonResponse({
                    "status": "error",
                    "message": "Title, description, and user email are required"
                })

            try:
                user = User.objects.get(email=user_email)
            except User.DoesNotExist:
                return JsonResponse({
                    "status": "error",
                    "message": "User not found"
                }, status=404)

            # Analyze complaint using NLP
            analysis = analyze_complaint(description)
            department = analysis['category']  # Override with analyzed category
            priority = analysis['priority'].lower().split()[0]  # 'high', 'medium', 'low'
            summary = analysis['summary']

            attachments = []
            for key, file in request.FILES.items():
                file_name = f"complaints/{user.id}/{file.name}"
                file_path = default_storage.save(file_name, ContentFile(file.read()))
                attachments.append({
                    "name": file.name,
                    "path": file_path,
                    "size": file.size,
                    "type": file.content_type,
                })

            complaint = Complaint.objects.create(
                title=title,
                description=description,
                department=department,
                priority=priority,
                summary=summary,
                user=user,
                attachments=attachments,
            )

            try:
                subject = f"Complaint Submitted Successfully - #{complaint.id}"
                message = f"""
Dear {user.name},

Your complaint has been submitted successfully!

Complaint Details:
- Complaint ID: #{complaint.id}
- Title: {title}
- Description: {description}
- Status: Pending
- Submitted on: {complaint.created_at.strftime('%B %d, %Y at %I:%M %p')}

Attachments: {len(attachments)} file(s) uploaded

You can track the status of your complaint by logging into your account.

Thank you for using our Complaint Portal!

Best regards,
Complaint Portal Team
                """
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception as email_error:
                print(f"Email sending failed: {email_error}")

            return JsonResponse({
                "status": "success",
                "message": "Complaint created successfully",
                "complaint_id": complaint.id,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e)
            })

    return JsonResponse({"message": "Only GET and POST allowed"})


def complaint_detail(request, complaint_id):
    if request.method != "GET":
        return JsonResponse({"message": "Only GET allowed"})

    try:
        complaint = Complaint.objects.get(id=complaint_id)
    except Complaint.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "Complaint not found"
        }, status=404)

    return JsonResponse({
        "status": "success",
        "complaint": complaint_to_dict(complaint),
    })
