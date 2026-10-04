from django.urls import path
from .views import (
    login_user,
    signup_user,
    create_complaint,
    complaint_detail,
    supervisor_request_access,
    supervisor_login,
    supervisor_logout,
    admin_supervisor_requests,
    admin_review_supervisor_request,
)

urlpatterns = [
    path('login/', login_user),
    path('signup/', signup_user),
    path('complaints/', create_complaint),
    path('complaints/<int:complaint_id>/', complaint_detail),
    path('supervisor/request-access/', supervisor_request_access),
    path('supervisor/login/', supervisor_login),
    path('supervisor/logout/', supervisor_logout),
    path('admin/supervisor-requests/', admin_supervisor_requests),
    path('admin/supervisor-requests/<uuid:request_id>/', admin_review_supervisor_request),
]