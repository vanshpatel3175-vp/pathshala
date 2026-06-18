from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from datetime import date as date_type
from .models import TeacherProfile
from school_admin.models import SchoolClass, Student, Attendance

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

    # Classes assigned to this teacher
    assigned_classes = SchoolClass.objects.filter(teacher=teacher).select_related('branch') if teacher else []
    total_students = Student.objects.filter(school_class__teacher=teacher).count() if teacher else 0

    # Attendance summary for today
    today = date_type.today()
    today_records = Attendance.objects.filter(teacher=teacher, date=today).count() if teacher else 0

    context = {
        'profile': profile,
        'teacher': teacher,
        'school_user': school_user,
        'institution': institution,
        'branch': branch,
        'assigned_classes': assigned_classes,
        'total_students': total_students,
        'today_records': today_records,
        'today': today,
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


@teacher_required
def teacher_attendance_view(request):
    """Teacher takes attendance for their assigned class on a selected date."""
    profile = get_teacher_profile(request.user)
    teacher = profile.teacher

    assigned_classes = SchoolClass.objects.filter(teacher=teacher).select_related('branch') if teacher else []

    today_str = str(date_type.today())
    selected_class_id = request.GET.get('class_id', '').strip()
    selected_date = request.GET.get('date', '').strip()
    if not selected_date:
        selected_date = today_str

    selected_class = None
    students = []
    existing_records = {}

    if selected_class_id:
        selected_class = get_object_or_404(SchoolClass, id=selected_class_id, teacher=teacher)
        students = Student.objects.filter(school_class=selected_class, status='active').order_by('name')
        # Load existing attendance for the selected date
        for att in Attendance.objects.filter(school_class=selected_class, date=selected_date):
            existing_records[att.student_id] = att

    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        att_date = request.POST.get('date', '').strip()
        if not att_date:
            att_date = today_str
        
        if att_date > today_str:
            messages.error(request, "You cannot mark attendance for future dates.")
            return redirect(f"{request.path}?class_id={class_id}&date={today_str}")

        cls = get_object_or_404(SchoolClass, id=class_id, teacher=teacher)
        class_students = Student.objects.filter(school_class=cls, status='active')

        saved = 0
        for student in class_students:
            status_val = request.POST.get(f'status_{student.id}', 'absent')
            note_val = request.POST.get(f'note_{student.id}', '').strip()
            att, created = Attendance.objects.update_or_create(
                school_class=cls,
                student=student,
                date=att_date,
                defaults={
                    'teacher': teacher,
                    'status': status_val,
                    'note': note_val,
                }
            )
            saved += 1

        messages.success(request, f"Attendance saved for {saved} student(s) on {att_date}.")
        return redirect(f"{request.path}?class_id={class_id}&date={att_date}")

    context = {
        'profile': profile,
        'teacher': teacher,
        'institution': teacher.branch.institution if teacher else None,
        'branch': teacher.branch if teacher else None,
        'assigned_classes': assigned_classes,
        'selected_class': selected_class,
        'selected_date': selected_date,
        'today_str': today_str,
        'students': students,
        'existing_records': existing_records,
        'current_tab': 'attendance',
    }
    return render(request, 'teacher/attendance.html', context)


@teacher_required
def teacher_attendance_history_view(request):
    """Teacher views their attendance history per class."""
    profile = get_teacher_profile(request.user)
    teacher = profile.teacher

    assigned_classes = SchoolClass.objects.filter(teacher=teacher).select_related('branch') if teacher else []

    today_str = str(date_type.today())
    selected_class_id = request.GET.get('class_id', '').strip()
    date_filter = request.GET.get('date', '').strip()
    status_filter = request.GET.get('status', '').strip()
    if not date_filter:
        date_filter = today_str

    selected_class = None
    attendances_by_date = {}

    if selected_class_id:
        selected_class = get_object_or_404(SchoolClass, id=selected_class_id, teacher=teacher)
        qs = Attendance.objects.filter(school_class=selected_class).select_related('student').order_by('-date', 'student__name')
        if date_filter:
            qs = qs.filter(date=date_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)
        for att in qs:
            d = str(att.date)
            if d not in attendances_by_date:
                attendances_by_date[d] = {
                    'records': [],
                    'present_count': 0,
                    'absent_count': 0,
                    'late_count': 0
                }
            attendances_by_date[d]['records'].append(att)
            if att.status == 'present':
                attendances_by_date[d]['present_count'] += 1
            elif att.status == 'absent':
                attendances_by_date[d]['absent_count'] += 1
            elif att.status == 'late':
                attendances_by_date[d]['late_count'] += 1

    context = {
        'profile': profile,
        'teacher': teacher,
        'institution': teacher.branch.institution if teacher else None,
        'branch': teacher.branch if teacher else None,
        'assigned_classes': assigned_classes,
        'selected_class': selected_class,
        'attendances_by_date': attendances_by_date,
        'date_filter': date_filter,
        'status_filter': status_filter,
        'current_tab': 'attendance_history',
    }
    return render(request, 'teacher/attendance_history.html', context)
