from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db import models as db_models
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
User = get_user_model()
from django.http import JsonResponse

from django.utils import timezone
from datetime import date
from super_admin.models import SchoolApplication, Institution, Role, SchoolRole, AcademicYear

from .models import SchoolAdminProfile, Branch, Student, Teacher, StaffMember, BranchRequest, SchoolClass, CustomRole, Medium, Attendance, Holiday, Event, RoleProfile, SchoolUser

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
            mobile_no=mobile_number,
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
            school_code="",
            plan='Premium'
        )
        inst.school_code = f"SCH-{inst.id:04d}"
        inst.save()

        # 2.5 Create SchoolRole and RoleProfile for SCHOOL_ADMIN role
        role_obj, _ = Role.objects.get_or_create(role_name='SCHOOL_ADMIN')
        school_role, _ = SchoolRole.objects.get_or_create(role=role_obj, school=inst)
        RoleProfile.objects.create(
            user=user,
            role=school_role.role,
            institution=inst,
            role_name=school_role.role.role_name,
            email_id=email,
            mobile_no=mobile_number,
            status='active'
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
            registration_code=inst.school_code,
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
            
        has_teacher = False
        has_student = False
        try:
            if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
                has_teacher = True
        except AttributeError:
            pass
        try:
            if hasattr(request.user, 'student_profile') and request.user.student_profile:
                has_student = True
        except AttributeError:
            pass

        if has_teacher or has_student:
            logout(request)
            messages.error(request, "This account is not authorized to access the School Admin portal.")
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
                    # 1. Create entry in CustomRole table
                    CustomRole.objects.create(institution=inst, name=role_name)
                    
                    # 2. Store in Role table inside super_admin (uppercase role_name)
                    role_obj, _ = Role.objects.get_or_create(role_name=role_name.upper())
                    
                    # 3. Create the SchoolRole entry to link it to this institution
                    SchoolRole.objects.get_or_create(role=role_obj, school=inst)
                    
                    messages.success(request, f"Role '{role_name}' added successfully.")
            return redirect('school_roles')
            
        elif action == 'rename_role':
            old_role_name = request.POST.get('old_role_name', '').strip()
            new_role_name = request.POST.get('new_role_name', '').strip()
            if old_role_name.lower() in ('student', 'teacher', 'principal', 'principle'):
                messages.error(request, f"System role '{old_role_name}' cannot be renamed.")
                return redirect('school_roles')
            if old_role_name and new_role_name:
                # 1. Update CustomRole entry if exists
                CustomRole.objects.filter(institution=inst, name__iexact=old_role_name).update(name=new_role_name)
                
                # 2. Get/create the new Role and link it to the school
                new_role_obj, _ = Role.objects.get_or_create(role_name=new_role_name.upper())
                SchoolRole.objects.get_or_create(role=new_role_obj, school=inst)
                
                # 3. Update StaffMembers having this role
                staff_updated = StaffMember.objects.filter(branch__in=branches, role_name__iexact=old_role_name)
                count = staff_updated.count()
                for staff in staff_updated:
                    staff.role = new_role_obj
                    staff.role_name = new_role_name
                    staff.save()
                
                messages.success(request, f"Role '{old_role_name}' renamed to '{new_role_name}' for {count} user(s).")
            return redirect('school_roles')
            
        elif action == 'delete_role':
            role_name = request.POST.get('role_name', '').strip()
            if role_name.lower() in ('student', 'teacher', 'principal', 'principle'):
                messages.error(request, f"System role '{role_name}' cannot be deleted.")
                return redirect('school_roles')
            if role_name:
                # 1. Delete CustomRole entry if exists
                CustomRole.objects.filter(institution=inst, name__iexact=role_name).delete()
                
                # 2. Delete SchoolRole link
                old_role_obj = Role.objects.filter(role_name=role_name.upper()).first()
                if old_role_obj:
                    SchoolRole.objects.filter(role=old_role_obj, school=inst).delete()
                
                # 3. Reset StaffMembers having this role to Student
                student_role_obj, _ = Role.objects.get_or_create(role_name='STUDENT')
                staff_updated = StaffMember.objects.filter(branch__in=branches, role_name__iexact=role_name)
                count = staff_updated.count()
                for staff in staff_updated:
                    staff.role = student_role_obj
                    staff.role_name = 'STUDENT'
                    staff.save()
                
                messages.success(request, f"Deleted role '{role_name}'. {count} user(s) reset to 'Student' role.")
            return redirect('school_roles')
            
    # Calculate role counts and unique roles
    from django.db.models import Count
    role_counts_query = StaffMember.objects.filter(branch__in=branches).values('role_name').annotate(count=Count('id'))
    
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
        role_name = item['role_name']
        if not role_name:
            continue
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
    students = Student.objects.filter(branch__in=branches).select_related('user', 'branch')
    if q:
        students = students.filter(
            db_models.Q(user__first_name__icontains=q) |
            db_models.Q(user__last_name__icontains=q)
        )
    if branch_filter_id:
        students = students.filter(branch_id=branch_filter_id)
        
    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'edit':
            student_id = request.POST.get('student_id')
            student = get_object_or_404(Student, id=student_id, branch__in=branches)
            branch_id = request.POST.get('branch_id')
            status = request.POST.get('status', 'active')
            class_id = request.POST.get('school_class_id', '').strip()
            
            if branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                student.branch = branch
                student.status = status
                
                # Update school class
                if class_id:
                    try:
                        school_class_obj = SchoolClass.objects.get(id=class_id, branch=branch)
                        student.school_class = school_class_obj
                    except SchoolClass.DoesNotExist:
                        student.school_class = None
                else:
                    student.school_class = None
                    
                student.save()
                messages.success(request, f"Student '{student.name}' updated successfully.")
            return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
        elif action == 'delete':
            student_id = request.POST.get('student_id')
            student = get_object_or_404(Student, id=student_id, branch__in=branches)
            student_name = student.name
            student.delete()
            messages.success(request, f"Student '{student_name}' deleted successfully.")
            return redirect(f"{reverse('school_students')}?branch_id={branch_filter_id}")
        else:  # add action
            school_user_id = request.POST.get('school_user_id', '').strip()
            password = request.POST.get('password', '').strip()
            branch_id = request.POST.get('branch_id', '').strip()
            first_name_val = request.POST.get('first_name', '').strip()
            middle_name_val = request.POST.get('middle_name', '').strip()
            last_name_val = request.POST.get('last_name', '').strip()
            
            # Fetch all extra student fields
            mobile_no = request.POST.get('mobile_no', '').strip()
            parent_full_name = request.POST.get('parent_full_name', '').strip()
            parent_mobile_no = request.POST.get('parent_mobile_no', '').strip()
            dob_str = request.POST.get('date_of_birth', '').strip()
            city = request.POST.get('city', '').strip()
            state = request.POST.get('state', '').strip() or 'Gujarat'
            address = request.POST.get('address', '').strip()
            pincode = request.POST.get('pincode', '').strip()
            gardian_name = request.POST.get('gardian_name', '').strip()
            gardian_mobile_no = request.POST.get('gardian_mobile_no', '').strip()
            uid_no = request.POST.get('uid_no', '').strip()
            roll_no = request.POST.get('roll_no', '').strip()
            grno = request.POST.get('grno', '').strip()
            
            if not school_user_id:
                messages.error(request, "Please search and select a user by email first.")
                return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
            
            if not branch_id:
                messages.error(request, "Please assign a school (branch).")
                return redirect(reverse('school_students'))
            
            # Validation for guardian mobile number
            if gardian_mobile_no:
                if gardian_mobile_no == mobile_no or gardian_mobile_no == parent_mobile_no:
                    messages.error(request, "Guardian mobile number must be different from both student mobile number and parent mobile number.")
                    return redirect(f"{reverse('school_students')}?branch_id={branch_id}")

            dob = None
            if dob_str:
                try:
                    from django.utils.dateparse import parse_date
                    dob = parse_date(dob_str)
                except Exception:
                    pass

            su = get_object_or_404(RoleProfile, id=school_user_id, institution=inst)
            user = su.user
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            
            student_role_obj, _ = Role.objects.get_or_create(role_name='STUDENT')
            student_school_role, _ = SchoolRole.objects.get_or_create(role=student_role_obj, school=inst)
            
            if RoleProfile.objects.filter(user=user, role=student_school_role.role, institution=inst).exists():
                messages.error(request, f"'{user.first_name} {user.last_name}' is already registered as a student.")
                return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
            
            if RoleProfile.objects.filter(user=user, institution=inst).exclude(role_name__in=['USER', 'STUDENT']).exists():
                messages.error(request, f"'{user.first_name} {user.last_name}' already has a staff or teacher role and cannot be registered as a student.")
                return redirect(f"{reverse('school_students')}?branch_id={branch_id}")
            
            # Check if this user is registered in another institution/school
            is_shared_user = RoleProfile.objects.filter(user=user).exclude(institution=inst).exists()
            
            if not is_shared_user:
                if first_name_val:
                    user.first_name = first_name_val
                user.middle_name = middle_name_val
                if last_name_val:
                    user.last_name = last_name_val
                if password:
                    user.set_password(password)
                if mobile_no:
                    user.mobile_no = mobile_no
                user.save()

            # Keep looking-up profile (USER role profile) details synced as well
            su.name = f"{user.first_name} {user.last_name}"
            su.middle_name = user.middle_name
            if mobile_no:
                su.mobile_no = mobile_no
            su.city = city
            su.state = state
            su.address = address
            su.pincode = pincode
            su.save()
            
            class_id = request.POST.get('school_class_id', '').strip()
            school_class_obj = None
            if class_id:
                try:
                    school_class_obj = SchoolClass.objects.get(id=class_id, branch=branch)
                except SchoolClass.DoesNotExist:
                    pass

            # Resolve active academic year from session or institution default
            active_year_id = request.session.get('academic_year_id') or (
                inst.current_academic_year_id
            )

            student_obj = Student.objects.create(
                user=user,
                role=student_school_role.role,
                institution=inst,
                branch=branch,
                school_class=school_class_obj,
                name=f"{user.first_name} {user.last_name}",
                middle_name=user.middle_name,
                email=user.email,
                password=user.password,
                status='active',
                parent_full_name=parent_full_name,
                parent_mobile_no=parent_mobile_no,
                date_of_birth=dob,
                city=city,
                state=state,
                address=address,
                pincode=pincode,
                mobile_no=mobile_no,
                gardian_name=gardian_name,
                gardian_mobile_no=gardian_mobile_no,
                roll_number=roll_no,
                gr_number=grno,
                academic_year_id=active_year_id,
            )

            from student.models import StudentProfile
            student_profile_defaults = {
                'parent_full_name': parent_full_name,
                'parent_mobile_no': parent_mobile_no,
                'gardian_name': gardian_name,
                'gardian_mobile_no': gardian_mobile_no,
            }
            if dob is not None:
                student_profile_defaults['date_of_birth'] = dob
            StudentProfile.objects.update_or_create(
                user=user,
                defaults=student_profile_defaults,
            )

            messages.success(request, f"Student '{user.first_name} {user.last_name}' registered successfully!")
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
    teachers = Teacher.objects.filter(branch__in=branches).select_related('user', 'branch')
    if q:
        teachers = teachers.filter(
            db_models.Q(user__first_name__icontains=q) |
            db_models.Q(user__last_name__icontains=q)
        )
    if branch_filter_id:
        teachers = teachers.filter(branch_id=branch_filter_id)
        
    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'edit':
            teacher_id = request.POST.get('teacher_id')
            teacher = get_object_or_404(Teacher, id=teacher_id, branch__in=branches)
            branch_id = request.POST.get('branch_id')
            status = request.POST.get('status', 'active')
            
            manage_attendance = request.POST.get('manage_attendance') == 'on'
            manage_subjects = request.POST.get('manage_subjects') == 'on'
            
            attendance_classes = request.POST.getlist('attendance_classes')
            subject_classes = {}
            for key in request.POST:
                if key.startswith('edit_subject_for_class_'):
                    class_id = key.split('_')[-1]
                    val = request.POST.get(key, '').strip()
                    if val:
                        subject_classes[class_id] = val
            
            if branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                teacher.branch = branch
                teacher.status = status
                
                if not isinstance(teacher.permissions, dict):
                    teacher.permissions = {}
                teacher.permissions['manage_attendance'] = manage_attendance
                teacher.permissions['manage_subjects'] = manage_subjects
                teacher.permissions['attendance_classes'] = attendance_classes
                teacher.permissions['subject_classes'] = subject_classes
                
                teacher.save()
                messages.success(request, f"Teacher '{teacher.name}' updated successfully.")
            return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
        else:  # add action
            school_user_id = request.POST.get('school_user_id', '').strip()
            password = request.POST.get('password', '').strip()
            branch_id = request.POST.get('branch_id', '').strip()
            
            # Additional teacher fields
            mobile_no = request.POST.get('mobile_no', '').strip()
            dob_str = request.POST.get('date_of_birth', '').strip()
            city = request.POST.get('city', '').strip()
            state = request.POST.get('state', '').strip() or 'Gujarat'
            address = request.POST.get('address', '').strip()
            pincode = request.POST.get('pincode', '').strip()
            
            manage_attendance = request.POST.get('manage_attendance') == 'on'
            manage_subjects = request.POST.get('manage_subjects') == 'on'
            
            attendance_classes = request.POST.getlist('attendance_classes')
            subject_classes = {}
            for key in request.POST:
                if key.startswith('subject_for_class_') and not key.startswith('edit_subject_for_class_'):
                    class_id = key.split('_')[-1]
                    val = request.POST.get(key, '').strip()
                    if val:
                        subject_classes[class_id] = val
            
            if not school_user_id:
                messages.error(request, "Please search and select a user by email first.")
                return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
            
            if not branch_id:
                messages.error(request, "Please assign a school (branch).")
                return redirect(reverse('school_teachers'))
            
            dob = None
            if dob_str:
                try:
                    from django.utils.dateparse import parse_date
                    dob = parse_date(dob_str)
                except Exception:
                    pass

            su = get_object_or_404(RoleProfile, id=school_user_id, institution=inst)
            user = su.user
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            
            teacher_role_obj, _ = Role.objects.get_or_create(role_name='TEACHER')
            teacher_school_role, _ = SchoolRole.objects.get_or_create(role=teacher_role_obj, school=inst)
            
            if RoleProfile.objects.filter(user=user, role=teacher_school_role.role, institution=inst).exists():
                messages.error(request, f"'{user.first_name} {user.last_name}' is already registered as a teacher.")
                return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
            
            if RoleProfile.objects.filter(user=user, institution=inst, role_name__iexact='STUDENT').exists():
                messages.error(request, f"'{user.first_name} {user.last_name}' is registered as a student and cannot be assigned as a teacher.")
                return redirect(f"{reverse('school_teachers')}?branch_id={branch_id}")
            
            # Check if this user is registered in another institution/school
            is_shared_user = RoleProfile.objects.filter(user=user).exclude(institution=inst).exists()
            
            if not is_shared_user:
                if password:
                    user.set_password(password)
                if mobile_no:
                    user.mobile_no = mobile_no
                user.save()
            
            # Keep looking-up profile (USER role profile) details synced as well
            su.name = f"{user.first_name} {user.last_name}"
            su.middle_name = user.middle_name
            if mobile_no:
                su.mobile_no = mobile_no
            su.city = city
            su.state = state
            su.address = address
            su.pincode = pincode
            su.save()
            
            # Resolve active academic year from session or institution default
            active_year_id = request.session.get('academic_year_id') or inst.current_academic_year_id

            teacher_obj = Teacher.objects.create(
                user=user,
                role=teacher_school_role.role,
                institution=inst,
                branch=branch,
                name=f"{user.first_name} {user.last_name}",
                middle_name=user.middle_name,
                email=user.email,
                password=user.password,
                status='active',
                date_of_birth=dob,
                city=city,
                state=state,
                address=address,
                pincode=pincode,
                mobile_no=mobile_no,
                academic_year_id=active_year_id,
                permissions={
                    'manage_attendance': manage_attendance, 
                    'manage_subjects': manage_subjects,
                    'attendance_classes': attendance_classes,
                    'subject_classes': subject_classes
                }
            )
            
            from teacher.models import TeacherProfile
            teacher_profile_defaults = {}
            if dob is not None:
                teacher_profile_defaults['date_of_birth'] = dob
            TeacherProfile.objects.update_or_create(user=user, defaults=teacher_profile_defaults)
            
            messages.success(request, f"Teacher '{user.first_name} {user.last_name}' registered successfully!")
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
    all_classes = SchoolClass.objects.filter(branch__in=branches).order_by('branch', 'name', 'section')

    context = {
        'profile': profile,
        'institution': inst,
        'teachers': teachers,
        'branches': branches,
        'mediums': mediums,
        'all_classes': all_classes,
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
        others = others.filter(
            db_models.Q(user__first_name__icontains=q) |
            db_models.Q(user__last_name__icontains=q)
        )
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
            password = request.POST.get('password', '').strip()
            if role == 'custom':
                role = request.POST.get('custom_role', '').strip()
            branch_id = request.POST.get('branch_id')
            status = request.POST.get('status', 'active')
            
            if branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                staff.branch = branch
                staff.status = status
                
                role_obj, _ = Role.objects.get_or_create(role_name=role.upper())
                SchoolRole.objects.get_or_create(role=role_obj, school=inst)
                staff.role = role_obj
                staff.role_name = role
                
                if staff.school_user:
                    staff.name = staff.school_user.full_name
                    staff.email = staff.school_user.email
                else:
                    if name:
                        staff.name = name
                    if email:
                        staff.email = email
                if password:
                    from django.contrib.auth.hashers import make_password as hash_pw
                    staff.password = hash_pw(password)
                    user_obj = User.objects.filter(email=staff.email).first()
                    if user_obj:
                        user_obj.set_password(password)
                        user_obj.save()
                staff.save()
                messages.success(request, f"Staff member '{staff.name}' updated successfully.")
            return redirect(f"{reverse('school_others')}?branch_id={branch_filter_id}")
        elif action == 'delete':
            staff_id = request.POST.get('staff_id')
            staff = get_object_or_404(StaffMember, id=staff_id, branch__in=branches)
            staff_name = staff.name
            staff.delete()
            messages.success(request, f"Staff member '{staff_name}' deleted successfully.")
            return redirect(f"{reverse('school_others')}?branch_id={branch_filter_id}")
        else:
            school_user_id = request.POST.get('school_user_id', '').strip()
            branch_id = request.POST.get('branch_id', '').strip()
            role = request.POST.get('role', '').strip()
            
            # Fetch all extra staff fields
            mobile_no = request.POST.get('mobile_no', '').strip()
            dob_str = request.POST.get('date_of_birth', '').strip()
            city = request.POST.get('city', '').strip()
            state = request.POST.get('state', '').strip() or 'Gujarat'
            address = request.POST.get('address', '').strip()
            pincode = request.POST.get('pincode', '').strip()

            if not school_user_id:
                messages.error(request, "Please search and select a user by email first.")
                return redirect(f"{reverse('school_others')}?branch_id={branch_id}")
            
            if not branch_id:
                messages.error(request, "Please assign a school (branch).")
                return redirect(reverse('school_others'))
            
            school_user = get_object_or_404(SchoolUser, id=school_user_id, institution=inst)
            branch = get_object_or_404(Branch, id=branch_id, institution=inst)
            
            # Enforce unique staff (prevent registering the same user with the same role twice in this institution)
            if StaffMember.objects.filter(user=school_user.user, institution=inst, role_name__iexact=role).exists():
                messages.error(request, f"'{school_user.full_name}' is already registered with the '{role}' role.")
                return redirect(f"{reverse('school_others')}?branch_id={branch_id}")
            
            if RoleProfile.objects.filter(user=school_user.user, institution=inst, role_name__iexact='STUDENT').exists():
                messages.error(request, f"'{school_user.full_name}' is registered as a student and cannot be assigned any other role.")
                return redirect(f"{reverse('school_others')}?branch_id={branch_id}")
            
            user = school_user.user
            if mobile_no:
                user.mobile_no = mobile_no
                user.save()

            dob = None
            if dob_str:
                try:
                    from django.utils.dateparse import parse_date
                    dob = parse_date(dob_str)
                except Exception:
                    pass

            from django.db import IntegrityError
            role_obj, _ = Role.objects.get_or_create(role_name=role.upper())
            SchoolRole.objects.get_or_create(role=role_obj, school=inst)
            
            # Resolve active academic year from session or institution default
            active_year_id = request.session.get('academic_year_id') or inst.current_academic_year_id

            try:
                StaffMember.objects.create(
                    user=user,
                    institution=inst,
                    branch=branch,
                    email=school_user.email,
                    password=user.password,
                    role=role_obj,
                    role_name=role,
                    status='active',
                    date_of_birth=dob,
                    city=city,
                    state=state,
                    address=address,
                    pincode=pincode,
                    mobile_no=mobile_no,
                    academic_year_id=active_year_id,
                )
                messages.success(request, f"Staff member '{school_user.full_name}' registered successfully!")
            except IntegrityError as e:
                messages.error(request, f"'{school_user.full_name}' is already registered as a staff member. (Database error: {e})")
                
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
        'available_roles': Role.objects.exclude(role_name__in=['STUDENT', 'TEACHER', 'student', 'teacher', 'USER', 'user', 'SCHOOL_ADMIN', 'school_admin']),
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
            medium_id = request.POST.get('medium', '').strip()
            if name and branch_id:
                if not medium_id:
                    messages.error(request, "Please select a medium.")
                    return redirect(f"{reverse('school_classes')}?branch_id={branch_id}")
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                section_val = section or None
                from .models import Medium
                medium_obj = get_object_or_404(Medium, id=medium_id, institution=inst)
                if SchoolClass.objects.filter(branch=branch, name=name, section=section_val, medium=medium_obj).exists():
                    messages.error(request, f"Class '{name}' with section '{section or '—'}' and medium '{medium_obj.name}' already exists in {branch.name}.")
                else:
                    SchoolClass.objects.create(branch=branch, name=name, section=section_val, medium=medium_obj)
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

    # Get unique class names already used in this school for the dropdown
    existing_class_names = list(
        SchoolClass.objects.filter(branch__in=branches)
        .values_list('name', flat=True)
        .distinct()
        .order_by('name')
    )

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
        'existing_class_names': existing_class_names,
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
    
    if not date_filter:
        date_filter = timezone.now().date().strftime('%Y-%m-%d')

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
        attendances = qs.order_by('-date', 'student__user__first_name', 'student__user__last_name')

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
        all_students    = Student.objects.filter(branch=selected_branch).order_by('user__first_name', 'user__last_name')
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

        # Old study material logic removed

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
    users = RoleProfile.objects.filter(institution=inst, role__role_name='USER').order_by('-id')
    if q:
        users = users.filter(
            db_models.Q(email_id__icontains=q) |
            db_models.Q(user__first_name__icontains=q) |
            db_models.Q(user__last_name__icontains=q) |
            db_models.Q(user__middle_name__icontains=q)
        )

    if request.method == 'POST':
        action = request.POST.get('action', 'add')

        if action == 'delete':
            user_id = request.POST.get('user_id')
            su = get_object_or_404(RoleProfile, id=user_id, institution=inst, role__role_name='USER')
            name = su.name
            su.delete()
            messages.success(request, f"User '{name}' deleted successfully.")
            return redirect('school_users')

        elif action == 'edit':
            user_id = request.POST.get('user_id')
            su = get_object_or_404(RoleProfile, id=user_id, institution=inst, role__role_name='USER')
            first_name = request.POST.get('first_name', '').strip()
            middle_name = request.POST.get('middle_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            mobile_no = request.POST.get('mobile_number', '').strip() or request.POST.get('mobile_no', '').strip()

            if first_name and last_name:
                user_obj = su.user
                user_obj.first_name = first_name
                user_obj.middle_name = middle_name
                user_obj.last_name = last_name
                user_obj.mobile_no = mobile_no
                user_obj.save()

                RoleProfile.objects.filter(user=user_obj).update(
                    mobile_no=mobile_no
                )

                messages.success(request, f"User '{su.name}' updated successfully.")
            return redirect('school_users')

        else:  # add
            first_name = request.POST.get('first_name', '').strip()
            middle_name = request.POST.get('middle_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            mobile_no = request.POST.get('mobile_number', '').strip() or request.POST.get('mobile_no', '').strip()
            password = request.POST.get('password', '').strip()

            if not (first_name and last_name and email and password):
                messages.error(request, "First name, last name, email, and password are required.")
                return redirect('school_users')

            role_obj, _ = Role.objects.get_or_create(role_name='USER')
            school_role, _ = SchoolRole.objects.get_or_create(role=role_obj, school=inst)

            if RoleProfile.objects.filter(role=school_role.role, institution=inst, email_id=email).exists():
                messages.error(request, f"A user with email '{email}' is already registered at this school.")
                return redirect('school_users')

            user_obj = User.objects.filter(email=email).first()
            if not user_obj:
                user_obj = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    middle_name=middle_name,
                    last_name=last_name,
                    mobile_no=mobile_no
                )
            else:
                # User already exists in the database. To prevent overwriting
                # existing user data across other schools/branches, do NOT modify
                # the existing User model's details (password, name, mobile number).
                pass

            RoleProfile.objects.create(
                user=user_obj,
                role=school_role.role,
                institution=inst,
                role_name=school_role.role.role_name,
                email_id=email,
                password=user_obj.password,
                mobile_no=mobile_no,
                status='active'
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
    """AJAX endpoint: search pre-registered school users (RoleProfile role='USER') for teacher/student registration."""
    profile = get_school_profile(request.user)
    inst = profile.institution
    q = request.GET.get('q', '').strip()

    if not q or len(q) < 1:
        return JsonResponse({'results': []})

    qs = RoleProfile.objects.filter(
        institution=inst,
        role__role_name='USER'
    ).filter(
        db_models.Q(user__first_name__icontains=q) |
        db_models.Q(user__last_name__icontains=q) |
        db_models.Q(email_id__icontains=q) |
        db_models.Q(user__middle_name__icontains=q)
    )[:10]

    results = []
    for su in qs:
        is_teacher = Teacher.objects.filter(branch__institution=inst, user=su.user).exists()
        is_student = Student.objects.filter(branch__institution=inst, user=su.user).exists()
        is_staff = StaffMember.objects.filter(branch__institution=inst, user=su.user).exists()
        results.append({
            'id': su.id,
            'first_name': su.first_name,
            'middle_name': su.middle_name or '',
            'last_name': su.last_name,
            'full_name': su.name,
            'email': su.email,
            'mobile_no': su.mobile_no or '',
            'date_of_birth': su.date_of_birth.strftime('%Y-%m-%d') if su.date_of_birth else '',
            'is_teacher': is_teacher,
            'is_student': is_student,
            'is_staff': is_staff,
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


# ─── Holidays Management ──────────────────────────────────────────────────────

@school_admin_required
def school_holidays_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    total_branches = branches.count()

    if request.method == 'POST':
        action = request.POST.get('action', 'add')

        if action == 'delete':
            holiday_id = request.POST.get('holiday_id')
            holiday = get_object_or_404(Holiday, id=holiday_id, institution=inst)
            holiday.delete()
            messages.success(request, "Holiday deleted successfully.")
            return redirect('school_holidays')

        else:  # add
            holiday_name = request.POST.get('holiday_name', '').strip()
            start_date_str = request.POST.get('start_date', '').strip()
            end_date_str = request.POST.get('end_date', '').strip()
            add_branch = request.POST.get('add_branch')
            branch_id = request.POST.get('branch_name', '').strip()

            if not holiday_name:
                messages.error(request, "Holiday name is required.")
                return redirect('school_holidays')
            if not start_date_str or not end_date_str:
                messages.error(request, "Start date and end date are required.")
                return redirect('school_holidays')

            from datetime import datetime, date, timedelta
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, "Invalid date format.")
                return redirect('school_holidays')

            today = date.today()
            if start_date == today and end_date == (today - timedelta(days=1)):
                messages.error(request, "If today is the start date, you cannot choose yesterday as the end date.")
                return redirect('school_holidays')

            if end_date < start_date:
                messages.error(request, "End date cannot be before start date.")
                return redirect('school_holidays')

            if add_branch == 'on':
                # Create a single holiday for the institution (branch=None means all branches)
                Holiday.objects.create(
                    institution=inst,
                    branch=None,
                    holiday_name=holiday_name,
                    start_date=start_date,
                    end_date=end_date,
                )
                messages.success(request, f"Holiday '{holiday_name}' added for all branches.")
            elif branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                Holiday.objects.create(
                    institution=inst,
                    branch=branch,
                    holiday_name=holiday_name,
                    start_date=start_date,
                    end_date=end_date,
                )
                messages.success(request, f"Holiday '{holiday_name}' added for branch '{branch.name}'.")
            else:
                messages.error(request, "Please select a branch or choose 'All Branches'.")
            return redirect('school_holidays')

    # Gather and filter holidays
    holidays = Holiday.objects.filter(institution=inst).select_related('branch')
    filter_branch_id = request.GET.get('branch_id', '').strip()
    if filter_branch_id:
        from django.db.models import Q
        holidays = holidays.filter(Q(branch_id=filter_branch_id) | Q(branch__isnull=True))

    # Auto-select branch if only one
    default_branch = branches.first() if total_branches == 1 else None

    context = {
        'profile': profile,
        'institution': inst,
        'branches': branches,
        'holidays': holidays,
        'total_branches': total_branches,
        'default_branch': default_branch,
        'filter_branch_id': filter_branch_id,
        'current_tab': 'holidays',
    }
    return render(request, 'school_admin/holidays.html', context)


# ─── Events Management ────────────────────────────────────────────────────────

@school_admin_required
def school_events_view(request):
    profile = get_school_profile(request.user)
    inst = profile.institution
    branches = inst.branches.all()
    total_branches = branches.count()

    if request.method == 'POST':
        action = request.POST.get('action', 'add')

        if action == 'delete':
            event_id = request.POST.get('event_id')
            event = get_object_or_404(Event, id=event_id, institution=inst)
            event.delete()
            messages.success(request, "Event deleted successfully.")
            return redirect('school_events')

        else:  # add
            event_name = request.POST.get('event_name', '').strip()
            start_date_str = request.POST.get('start_date', '').strip()
            end_date_str = request.POST.get('end_date', '').strip()
            add_branch = request.POST.get('add_branch')
            branch_id = request.POST.get('branch_name', '').strip()

            if not event_name:
                messages.error(request, "Event name is required.")
                return redirect('school_events')
            if not start_date_str or not end_date_str:
                messages.error(request, "Start date and end date are required.")
                return redirect('school_events')

            from datetime import datetime, date, timedelta
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, "Invalid date format.")
                return redirect('school_events')

            today = date.today()
            if start_date == today and end_date == (today - timedelta(days=1)):
                messages.error(request, "If today is the start date, you cannot choose yesterday as the end date.")
                return redirect('school_events')

            if end_date < start_date:
                messages.error(request, "End date cannot be before start date.")
                return redirect('school_events')

            if add_branch == 'on':
                # Create a single event for the institution (branch=None means all branches)
                Event.objects.create(
                    institution=inst,
                    branch=None,
                    event_name=event_name,
                    start_date=start_date,
                    end_date=end_date,
                )
                messages.success(request, f"Event '{event_name}' added for all branches.")
            elif branch_id:
                branch = get_object_or_404(Branch, id=branch_id, institution=inst)
                Event.objects.create(
                    institution=inst,
                    branch=branch,
                    event_name=event_name,
                    start_date=start_date,
                    end_date=end_date,
                )
                messages.success(request, f"Event '{event_name}' added for branch '{branch.name}'.")
            else:
                messages.error(request, "Please select a branch or choose 'All Branches'.")
            return redirect('school_events')

    # Gather and filter events
    events = Event.objects.filter(institution=inst).select_related('branch')
    filter_branch_id = request.GET.get('branch_id', '').strip()
    if filter_branch_id:
        from django.db.models import Q
        events = events.filter(Q(branch_id=filter_branch_id) | Q(branch__isnull=True))

    # Auto-select branch if only one
    default_branch = branches.first() if total_branches == 1 else None

    context = {
        'profile': profile,
        'institution': inst,
        'branches': branches,
        'events': events,
        'total_branches': total_branches,
        'default_branch': default_branch,
        'filter_branch_id': filter_branch_id,
        'current_tab': 'events',
    }
    return render(request, 'school_admin/events.html', context)


@school_admin_required
def school_set_academic_year_view(request):
    """Sets the active academic year in the school admin session and redirects back."""
    if request.method == 'POST':
        year_id = request.POST.get('academic_year_id', '').strip()
        if year_id:
            year = AcademicYear.objects.filter(pk=year_id, is_active=True).first()
            if year:
                request.session['academic_year_id'] = year.pk
                messages.success(request, f"Switched to academic year: {year.name}")
            else:
                messages.error(request, 'Invalid or inactive academic year selected.')
        else:
            # Clear session — fall back to institution default
            request.session.pop('academic_year_id', None)
            messages.success(request, 'Academic year reset to institution default.')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('school_overview')
    return redirect(next_url)


import os
from django.conf import settings
from django.http import FileResponse, Http404

@school_admin_required
def student_template_csv(request):
    file_path = os.path.join(settings.BASE_DIR, 'school_admin', 'sample_templates', 'students_sample.csv')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='students_sample.csv')
    raise Http404("CSV Template file not found")


@school_admin_required
def student_template_xlsx(request):
    file_path = os.path.join(settings.BASE_DIR, 'school_admin', 'sample_templates', 'students_sample.xlsx')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='students_sample.xlsx')
    raise Http404("Excel Template file not found")


@school_admin_required
def student_import_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=400)
    
    uploaded_file = request.FILES.get('file')
    branch_id = request.POST.get('branch_id', '').strip()
    
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded.'}, status=400)
        
    if not branch_id:
        return JsonResponse({'error': 'Please select a branch.'}, status=400)
        
    profile = get_school_profile(request.user)
    inst = profile.institution
    branch = get_object_or_404(Branch, id=branch_id, institution=inst)
    
    from school_admin.services.student_import import StudentImportService
    importer = StudentImportService()
    result = importer.run(uploaded_file, inst, branch)
    
    return JsonResponse(result.to_dict())


