from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db import models as db_models
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import JsonResponse
User = get_user_model()
from django.utils import timezone
from datetime import date
from super_admin.models import SchoolApplication, Institution

from .models import SchoolAdminProfile, Branch, Student, Teacher, StaffMember, BranchRequest, SchoolClass, CustomRole, SchoolUser, Medium, Attendance

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
            status='pending',
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
    
    if total_branches <= 1 and not (inst.features.get('manage_branches', False) or inst.features.get('add_new_branch', False)):
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
            branch_id = request.POST.get('branch_id')
            status = request.POST.get('status', 'active')
            
            if branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                student.branch = branch
                student.status = status
                student.save()
                messages.success(request, f"Student '{student.name}' updated successfully.")
            return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
        else:  # add action
            school_user_id = request.POST.get('school_user_id', '').strip()
            password = request.POST.get('password', '').strip()
            branch_id = request.POST.get('branch_id', '').strip()
            
            if not school_user_id:
                messages.error(request, "Please search and select a user by email first.")
                return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
            
            if not password:
                messages.error(request, "Password is required.")
                return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
            
            if not branch_id:
                messages.error(request, "Please assign a school (branch).")
                return redirect(reverse('school_students'))
            
            school_user = get_object_or_404(SchoolUser, id=school_user_id, institution=inst)
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            
            # Enforce unique student email
            if Student.objects.filter(email=school_user.email).exists():
                messages.error(request, f"'{school_user.email}' is already registered as a student.")
                return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
            
            # Enforce unique Django user email (allow if they are already registered as a teacher)
            existing_user = User.objects.filter(email=school_user.email).first() or User.objects.filter(username=school_user.email).first()
            if existing_user:
                if hasattr(existing_user, 'teacher_profile') and existing_user.teacher_profile:
                    user = existing_user
                    if password:
                        user.set_password(password)
                        user.save()
                else:
                    messages.error(request, f"A login account with email '{school_user.email}' already exists.")
                    return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
            else:
                # Create Django User with STUDENT role
                user = User.objects.create_user(
                    username=school_user.email,
                    email=school_user.email,
                    password=password,
                    first_name=school_user.first_name,
                    last_name=school_user.last_name,
                    role='STUDENT'
                )
            
            # Create Student record
            from django.contrib.auth.hashers import make_password as hash_pw
            class_id = request.POST.get('school_class_id', '').strip()
            school_class_obj = None
            if class_id:
                try:
                    school_class_obj = SchoolClass.objects.get(id=class_id, branch=branch)
                except SchoolClass.DoesNotExist:
                    pass
            student_obj = Student.objects.create(
                branch=branch,
                school_class=school_class_obj,
                school_user=school_user,
                name=school_user.full_name,
                email=school_user.email,
                password=hash_pw(password),
                status='active'
            )
            
            # Create StudentProfile (links User ↔ Student)
            from student.models import StudentProfile
            StudentProfile.objects.create(user=user, student=student_obj)
            
            messages.success(request, f"Student '{school_user.full_name}' registered successfully!")
            return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
            
    selected_branch_ids = []
    if branch_filter_id:
        try:
            selected_branch_ids.append(int(branch_filter_id))
        except ValueError:
            pass
    elif branches.count() == 1:
        selected_branch_ids.append(branches.first().id)

    from .models import Medium
    mediums = Medium.objects.filter(institution=inst)
    all_classes = SchoolClass.objects.filter(branch__in=branches).order_by('branch', 'name', 'section')

    context = {
        'profile': profile,
        'institution': inst,
        'students': students,
        'branches': branches,
        'mediums': mediums,
        'all_classes': all_classes,
        'query': q,
        'branch_filter_id': branch_filter_id,
        'selected_branch_ids': selected_branch_ids,
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
    teachers = Teacher.objects.filter(branch__in=branches).select_related('school_user', 'branch')
    if q:
        teachers = teachers.filter(name__icontains=q)
    if branch_filter_id:
        teachers = teachers.filter(branch_id=branch_filter_id)
        
    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'edit':
            teacher_id = request.POST.get('teacher_id')
            teacher = get_object_or_404(Teacher, id=teacher_id, branch__in=branches)
            branch_id = request.POST.get('branch_id')
            status = request.POST.get('status', 'active')
            
            if branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                teacher.branch = branch
                teacher.status = status
                teacher.save()
                    
                messages.success(request, f"Teacher '{teacher.name}' updated successfully.")
            return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")

        else:  # add action
            school_user_id = request.POST.get('school_user_id', '').strip()
            password = request.POST.get('password', '').strip()
            branch_id = request.POST.get('branch_id', '').strip()
            medium_id = request.POST.get('medium_id', '').strip()
            
            if not school_user_id:
                messages.error(request, "Please search and select a user by email first.")
                return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
            
            if not password:
                messages.error(request, "Password is required.")
                return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
            
            if not branch_id:
                messages.error(request, "Please assign a school (branch).")
                return redirect(reverse('school_teachers'))
            
            school_user = get_object_or_404(SchoolUser, id=school_user_id, institution=inst)
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            
            # Enforce unique teacher email
            if Teacher.objects.filter(email=school_user.email).exists():
                messages.error(request, f"'{school_user.email}' is already registered as a teacher.")
                return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
            
            # Enforce unique Django user email (allow if they are already registered as a student)
            existing_user = User.objects.filter(email=school_user.email).first() or User.objects.filter(username=school_user.email).first()
            if existing_user:
                if hasattr(existing_user, 'student_profile') and existing_user.student_profile:
                    user = existing_user
                    if password:
                        user.set_password(password)
                        user.save()
                else:
                    messages.error(request, f"A login account with email '{school_user.email}' already exists.")
                    return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
            else:
                # Create Django User with TEACHER role
                user = User.objects.create_user(
                    username=school_user.email,
                    email=school_user.email,
                    password=password,
                    first_name=school_user.first_name,
                    last_name=school_user.last_name,
                    role='TEACHER'
                )
            
            # Create Teacher record
            from django.contrib.auth.hashers import make_password as hash_pw
            teacher_obj = Teacher.objects.create(
                branch=branch,
                school_user=school_user,
                name=school_user.full_name,
                email=school_user.email,
                password=hash_pw(password),
                status='active'
            )
            
            # Create TeacherProfile (links User ↔ Teacher)
            from teacher.models import TeacherProfile
            TeacherProfile.objects.create(user=user, teacher=teacher_obj)
            
            messages.success(request, f"Teacher '{school_user.full_name}' registered successfully!")
            return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
            
    selected_branch_ids = []
    if branch_filter_id:
        try:
            selected_branch_ids.append(int(branch_filter_id))
        except ValueError:
            pass
    elif branches.count() == 1:
        selected_branch_ids.append(branches.first().id)

    mediums = Medium.objects.filter(institution=inst)

    context = {
        'profile': profile,
        'institution': inst,
        'teachers': teachers,
        'branches': branches,
        'mediums': mediums,
        'query': q,
        'branch_filter_id': branch_filter_id,
        'selected_branch_ids': selected_branch_ids,
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
            
    selected_branch_ids = []
    if branch_filter_id:
        try:
            selected_branch_ids.append(int(branch_filter_id))
        except ValueError:
            pass
    elif branches.count() == 1:
        selected_branch_ids.append(branches.first().id)

    from .models import Medium
    mediums = Medium.objects.filter(institution=inst)

    context = {
        'profile': profile,
        'institution': inst,
        'others': others,
        'branches': branches,
        'mediums': mediums,
        'custom_roles': CustomRole.objects.filter(institution=inst),
        'query': q,
        'branch_filter_id': branch_filter_id,
        'selected_branch_ids': selected_branch_ids,
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
            name = request.POST.get('medium', '').strip()
            if name == 'Custom':
                name = request.POST.get('custom_medium', '').strip()
                
            if not name:
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
        elif action == 'assign_teacher':
            class_id = request.POST.get('class_id')
            teacher_id = request.POST.get('teacher_id', '').strip()
            cls = get_object_or_404(SchoolClass, id=class_id, branch__in=branches)
            if teacher_id:
                teacher_obj = get_object_or_404(Teacher, id=teacher_id, branch__in=branches)
                cls.teacher = teacher_obj
            else:
                cls.teacher = None
            cls.save()
            messages.success(request, f"Teacher assigned to '{cls.name}' successfully.")
            return redirect(f"{reverse('school_classes')}?branch_id={cls.branch_id}")
        else:
            name = request.POST.get('name', '').strip()
            section = request.POST.get('section', '').strip()
            branch_id = request.POST.get('branch_id', '')
            if name and branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                section_val = section or None
                if SchoolClass.objects.filter(branch=branch, name=name, section=section_val).exists():
                    messages.error(request, f"Class '{name}' already exists in {branch.name}.")
                else:
                    SchoolClass.objects.create(branch=branch, name=name, section=section_val)
                    messages.success(request, f"Class '{name}' added successfully.")
            return redirect(f"{reverse('school_classes')}?branch_id={branch_id}")

    from .models import Medium
    mediums = Medium.objects.filter(institution=inst)

    total_classes = classes.count()
    
    selected_branch_ids = []
    if branch_filter_id:
        try:
            selected_branch_ids.append(int(branch_filter_id))
        except ValueError:
            pass
    elif branches.count() == 1:
        selected_branch_ids.append(branches.first().id)
        
    medium_filter_id = request.GET.get('medium_id', '')
    selected_medium_ids = []
    if medium_filter_id:
        try:
            selected_medium_ids.append(int(medium_filter_id))
        except ValueError:
            pass
    elif mediums.count() == 1:
        selected_medium_ids.append(mediums.first().id)

    teachers = Teacher.objects.filter(branch__in=branches)

    context = {
        'profile': profile,
        'institution': inst,
        'branches': branches,
        'classes': classes,
        'mediums': mediums,
        'teachers': teachers,
        'query': q,
        'branch_filter_id': branch_filter_id,
        'selected_branch_ids': selected_branch_ids,
        'selected_medium_ids': selected_medium_ids,
        'total_classes': total_classes,
        'current_tab': 'classes',
    }
    return render(request, 'school_admin/classes.html', context)


# ─── Attendance Report (School Admin) ─────────────────────────────────────────

@school_admin_required
def school_attendance_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()

    branch_filter_id = request.GET.get('branch_id', '').strip()
    class_filter_id = request.GET.get('class_id', '').strip()
    date_filter = request.GET.get('date', '').strip()

    classes = SchoolClass.objects.filter(branch__in=branches)
    if branch_filter_id:
        classes = classes.filter(branch_id=branch_filter_id)

    selected_class = None
    attendances = []
    if class_filter_id:
        selected_class = get_object_or_404(SchoolClass, id=class_filter_id, branch__in=branches)
        qs = Attendance.objects.filter(school_class=selected_class).select_related('student', 'teacher')
        if date_filter:
            qs = qs.filter(date=date_filter)
        attendances = qs.order_by('-date', 'student__name')

    # Attendance summary per class
    from django.db.models import Count, Q
    class_summary = []
    for cls in SchoolClass.objects.filter(branch__in=branches).select_related('teacher', 'branch'):
        total = Attendance.objects.filter(school_class=cls).values('date').distinct().count()
        present = Attendance.objects.filter(school_class=cls, status='present').count()
        absent = Attendance.objects.filter(school_class=cls, status='absent').count()
        class_summary.append({'cls': cls, 'sessions': total, 'present': present, 'absent': absent})

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
        'classes': SchoolClass.objects.filter(branch__in=branches),
        'class_summary': class_summary,
        'selected_class': selected_class,
        'attendances': attendances,
        'branch_filter_id': branch_filter_id,
        'class_filter_id': class_filter_id,
        'date_filter': date_filter,
        'selected_branch_ids': selected_branch_ids,
        'current_tab': 'attendance',
    }
    return render(request, 'school_admin/attendance.html', context)


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


# ─── School Users Management ──────────────────────────────────────────────────

@school_admin_required
def school_users_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution

    q = request.GET.get('q', '').strip()
    users = SchoolUser.objects.filter(institution=inst).order_by('-created_at')
    if q:
        users = users.filter(email__icontains=q) | users.filter(first_name__icontains=q) | users.filter(last_name__icontains=q)
        users = users.filter(institution=inst).order_by('-created_at')

    if request.method == 'POST':
        action = request.POST.get('action', 'add')

        if action == 'edit':
            user_id = request.POST.get('user_id')
            su = get_object_or_404(SchoolUser, id=user_id, institution=inst)
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            dob = request.POST.get('dob', '').strip() or None
            city = request.POST.get('city', '').strip()
            state = request.POST.get('state', '').strip()
            address = request.POST.get('address', '').strip()
            pincode = request.POST.get('pincode', '').strip()

            if first_name and last_name:
                su.first_name = first_name
                su.last_name = last_name
                su.dob = dob
                su.city = city
                su.state = state
                su.address = address
                su.pincode = pincode
                su.save()

                # Sync name changes to Teacher, Student, and User if the user is registered
                user_needs_sync = False
                if hasattr(su, 'teacher_role') and su.teacher_role:
                    teacher = su.teacher_role
                    teacher.name = su.full_name
                    teacher.save()
                    user_needs_sync = True
                if hasattr(su, 'student_role') and su.student_role:
                    student = su.student_role
                    student.name = su.full_name
                    student.save()
                    user_needs_sync = True
                    
                if user_needs_sync:
                    user = User.objects.filter(email=su.email).first()
                    if user:
                        user.first_name = first_name
                        user.last_name = last_name
                        user.save()

                messages.success(request, f"User '{su.full_name}' updated successfully.")
            return redirect('school_users')

        else:  # add
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            dob = request.POST.get('dob', '').strip() or None
            city = request.POST.get('city', '').strip()
            state = request.POST.get('state', '').strip()
            address = request.POST.get('address', '').strip()
            pincode = request.POST.get('pincode', '').strip()

            if not (first_name and last_name and email):
                messages.error(request, "First name, last name, and email are required.")
                return redirect('school_users')

            if SchoolUser.objects.filter(email=email).exists():
                messages.error(request, f"A user with email '{email}' already exists.")
                return redirect('school_users')

            SchoolUser.objects.create(
                institution=inst,
                first_name=first_name,
                last_name=last_name,
                email=email,
                dob=dob,
                city=city,
                state=state,
                address=address,
                pincode=pincode,
            )
            messages.success(request, f"User '{first_name} {last_name}' added successfully.")
            return redirect('school_users')

    context = {
        'profile': profile,
        'institution': inst,
        'school_users': users,
        'query': q,
        'current_tab': 'users',
    }
    return render(request, 'school_admin/users.html', context)


@school_admin_required
def school_user_lookup_api(request):
    """AJAX endpoint: search SchoolUser by email for teacher/student registration."""
    profile = get_school_profile(request.user)
    inst = profile.institution
    q = request.GET.get('q', '').strip()

    if not q or len(q) < 1:
        return JsonResponse({'results': []})

    existing_teacher_emails = set(
        Teacher.objects.filter(branch__institution=inst).values_list('email', flat=True)
    )
    existing_student_emails = set(
        Student.objects.filter(branch__institution=inst).values_list('email', flat=True)
    )

    qs = SchoolUser.objects.filter(institution=inst).filter(
        db_models.Q(first_name__icontains=q) |
        db_models.Q(last_name__icontains=q) |
        db_models.Q(email__icontains=q)
    )[:10]

    results = []
    for su in qs:
        results.append({
            'id': su.id,
            'first_name': su.first_name,
            'last_name': su.last_name,
            'full_name': su.full_name,
            'email': su.email,
            'is_teacher': su.email in existing_teacher_emails,
            'is_student': su.email in existing_student_emails,
        })

    return JsonResponse({'results': results})


@school_admin_required
def classes_by_branch_api(request):
    """AJAX endpoint: return SchoolClass list for a given branch_id."""
    profile = get_school_profile(request.user)
    inst = profile.institution
    branch_id = request.GET.get('branch_id', '').strip()

    if not branch_id:
        return JsonResponse({'classes': []})

    branch = Branch.objects.filter(id=branch_id, institution=inst).first()
    if not branch:
        return JsonResponse({'classes': []})

    classes = SchoolClass.objects.filter(branch=branch).order_by('name', 'section')
    data = []
    for c in classes:
        label = c.name
        if c.section:
            label += f' — {c.section}'
        data.append({'id': c.id, 'label': label})

    return JsonResponse({'classes': data})

