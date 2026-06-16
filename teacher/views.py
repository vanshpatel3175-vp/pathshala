from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from .models import TeacherProfile

User = get_user_model()


def get_teacher_profile(user):
    try:
        return user.teacher_profile
    except TeacherProfile.DoesNotExist:
        return None


def teacher_required(view_func):
    """Decorator: only TEACHER role users with a TeacherProfile can access."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        # Check active session for dual-role users
        if hasattr(request.user, 'teacher_profile') and hasattr(request.user, 'student_profile'):
            if request.session.get('active_role') != 'TEACHER':
                return redirect('select_profile')
        elif request.user.role != 'TEACHER':
            messages.error(request, "Access denied. Teacher accounts only.")
            return redirect('login')
        profile = get_teacher_profile(request.user)
        if not profile:
            messages.error(request, "Teacher profile not found.")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def teacher_login_view(request):
    """Fallback redirect to main login page."""
    return redirect('login')


def teacher_logout_view(request):
    logout(request)
    return redirect('login')


@teacher_required
def teacher_dashboard_view(request):
    profile = get_teacher_profile(request.user)
    teacher = profile.teacher
    school_user = teacher.school_user if teacher else None
    institution = teacher.branch.institution if teacher else None
    branch = teacher.branch if teacher else None

    context = {
        'profile': profile,
        'teacher': teacher,
        'school_user': school_user,
        'institution': institution,
        'branch': branch,
        'current_tab': 'dashboard',
    }
    return render(request, 'teacher/dashboard.html', context)


@teacher_required
def teacher_profile_view(request):
    profile = get_teacher_profile(request.user)
    teacher = profile.teacher
    school_user = teacher.school_user if teacher else None
    institution = teacher.branch.institution if teacher else None
    branch = teacher.branch if teacher else None

    context = {
        'profile': profile,
        'teacher': teacher,
        'school_user': school_user,
        'institution': institution,
        'branch': branch,
        'current_tab': 'profile',
    }
    return render(request, 'teacher/profile.html', context)
