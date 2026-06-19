from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from .models import StudentProfile

def get_student_profile(user):
    try:
        return user.student_profile
    except StudentProfile.DoesNotExist:
        return None

def student_required(view_func):
    """Decorator: only STUDENT role users with a StudentProfile can access."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        # Check active session for dual-role users
        if hasattr(request.user, 'teacher_profile') and hasattr(request.user, 'student_profile'):
            if request.session.get('active_role') != 'STUDENT':
                return redirect('select_profile')
        elif request.user.role != 'STUDENT':
            messages.error(request, "Access denied. Student accounts only.")
            return redirect('login')
        profile = get_student_profile(request.user)
        if not profile:
            messages.error(request, "Student profile not found.")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper

def student_login_view(request):
    """Fallback redirect to main login page."""
    return redirect('login')

def student_logout_view(request):
    logout(request)
    return redirect('login')

@student_required
def student_dashboard_view(request):
    profile = get_student_profile(request.user)
    student = profile.student if profile else None
    school_user = student.school_user if student else None
    institution = student.branch.institution if student else None
    branch = student.branch if student else None
    school_class = student.school_class if student else None
    class_teacher = school_class.teacher if school_class else None

    context = {
        'profile': profile,
        'student': student,
        'school_user': school_user,
        'institution': institution,
        'branch': branch,
        'school_class': school_class,
        'class_teacher': class_teacher,
        'current_tab': 'dashboard',
    }
    return render(request, 'student/dashboard.html', context)

@student_required
def student_profile_view(request):
    profile = get_student_profile(request.user)
    student = profile.student if profile else None
    school_user = student.school_user if student else None
    institution = student.branch.institution if student else None
    branch = student.branch if student else None

    context = {
        'profile': profile,
        'student': student,
        'school_user': school_user,
        'institution': institution,
        'branch': branch,
        'current_tab': 'profile',
    }
    return render(request, 'student/profile.html', context)

@student_required
def student_attendance_view(request):
    profile = get_student_profile(request.user)
    student = profile.student if profile else None
    
    from school_admin.models import Attendance
    
    # Get attendance records for this student, ordered by date descending
    attendance_records = Attendance.objects.filter(student=student).order_by('-date') if student else []
    
    context = {
        'student': student,
        'institution': student.branch.institution if student else None,
        'attendance_records': attendance_records,
        'current_tab': 'attendance',
    }
    return render(request, 'student/attendance.html', context)


@student_required
def student_result_view(request):
    profile = get_student_profile(request.user)
    student = profile.student if profile else None
    context = {
        'student': student,
        'institution': student.branch.institution if student else None,
        'current_tab': 'result',
    }
    return render(request, 'student/result.html', context)


@student_required
def student_holidays_view(request):
    """Student views holidays for their branch."""
    profile = get_student_profile(request.user)
    student = profile.student if profile else None
    branch = student.branch if student else None
    institution = student.branch.institution if student else None

    from school_admin.models import Holiday
    from django.db.models import Q
    holidays = []
    if branch and institution:
        holidays = Holiday.objects.filter(
            institution=institution
        ).filter(
            Q(branch=branch) | Q(branch__isnull=True)
        ).order_by('start_date')

    context = {
        'student': student,
        'profile': profile,
        'institution': institution,
        'branch': branch,
        'holidays': holidays,
        'current_tab': 'holidays',
    }
    return render(request, 'student/holidays.html', context)


@student_required
def student_events_view(request):
    """Student views events for their branch."""
    profile = get_student_profile(request.user)
    student = profile.student if profile else None
    branch = student.branch if student else None
    institution = student.branch.institution if student else None

    from school_admin.models import Event
    from django.db.models import Q
    events = []
    if branch and institution:
        events = Event.objects.filter(
            institution=institution
        ).filter(
            Q(branch=branch) | Q(branch__isnull=True)
        ).order_by('start_date')

    context = {
        'student': student,
        'profile': profile,
        'institution': institution,
        'branch': branch,
        'events': events,
        'current_tab': 'events',
    }
    return render(request, 'student/events.html', context)

