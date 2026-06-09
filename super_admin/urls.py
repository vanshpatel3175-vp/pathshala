from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('review/<int:app_id>/', views.review_application_view, name='review_application'),
    path('review/approve/<int:app_id>/', views.approve_application_view, name='approve_application'),
    path('review/decline/<int:app_id>/', views.decline_application_view, name='decline_application'),
    path('institutions/', views.all_institutions_view, name='all_institutions'),
    path('institutions/toggle/<int:inst_id>/', views.toggle_institution_view, name='toggle_institution'),
    path('users/', views.platform_users_view, name='platform_users'),
    path('inquiry/', views.inquiries_view, name='inquiries'),
    path('inquiry/view/<int:inq_id>/', views.inquiry_details_view, name='inquiry_details'),
    path('inquiry/review/<int:inq_id>/', views.inquiry_review_view, name='inquiry_review'),
    path('inquiry/review/<int:inq_id>/status/', views.inquiry_update_status_view, name='inquiry_update_status'),
    path('inquiry/review/<int:inq_id>/meeting/add/', views.inquiry_add_meeting_view, name='inquiry_add_meeting'),
    path('branch-requests/', views.branch_requests_view, name='branch_requests'),
    path('branch-requests/approve/<int:req_id>/', views.approve_branch_request_view, name='approve_branch_request'),
    path('branch-requests/reject/<int:req_id>/', views.reject_branch_request_view, name='reject_branch_request'),
]
