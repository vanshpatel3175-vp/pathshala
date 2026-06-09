from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from dashboard.models import SchoolApplication, Institution
from .models import SchoolAdminProfile, Branch, Student, Teacher, StaffMember, BranchRequest, SchoolClass

def school_signup_view(request):
    if request.user.is_authenticated:
        return redirect('school_overview')
        
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        school_name = request.POST.get('school_name', '').strip()
        mobile_number = request.POST.get('mobile_number', '').strip()
        state = request.POST.get('state', '').strip()
        city = request.POST.get('city', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            messages.error(request, "A user with this email already exists.")
            return render(request, 'school/signup.html')
            
        # 1. Create User (marked active immediately for dashboard access)
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        
        # 2. Create Institution
        inst = Institution.objects.create(
            name=school_name,
            type="SCHOOL",
            planned_type="SCHOOL",
            contact_no=mobile_number,
            email=email,
            expired_date=timezone.now() + timezone.timedelta(days=365),
            status='active',
            school_code=f"SCH-{user.id:04d}",
            plan='Premium'
        )

        # 3. Create Profile
        profile = SchoolAdminProfile.objects.create(
            user=user,
            institution=inst,
            phone=mobile_number,
            state=state,
            city=city
        )
        
        # 4. Create default first branch for the school
        Branch.objects.create(
            institution=inst,
            name="Main Branch",
            city=city if city else "Gujarat",
            branch_code=f"BR-{inst.id:04d}-01",
            address="Main Campus Address",
            status="active"
        )

        # 5. Create Superadmin application review request as 'Validated'
        SchoolApplication.objects.create(
            name=school_name,
            trust_name=f"Trust of {school_name}",
            principal_name=f"{first_name} {last_name}",
            email=email,
            contact_number=mobile_number,
            board="Gujarat State Board",
            medium="English Medium",
            registration_code=f"SCH-{user.id:04d}",
            date_applied=timezone.now().date(),
            status="Validated",
            video_url="https://www.w3schools.com/html/mov_bbb.mp4",
            accreditation_certificate="registration_certificate.pdf"
        )
        
        # Log the user in and redirect to dashboard
        authenticated_user = authenticate(username=email, password=password)
        if authenticated_user is not None:
            login(request, authenticated_user)
            messages.success(request, f"Welcome to your dashboard, {first_name}!")
            return redirect('school_overview')
            
        messages.success(request, "Registration successful! Please log in.")
        return redirect('login')
        
    return render(request, 'school/signup.html')

def school_login_view(request):
    return redirect('login')

def school_logout_view(request):
    logout(request)
    return redirect('school_login')

def get_school_profile(user):
    try:
        return user.school_profile
    except SchoolAdminProfile.DoesNotExist:
        return None

def school_admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        profile = get_school_profile(request.user)
        if not profile or not profile.institution:
            logout(request)
            messages.error(request, "This account is not authorized to access the School Admin portal.")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper

@school_admin_required
def school_overview_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    
    total_branches = branches.count()
    total_students = Student.objects.filter(branch__in=branches).count()
    total_teachers = Teacher.objects.filter(branch__in=branches).count()
    total_classes = SchoolClass.objects.filter(branch__in=branches).count()
    
    # Check if there is a pending, approved, or rejected branch request
    pending_request = BranchRequest.objects.filter(institution=inst, status='Pending').first()
    approved_request = BranchRequest.objects.filter(institution=inst, status='Approved').first()
    rejected_request = BranchRequest.objects.filter(institution=inst, status='Rejected').first()
    
    # Handle dashboard POST actions (request branch or create branch)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'request_branch':
            if not pending_request and not approved_request:
                BranchRequest.objects.create(
                    institution=inst,
                    status='Pending'
                )
                messages.success(request, "Branch creation request submitted successfully to Super Admin.")
            return redirect('school_overview')
            
        elif action == 'add_branch':
            if approved_request:
                name = request.POST.get('name', '').strip()
                city = request.POST.get('city', '').strip()
                branch_code = request.POST.get('branch_code', '').strip()
                address = request.POST.get('address', '').strip()
                
                if name and city:
                    # Create the branch
                    new_branch = Branch.objects.create(
                        institution=inst,
                        name=name,
                        city=city,
                        branch_code=branch_code if branch_code else f"BR-{inst.id:04d}-{total_branches+1:02d}",
                        address=address,
                        status='active'
                    )
                    # Automatically create default classes for new branch
                    SchoolClass.objects.create(branch=new_branch, name="Grade 1", section="A")
                    SchoolClass.objects.create(branch=new_branch, name="Grade 2", section="A")
                    
                    # Complete/consume the request
                    approved_request.status = 'Completed'
                    approved_request.save()
                    messages.success(request, f"Branch '{name}' created successfully!")
                return redirect('school_overview')
            else:
                messages.error(request, "Branch creation requires an approved request.")
                return redirect('school_overview')
                
    main_branch = branches.first() if total_branches == 1 else None
    
    # Handle branch selection for statistics (Multiple Branch Logic)
    selected_branch_id = request.GET.get('branch_id')
    selected_branch = None
    branch_students_count = 0
    branch_teachers_count = 0
    branch_classes_count = 0
    
    if selected_branch_id:
        selected_branch = get_object_or_404(Branch, id=selected_branch_id, institution=inst)
        branch_students_count = selected_branch.students.count()
        branch_teachers_count = selected_branch.teachers.count()
        branch_classes_count = selected_branch.classes.count()
    elif total_branches > 1:
        # Default to first branch if multiple exist
        selected_branch = branches.first()
        branch_students_count = selected_branch.students.count()
        branch_teachers_count = selected_branch.teachers.count()
        branch_classes_count = selected_branch.classes.count()
        
    context = {
        'profile': profile,
        'institution': inst,
        'branches': branches,
        'total_branches': total_branches,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_classes': total_classes,
        'pending_request': pending_request,
        'approved_request': approved_request,
        'rejected_request': rejected_request,
        'main_branch': main_branch,
        'selected_branch': selected_branch,
        'branch_students_count': branch_students_count,
        'branch_teachers_count': branch_teachers_count,
        'branch_classes_count': branch_classes_count,
        'current_tab': 'overview'
    }
    return render(request, 'school/overview.html', context)

@school_admin_required
def school_branches_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    total_branches = branches.count()
    
    if total_branches <= 1:
        messages.warning(request, "Branch Management page is not available for single branch schools.")
        return redirect('school_overview')
        
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        city = request.POST.get('city', '').strip()
        if name and city:
            Branch.objects.create(
                institution=inst,
                name=name,
                city=city,
                status='active'
            )
            messages.success(request, f"Branch '{name}' added successfully.")
            return redirect('school_branches')
            
    total_students = Student.objects.filter(branch__in=branches).count()
    total_teachers = Teacher.objects.filter(branch__in=branches).count()
    
    context = {
        'profile': profile,
        'institution': inst,
        'branches': branches,
        'total_branches': total_branches,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'current_tab': 'branches'
    }
    return render(request, 'school/branches.html', context)

@school_admin_required
def school_roles_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    
    # We display users/roles.
    # In the mockup: id, name, email, roles, edit.
    # Let's collect all school staff members as roles profiles.
    staff_members = StaffMember.objects.filter(branch__in=branches)
    
    # Handle role updates
    if request.method == 'POST':
        staff_id = request.POST.get('staff_id')
        new_role = request.POST.get('role', '').strip()
        if staff_id and new_role:
            staff = get_object_or_404(StaffMember, id=staff_id, branch__in=branches)
            staff.role = new_role
            staff.save()
            messages.success(request, f"Role for {staff.name} updated to {new_role}.")
            return redirect('school_roles')
            
    context = {
        'profile': profile,
        'institution': inst,
        'staff_members': staff_members,
        'current_tab': 'roles'
    }
    return render(request, 'school/roles.html', context)

@school_admin_required
def school_students_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    
    q = request.GET.get('q', '').strip()
    students = Student.objects.filter(branch__in=branches)
    if q:
        students = students.filter(name__icontains=q)
        
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        branch_id = request.POST.get('branch_id')
        
        if name and email and branch_id:
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            Student.objects.create(
                branch=branch,
                name=name,
                email=email,
                status='active'
            )
            messages.success(request, f"Student '{name}' added successfully.")
            return redirect('school_students')
            
    context = {
        'profile': profile,
        'institution': inst,
        'students': students,
        'branches': branches,
        'query': q,
        'current_tab': 'students'
    }
    return render(request, 'school/students.html', context)

@school_admin_required
def school_teachers_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    
    q = request.GET.get('q', '').strip()
    teachers = Teacher.objects.filter(branch__in=branches)
    if q:
        teachers = teachers.filter(name__icontains=q)
        
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        branch_id = request.POST.get('branch_id')
        
        if name and email and branch_id:
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            Teacher.objects.create(
                branch=branch,
                name=name,
                email=email,
                status='active'
            )
            messages.success(request, f"Teacher '{name}' added successfully.")
            return redirect('school_teachers')
            
    context = {
        'profile': profile,
        'institution': inst,
        'teachers': teachers,
        'branches': branches,
        'query': q,
        'current_tab': 'teachers'
    }
    return render(request, 'school/teachers.html', context)

@school_admin_required
def school_others_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    
    q = request.GET.get('q', '').strip()
    others = StaffMember.objects.filter(branch__in=branches)
    if q:
        others = others.filter(name__icontains=q)
        
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', '').strip()
        branch_id = request.POST.get('branch_id')
        
        if name and email and role and branch_id:
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            StaffMember.objects.create(
                branch=branch,
                name=name,
                email=email,
                role=role,
                status='active'
            )
            messages.success(request, f"Staff member '{name}' added successfully.")
            return redirect('school_others')
            
    context = {
        'profile': profile,
        'institution': inst,
        'others': others,
        'branches': branches,
        'query': q,
        'current_tab': 'others'
    }
    return render(request, 'school/others.html', context)

from django.http import JsonResponse

@school_admin_required
def branch_request_status_api(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    
    pending_request = BranchRequest.objects.filter(institution=inst, status='Pending').first()
    approved_request = BranchRequest.objects.filter(institution=inst, status='Approved').first()
    rejected_request = BranchRequest.objects.filter(institution=inst, status='Rejected').first()
    
    status = 'None'
    if pending_request:
        status = 'Pending'
    elif approved_request:
        status = 'Approved'
    elif rejected_request:
        status = 'Rejected'
        
    return JsonResponse({
        'status': status,
        'approved': approved_request is not None,
        'branch_count': inst.branches.count()
    })

# ─── Classes Management ────────────────────────────────────────────────────────

@school_admin_required
def school_classes_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()

    q = request.GET.get('q', '').strip()
    branch_filter_id = request.GET.get('branch_id', '')

    classes = SchoolClass.objects.filter(branch__in=branches)
    if q:
        classes = classes.filter(name__icontains=q)
    if branch_filter_id:
        classes = classes.filter(branch_id=branch_filter_id)

    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'delete':
            class_id = request.POST.get('class_id')
            cls = get_object_or_404(SchoolClass, id=class_id, branch__in=branches)
            cls.delete()
            messages.success(request, "Class deleted successfully.")
            return redirect('school_classes')
        else:
            name = request.POST.get('name', '').strip()
            section = request.POST.get('section', '').strip()
            branch_id = request.POST.get('branch_id', '')
            if name and branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                SchoolClass.objects.create(branch=branch, name=name, section=section or None)
                messages.success(request, f"Class '{name}' added successfully.")
            return redirect('school_classes')

    total_classes = classes.count()
    context = {
        'profile': profile,
        'institution': inst,
        'branches': branches,
        'classes': classes,
        'query': q,
        'branch_filter_id': branch_filter_id,
        'total_classes': total_classes,
        'current_tab': 'classes',
    }
    return render(request, 'school/classes.html', context)


# ─── School Profile / Settings ─────────────────────────────────────────────────

@school_admin_required
def school_profile_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution

    if request.method == 'POST':
        # Update institution details
        inst.name = request.POST.get('school_name', inst.name).strip()
        inst.contact_no = request.POST.get('contact_no', inst.contact_no).strip()
        inst.email = request.POST.get('email', inst.email).strip()
        inst.save()

        # Update profile details
        profile.phone = request.POST.get('phone', profile.phone).strip()
        profile.state = request.POST.get('state', profile.state).strip()
        profile.city = request.POST.get('city', profile.city).strip()
        profile.save()

        messages.success(request, "School profile updated successfully.")
        return redirect('school_profile')

    context = {
        'profile': profile,
        'institution': inst,
        'current_tab': 'profile',
    }
    return render(request, 'school/profile.html', context)


# ─── Management Dashboard ──────────────────────────────────────────────────────

@school_admin_required
def school_manage_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()

    total_branches = branches.count()
    total_students = Student.objects.filter(branch__in=branches).count()
    total_teachers = Teacher.objects.filter(branch__in=branches).count()
    total_staff    = StaffMember.objects.filter(branch__in=branches).count()
    total_classes  = SchoolClass.objects.filter(branch__in=branches).count()

    recent_students = Student.objects.filter(branch__in=branches).order_by('-id')[:5]
    recent_teachers = Teacher.objects.filter(branch__in=branches).order_by('-id')[:5]
    recent_classes  = SchoolClass.objects.filter(branch__in=branches).order_by('-id')[:5]

    pending_request  = BranchRequest.objects.filter(institution=inst, status='Pending').first()
    approved_request = BranchRequest.objects.filter(institution=inst, status='Approved').first()

    context = {
        'profile': profile,
        'institution': inst,
        'branches': branches,
        'total_branches': total_branches,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_staff': total_staff,
        'total_classes': total_classes,
        'recent_students': recent_students,
        'recent_teachers': recent_teachers,
        'recent_classes': recent_classes,
        'pending_request': pending_request,
        'approved_request': approved_request,
        'current_tab': 'dashboard',
    }
    return render(request, 'school/manage.html', context)
