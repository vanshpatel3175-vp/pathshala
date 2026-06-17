from django.urls import path
from . import views

urlpatterns = [
    path('', views.school_overview_view, name='school_overview'),
    path('signup/', views.school_signup_view, name='school_signup'),
    path('logout/', views.school_logout_view, name='school_logout'),
    path('overview/', views.school_overview_view, name='school_overview'),
    path('branches/', views.school_branches_view, name='school_branches'),
    path('roles/', views.school_roles_view, name='school_roles'),
    path('students/', views.school_students_view, name='school_students'),
    path('teachers/', views.school_teachers_view, name='school_teachers'),
    path('others/', views.school_others_view, name='school_others'),
    path('mediums/', views.school_mediums_view, name='school_mediums'),
    path('classes/', views.school_classes_view, name='school_classes'),
    path('profile/', views.school_profile_view, name='school_profile'),
    path('manage/', views.school_manage_view, name='school_manage'),
    path('users/', views.school_users_view, name='school_users'),
    path('api/branch-request-status/', views.branch_request_status_api, name='branch_request_status_api'),
    path('api/user-lookup/', views.school_user_lookup_api, name='school_user_lookup_api'),
    path('api/classes-by-branch/', views.classes_by_branch_api, name='classes_by_branch_api'),
    path('attendance/', views.school_attendance_view, name='school_attendance'),
]
