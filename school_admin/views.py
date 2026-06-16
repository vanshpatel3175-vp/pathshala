from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
User = get_user_model()
from django.utils import timezone
from datetime import date
from super_admin.models import SchoolApplication, Institution

from .models import SchoolAdminProfile, Branch, Student, Teacher, StaffMember, BranchRequest, SchoolClass, CustomRole

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
            return render(request, 'school_admin/signup.html')
            
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
            name=school_name,
            city=city if city else "Gujarat",
            branch_code=f"BR-{inst.id:04d}-01",
            address=city,
            status="active"
        )

        # 5. Create Superadmin application review request as 'Awaiting Review'
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
            status="Awaiting Review",
            video_url="https://www.w3schools.com/html/mov_bbb.mp4",
            accreditation_certificate="registration_certificate.pdf"
        )
        
        # Create PlatformUser entry
        from super_admin.models import PlatformUser
        PlatformUser.objects.get_or_create(
            email=email,
            defaults={
                'username': f"{first_name} {last_name}",
                'phone': mobile_number,
                'date_joined': timezone.now(),
                'role': 'SCHOOL STAFF'
            }
        )
        
        # Log the user in and redirect to dashboard
        authenticated_user = authenticate(username=email, password=password)
        if authenticated_user is not None:
            login(request, authenticated_user)
            messages.success(request, f"Welcome to your dashboard, {first_name}!")
            return redirect('school_overview')
            
        messages.success(request, "Registration successful! Please log in.")
        return redirect('login')
        
    return render(request, 'school_admin/signup.html')

def school_login_view(request):
    if request.user.is_authenticated:
        return redirect('school_overview')
        
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        authenticated_user = authenticate(request, username=email, password=password)
        if authenticated_user is not None:
            login(request, authenticated_user)
            messages.success(request, "Welcome back!")
            return redirect('school_overview')
        else:
            messages.error(request, "Invalid email or password.")
            
    return render(request, 'school_admin/login.html')
def school_logout_view(request):
    logout(request)
    return redirect('login')

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
            
        # Determine approval status
        app = SchoolApplication.objects.filter(email=profile.institution.email).first()
        request.is_approved = not (app and app.status == 'Awaiting Review')
            
        # Check if the application is approved for pages other than overview
        if view_func.__name__ != 'school_overview_view' and not request.is_approved:
            messages.warning(request, "Access restricted. Your school registration is pending validation by Super Admin.")
            return redirect('school_overview')
            
        if profile.institution.status == 'disabled' and view_func.__name__ not in ('school_overview_view', 'branch_request_status_api'):
            messages.warning(request, "Your institution is disabled. Access is restricted to the Overview dashboard.")
            return redirect('school_overview')
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
        if action in ('request_branch', 'add_branch') and inst.status == 'disabled':
            messages.error(request, "This action is locked because your institution is disabled.")
            return redirect('school_overview')

        if action == 'request_branch':
            if not pending_request and not approved_request:
                BranchRequest.objects.create(
                    institution=inst,
                    status='Pending'
                )
                messages.success(request, "Branch creation request submitted successfully to Super Admin.")
            return redirect('school_overview')
            
        elif action == 'request_activation':
            if inst.status == 'disabled' and not inst.activation_requested:
                inst.activation_requested = True
                inst.save()
                messages.success(request, "Activation request submitted successfully to Super Admin.")
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

        elif action == 'edit_branch':
            branch_id = request.POST.get('branch_id')
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            name = request.POST.get('name', '').strip()
            city = request.POST.get('city', '').strip()
            branch_code = request.POST.get('branch_code', '').strip()
            address = request.POST.get('address', '').strip()
            status = request.POST.get('status', 'active')
            
            if name and city:
                branch.name = name
                branch.city = city
                branch.branch_code = branch_code
                branch.address = address
                branch.status = status
                branch.save()
                messages.success(request, f"Branch '{name}' updated successfully.")
            else:
                messages.error(request, "Branch Name and City are required.")
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
    return render(request, 'school_admin/overview.html', context)

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
        action = request.POST.get('action', 'add')
        if action == 'edit':
            branch_id = request.POST.get('branch_id')
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            name = request.POST.get('name', '').strip()
            city = request.POST.get('city', '').strip()
            branch_code = request.POST.get('branch_code', '').strip()
            address = request.POST.get('address', '').strip()
            status = request.POST.get('status', 'active')
            
            if name and city:
                branch.name = name
                branch.city = city
                branch.branch_code = branch_code
                branch.address = address
                branch.status = status
                branch.save()
                messages.success(request, f"Branch '{name}' updated successfully.")
            else:
                messages.error(request, "Branch Name and City are required.")
            return redirect('school_branches')
        else:
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
    return render(request, 'school_admin/branches.html', context)

@school_admin_required
def school_roles_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    
    # Handle role updates
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_role':
            role_name = request.POST.get('role_name', '').strip()
            if role_name:
                is_default = role_name.lower() in ('student', 'teacher', 'principal', 'principle')
                exists_custom = CustomRole.objects.filter(institution=inst, name__iexact=role_name).exists()
                if is_default or exists_custom:
                    messages.warning(request, f"Role '{role_name}' already exists.")
                else:
                    CustomRole.objects.create(institution=inst, name=role_name)
                    messages.success(request, f"Role '{role_name}' added successfully.")
            return redirect('school_roles')
            
        elif action == 'rename_role':
            old_role_name = request.POST.get('old_role_name', '').strip()
            new_role_name = request.POST.get('new_role_name', '').strip()
            if old_role_name.lower() in ('student', 'teacher', 'principal', 'principle'):
                messages.error(request, f"System role '{old_role_name}' cannot be renamed.")
                return redirect('school_roles')
            if old_role_name and new_role_name:
                # Update CustomRole entry if exists
                CustomRole.objects.filter(institution=inst, name__iexact=old_role_name).update(name=new_role_name)
                # Update StaffMembers having this role
                staff_updated = StaffMember.objects.filter(branch__in=branches, role=old_role_name)
                count = staff_updated.count()
                staff_updated.update(role=new_role_name)
                messages.success(request, f"Role '{old_role_name}' renamed to '{new_role_name}' for {count} user(s).")
            return redirect('school_roles')
            
        elif action == 'delete_role':
            role_name = request.POST.get('role_name', '').strip()
            if role_name.lower() in ('student', 'teacher', 'principal', 'principle'):
                messages.error(request, f"System role '{role_name}' cannot be deleted.")
                return redirect('school_roles')
            if role_name:
                # Delete CustomRole entry if exists
                CustomRole.objects.filter(institution=inst, name__iexact=role_name).delete()
                # Update StaffMembers having this role to Student
                staff_updated = StaffMember.objects.filter(branch__in=branches, role=role_name)
                count = staff_updated.count()
                staff_updated.update(role='Student')
                messages.success(request, f"Deleted role '{role_name}'. {count} user(s) reset to 'Student' role.")
            return redirect('school_roles')
            
    # Calculate role counts and unique roles
    from django.db.models import Count
    role_counts_query = StaffMember.objects.filter(branch__in=branches).values('role').annotate(count=Count('id'))
    
    # Start with default system roles and their respective counts from their specific tables
    total_students_count = Student.objects.filter(branch__in=branches).count()
    total_teachers_count = Teacher.objects.filter(branch__in=branches).count()
    
    role_dict = {
        'Student': total_students_count,
        'Teacher': total_teachers_count,
        'Principal': 0
    }
    
    # Load all CustomRoles for this institution to ensure they always show (even with 0 users)
    custom_roles = CustomRole.objects.filter(institution=inst)
    for cr in custom_roles:
        if cr.name not in role_dict:
            role_dict[cr.name] = 0
            
    # Add counts from StaffMember database
    for item in role_counts_query:
        role_name = item['role']
        matched = False
        for k in role_dict.keys():
            if k.lower() == role_name.lower():
                role_dict[k] += item['count']
                matched = True
                break
        if not matched:
            role_dict[role_name] = item['count']
            
    # Convert to list of dicts for template rendering
    role_counts = [{'role': k, 'count': v} for k, v in role_dict.items()]
    total_unique_roles = len(role_counts)
            
    context = {
        'profile': profile,
        'institution': inst,
        'role_counts': role_counts,
        'total_unique_roles': total_unique_roles,
        'current_tab': 'roles'
    }
    return render(request, 'school_admin/roles.html', context)

@school_admin_required
def school_students_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    
    q = request.GET.get('q', '').strip()
    branch_filter_id = request.GET.get('branch_id', '').strip()
    students = Student.objects.filter(branch__in=branches)
    if q:
        students = students.filter(name__icontains=q)
    if branch_filter_id:
        students = students.filter(branch_id=branch_filter_id)
        
    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'edit':
            student_id = request.POST.get('student_id')
            student = get_object_or_404(Student, id=student_id, branch__in=branches)
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            branch_id = request.POST.get('branch_id')
            status = request.POST.get('status', 'active')
            
            if name and email and branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                student.name = name
                student.email = email
                student.branch = branch
                student.status = status
                student.save()
                messages.success(request, f"Student '{name}' updated successfully.")
            return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
        else:
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
                return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
            
    context = {
        'profile': profile,
        'institution': inst,
        'students': students,
        'branches': branches,
        'query': q,
        'branch_filter_id': branch_filter_id,
        'current_tab': 'students'
    }
    return render(request, 'school_admin/students.html', context)

@school_admin_required
def school_teachers_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    
    q = request.GET.get('q', '').strip()
    branch_filter_id = request.GET.get('branch_id', '').strip()
    teachers = Teacher.objects.filter(branch__in=branches)
    if q:
        teachers = teachers.filter(name__icontains=q)
    if branch_filter_id:
        teachers = teachers.filter(branch_id=branch_filter_id)
        
    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'edit':
            teacher_id = request.POST.get('teacher_id')
            teacher = get_object_or_404(Teacher, id=teacher_id, branch__in=branches)
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            branch_id = request.POST.get('branch_id')
            status = request.POST.get('status', 'active')
            
            if name and email and branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                teacher.name = name
                teacher.email = email
                teacher.branch = branch
                teacher.status = status
                teacher.save()
                messages.success(request, f"Teacher '{name}' updated successfully.")
            return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
        else:
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
                return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
            
    context = {
        'profile': profile,
        'institution': inst,
        'teachers': teachers,
        'branches': branches,
        'query': q,
        'branch_filter_id': branch_filter_id,
        'current_tab': 'teachers'
    }
    return render(request, 'school_admin/teachers.html', context)

@school_admin_required
def school_others_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    
    q = request.GET.get('q', '').strip()
    branch_filter_id = request.GET.get('branch_id', '').strip()
    others = StaffMember.objects.filter(branch__in=branches)
    if q:
        others = others.filter(name__icontains=q)
    if branch_filter_id:
        others = others.filter(branch_id=branch_filter_id)
        
    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'edit':
            staff_id = request.POST.get('staff_id')
            staff = get_object_or_404(StaffMember, id=staff_id, branch__in=branches)
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            role = request.POST.get('role', '').strip()
            if role == 'custom':
                role = request.POST.get('custom_role', '').strip()
            branch_id = request.POST.get('branch_id')
            status = request.POST.get('status', 'active')
            
            if name and email and role and branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                staff.name = name
                staff.email = email
                staff.role = role
                staff.branch = branch
                staff.status = status
                staff.save()
                messages.success(request, f"Staff member '{name}' updated successfully.")
            return redirect(f"{reverse('school_others')}?branch_id={branch_id}")
        else:
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            role = request.POST.get('role', '').strip()
            if role == 'custom':
                role = request.POST.get('custom_role', '').strip()
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
                return redirect(f"{reverse('school_others')}?branch_id={branch_id}")
            
    context = {
        'profile': profile,
        'institution': inst,
        'others': others,
        'branches': branches,
        'custom_roles': CustomRole.objects.filter(institution=inst),
        'query': q,
        'branch_filter_id': branch_filter_id,
        'current_tab': 'others'
    }
    return render(request, 'school_admin/others.html', context)

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

# ─── Mediums Management ────────────────────────────────────────────────────────

@school_admin_required
def school_mediums_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution

    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'delete':
            medium_id = request.POST.get('medium_id')
            from .models import Medium
            medium = get_object_or_404(Medium, id=medium_id, institution=inst)
            medium.delete()
            messages.success(request, "Medium deleted successfully.")
        else:
            name = request.POST.get('name', '').strip()
            if name:
                from .models import Medium
                Medium.objects.create(institution=inst, name=name)
                messages.success(request, f"Medium '{name}' added successfully.")
        return redirect('school_mediums')

    from .models import Medium
    mediums = Medium.objects.filter(institution=inst)
    
    context = {
        'profile': profile,
        'institution': inst,
        'mediums': mediums,
        'current_tab': 'mediums',
    }
    return render(request, 'school_admin/mediums.html', context)

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
            deleted_branch_id = cls.branch_id
            cls.delete()
            messages.success(request, "Class deleted successfully.")
            return redirect(f"{reverse('school_classes')}?branch_id={deleted_branch_id}")
        else:
            name = request.POST.get('name', '').strip()
            section = request.POST.get('section', '').strip()
            branch_id = request.POST.get('branch_id', '')
            if name and branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                SchoolClass.objects.create(branch=branch, name=name, section=section or None)
                messages.success(request, f"Class '{name}' added successfully.")
            return redirect(f"{reverse('school_classes')}?branch_id={branch_id}")

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
    return render(request, 'school_admin/classes.html', context)


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
    return render(request, 'school_admin/profile.html', context)


# ─── Management Dashboard ──────────────────────────────────────────────────────

@school_admin_required
def school_manage_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()

    total_branches = branches.count()
    
    # Filter statistics and logs by selected branch
    selected_branch_id = request.GET.get('branch_id')
    selected_branch = None
    if selected_branch_id:
        selected_branch = get_object_or_404(Branch, id=selected_branch_id, institution=inst)
    elif total_branches > 0:
        selected_branch = branches.first()

    if selected_branch:
        total_students = Student.objects.filter(branch=selected_branch).count()
        total_teachers = Teacher.objects.filter(branch=selected_branch).count()
        total_staff    = StaffMember.objects.filter(branch=selected_branch).count()
        total_classes  = SchoolClass.objects.filter(branch=selected_branch).count()

        recent_students = Student.objects.filter(branch=selected_branch).order_by('-id')[:5]
        recent_teachers = Teacher.objects.filter(branch=selected_branch).order_by('-id')[:5]
        recent_classes  = SchoolClass.objects.filter(branch=selected_branch).order_by('-id')[:5]
        recent_staff    = StaffMember.objects.filter(branch=selected_branch).order_by('-id')[:5]
        all_students    = Student.objects.filter(branch=selected_branch).order_by('name')
        all_classes     = SchoolClass.objects.filter(branch=selected_branch).order_by('name')
    else:
        total_students = 0
        total_teachers = 0
        total_staff = 0
        total_classes = 0
        recent_students = []
        recent_teachers = []
        recent_classes = []
        recent_staff = []
        all_students = []
        all_classes = []

    pending_request  = BranchRequest.objects.filter(institution=inst, status='Pending').first()
    approved_request = BranchRequest.objects.filter(institution=inst, status='Approved').first()

    # --- Handle File Upload ---
    if request.method == 'POST' and request.FILES.get('material_file'):
        title = request.POST.get('title')
        standard_id = request.POST.get('standard')
        material_file = request.FILES.get('material_file')
        
        branch_id = request.POST.get('branch_id')
        branch_to_save = get_object_or_404(Branch, id=branch_id, institution=inst) if branch_id else selected_branch

        if branch_to_save and title and material_file:
            school_class = None
            if standard_id and standard_id != 'other':
                school_class = SchoolClass.objects.filter(id=standard_id, branch=branch_to_save).first()
            
            from .models import StudyMaterial
            StudyMaterial.objects.create(
                branch=branch_to_save,
                school_class=school_class,
                title=title,
                file=material_file
            )
            from django.contrib import messages
            messages.success(request, "Study material uploaded successfully!")
            
            # Redirect to same page with study tab active
            redirect_url = f"{request.path}?tab=study"
            if selected_branch_id:
                redirect_url += f"&branch_id={selected_branch_id}"
            return redirect(redirect_url)

    # --- Fetch Study Materials ---
    from .models import StudyMaterial
    if selected_branch:
        study_materials = StudyMaterial.objects.filter(branch=selected_branch).order_by('-uploaded_at')
    else:
        study_materials = []

    context = {
        'profile': profile,
        'institution': inst,
        'branches': branches,
        'selected_branch': selected_branch,
        'total_branches': total_branches,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_staff': total_staff,
        'total_classes': total_classes,
        'recent_students': recent_students,
        'recent_teachers': recent_teachers,
        'recent_classes': recent_classes,
        'recent_staff': recent_staff,
        'all_students': all_students,
        'all_classes': all_classes,
        'pending_request': pending_request,
        'approved_request': approved_request,
        'study_materials': study_materials,
        'current_tab': request.GET.get('tab', 'dashboard'),
    }
    return render(request, 'school_admin/manage.html', context)


