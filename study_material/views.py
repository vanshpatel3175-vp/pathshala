from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from school_admin.models import Branch, SchoolClass, Teacher
from school_admin.views import school_admin_required, get_school_profile
from teacher.views import teacher_required, get_teacher_profile
from student.views import student_required, get_student_profile
from .models import StudyMaterial


# ─── School Admin Views ───────────────────────────────────────────────────────

@school_admin_required
def admin_study_materials_view(request):
    """School admin: list + upload study materials."""
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()

    branch_filter_id = request.GET.get('branch_id', '').strip()
    class_filter_id = request.GET.get('class_id', '').strip()
    category_filter = request.GET.get('category', '').strip()

    materials_qs = StudyMaterial.objects.filter(branch__in=branches).select_related(
        'branch', 'school_class', 'uploaded_by_teacher'
    )
    if branch_filter_id:
        materials_qs = materials_qs.filter(branch_id=branch_filter_id)
    if class_filter_id:
        materials_qs = materials_qs.filter(school_class_id=class_filter_id)
    if category_filter:
        materials_qs = materials_qs.filter(category=category_filter)

    # Handle upload POST
    if request.method == 'POST' and request.FILES.get('file'):
        title = request.POST.get('title', '').strip()
        subject = request.POST.get('subject', '').strip()
        category = request.POST.get('category', 'notes').strip()
        description = request.POST.get('description', '').strip()
        branch_id = request.POST.get('branch_id', '').strip()
        class_id = request.POST.get('class_id', '').strip()
        f = request.FILES['file']

        if not title or not branch_id:
            messages.error(request, "Title and School are required.")
        else:
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            school_class = None
            if class_id:
                school_class = SchoolClass.objects.filter(id=class_id, branch=branch).first()
            StudyMaterial.objects.create(
                branch=branch,
                school_class=school_class,
                title=title,
                subject=subject,
                category=category,
                description=description,
                file=f,
                uploaded_by_teacher=None,
            )
            messages.success(request, f"'{title}' uploaded successfully!")
        return redirect(request.path + (f'?branch_id={branch_filter_id}' if branch_filter_id else ''))

    # Handle delete
    if request.method == 'POST' and request.POST.get('action') == 'delete':
        mat_id = request.POST.get('material_id')
        mat = get_object_or_404(StudyMaterial, id=mat_id, branch__in=branches)
        mat.delete()
        messages.success(request, "Material deleted.")
        return redirect(request.path)

    classes = SchoolClass.objects.filter(branch__in=branches).order_by('name', 'section')
    selected_branch_ids = []
    if branch_filter_id:
        try:
            selected_branch_ids.append(int(branch_filter_id))
        except ValueError:
            pass
    elif branches.count() == 1:
        selected_branch_ids.append(branches.first().id)

    context = {
        'profile': profile,
        'institution': inst,
        'branches': branches,
        'classes': classes,
        'materials': materials_qs,
        'branch_filter_id': branch_filter_id,
        'class_filter_id': class_filter_id,
        'category_filter': category_filter,
        'selected_branch_ids': selected_branch_ids,
        'category_choices': StudyMaterial.CATEGORY_CHOICES,
        'current_tab': 'study_materials',
    }
    return render(request, 'study_material/admin_list.html', context)


@school_admin_required
def admin_delete_material_view(request, material_id):
    profile = get_school_profile(request.user)
    inst = profile.institution
    mat = get_object_or_404(StudyMaterial, id=material_id, branch__institution=inst)
    mat.delete()
    messages.success(request, "Study material deleted.")
    return redirect('admin_study_materials')


# ─── Teacher Views ────────────────────────────────────────────────────────────

@teacher_required
def teacher_study_materials_view(request):
    """Teacher: view + upload study materials for their assigned classes."""
    profile = get_teacher_profile(request.user)
    teacher = profile.teacher
    branch = teacher.branch if teacher else None

    assigned_classes = SchoolClass.objects.filter(teacher=teacher) if teacher else []

    class_filter_id = request.GET.get('class_id', '').strip()
    category_filter = request.GET.get('category', '').strip()

    materials_qs = StudyMaterial.objects.filter(branch=branch).select_related(
        'school_class', 'uploaded_by_teacher'
    )
    if class_filter_id:
        materials_qs = materials_qs.filter(school_class_id=class_filter_id)
    if category_filter:
        materials_qs = materials_qs.filter(category=category_filter)

    # Handle upload
    if request.method == 'POST' and request.FILES.get('file'):
        title = request.POST.get('title', '').strip()
        subject = request.POST.get('subject', '').strip()
        category = request.POST.get('category', 'notes').strip()
        description = request.POST.get('description', '').strip()
        class_id = request.POST.get('class_id', '').strip()
        f = request.FILES['file']

        if not title:
            messages.error(request, "Title is required.")
        else:
            school_class = None
            if class_id:
                school_class = SchoolClass.objects.filter(id=class_id, teacher=teacher).first()
            StudyMaterial.objects.create(
                branch=branch,
                school_class=school_class,
                title=title,
                subject=subject,
                category=category,
                description=description,
                file=f,
                uploaded_by_teacher=teacher,
            )
            messages.success(request, f"'{title}' uploaded successfully!")
        return redirect('teacher_study_materials')

    context = {
        'profile': profile,
        'teacher': teacher,
        'institution': branch.institution if branch else None,
        'branch': branch,
        'assigned_classes': assigned_classes,
        'materials': materials_qs,
        'class_filter_id': class_filter_id,
        'category_filter': category_filter,
        'category_choices': StudyMaterial.CATEGORY_CHOICES,
        'current_tab': 'study_materials',
    }
    return render(request, 'study_material/teacher_list.html', context)


@teacher_required
def teacher_delete_material_view(request, material_id):
    profile = get_teacher_profile(request.user)
    teacher = profile.teacher
    mat = get_object_or_404(StudyMaterial, id=material_id, uploaded_by_teacher=teacher)
    mat.delete()
    messages.success(request, "Study material deleted.")
    return redirect('teacher_study_materials')


# ─── Student Views ────────────────────────────────────────────────────────────

@student_required
def student_study_materials_view(request):
    """Student: view study materials for their class."""
    profile = get_student_profile(request.user)
    student = profile.student if profile else None
    school_class = student.school_class if student else None
    branch = student.branch if student else None

    category_filter = request.GET.get('category', '').strip()

    materials_qs = []
    if school_class and branch:
        materials_qs = StudyMaterial.objects.filter(
            branch=branch, school_class=school_class
        ).select_related('uploaded_by_teacher')
        if category_filter:
            materials_qs = materials_qs.filter(category=category_filter)

    context = {
        'student': student,
        'institution': branch.institution if branch else None,
        'school_class': school_class,
        'materials': materials_qs,
        'category_filter': category_filter,
        'category_choices': StudyMaterial.CATEGORY_CHOICES,
        'current_tab': 'study_materials',
    }
    return render(request, 'study_material/student_list.html', context)
