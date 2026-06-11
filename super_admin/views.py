from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, date, timedelta
from .models import SchoolApplication, Institution, PlatformUser, Inquiry, Meeting, Subscription

def superadmin_required(view_func):
    decorator = user_passes_test(
        lambda u: u.is_authenticated and (u.is_superuser or u.is_staff),
        login_url='login'
    )
    return decorator(view_func)

def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return redirect('dashboard')
        # Check if the user is a school admin and redirect them
        try:
            if hasattr(request.user, 'school_profile'):
                return redirect('school_overview')
        except Exception:
            pass
        return redirect('dashboard')
        
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        # Try authenticating with full email as username first (e.g. for school admin users)
        user = authenticate(username=email, password=password)
        if user is None:
            # Try split username fallback (e.g. for superadmin admin user)
            username = email.split('@')[0] if '@' in email else email
            user = authenticate(username=username, password=password)
            
        if user is None:
            # Hardcoded demo convenience fallback for admin
            if email in ['admin@ab.com', 'admin', 'ab@gmail.com']:
                user = authenticate(username='admin', password=password)
                
        if user is not None:
            if user.is_active:
                login(request, user)
                if user.is_superuser or user.is_staff:
                    return redirect('dashboard')
                else:
                    try:
                        if hasattr(user, 'school_profile'):
                            return redirect('school_overview')
                    except Exception:
                        pass
                    logout(request)
                    messages.error(request, "This account is not linked to any school or superadmin portal.")
                    return render(request, 'super_admin/login.html')
            else:
                try:
                    if hasattr(user, 'school_profile'):
                        messages.error(request, "Your registration is currently pending Superadmin validation.")
                    else:
                        messages.error(request, "This account is inactive.")
                except Exception:
                    messages.error(request, "This account is inactive.")
                return render(request, 'super_admin/login.html')
        else:
            # Check if it was because the user exists but is inactive
            inactive_user = None
            try:
                inactive_user = User.objects.get(username=email)
            except User.DoesNotExist:
                try:
                    username = email.split('@')[0] if '@' in email else email
                    inactive_user = User.objects.get(username=username)
                except User.DoesNotExist:
                    pass
                    
            if inactive_user is not None and not inactive_user.is_active and inactive_user.check_password(password):
                try:
                    if hasattr(inactive_user, 'school_profile'):
                        messages.error(request, "Your registration is currently pending Superadmin validation.")
                    else:
                        messages.error(request, "This account is inactive.")
                except Exception:
                    messages.error(request, "This account is inactive.")
            else:
                messages.error(request, "Invalid Email or Password.")
            
    return render(request, 'super_admin/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@superadmin_required
def dashboard_view(request):
    applications = SchoolApplication.objects.filter(status='Awaiting Review').order_by('-date_applied')
    
    # Statistics cards data
    awaiting_review = SchoolApplication.objects.filter(status='Awaiting Review').count()
    validated = SchoolApplication.objects.filter(status='Validated').count()
    declined = SchoolApplication.objects.filter(status='Declined').count()
    unsubmitted = SchoolApplication.objects.filter(status='Draft').count()
    total_registered = Institution.objects.count()
    
    # Show success notification overlay if coming from an approval
    approved_success = request.GET.get('approved', 'false') == 'true'
    
    context = {
        'applications': applications,
        'awaiting_review': awaiting_review,
        'validated': validated,
        'declined': declined,
        'unsubmitted': unsubmitted,
        'total_registered': total_registered,
        'approved_success': approved_success,
        'current_tab': 'dashboard'
    }
    return render(request, 'super_admin/dashboard.html', context)

@superadmin_required
def review_application_view(request, app_id):
    app = get_object_or_404(SchoolApplication, id=app_id)
    context = {
        'app': app,
        'current_tab': 'dashboard'
    }
    return render(request, 'super_admin/review_application.html', context)

@superadmin_required
def approve_application_view(request, app_id):
    app = get_object_or_404(SchoolApplication, id=app_id)
    app.status = 'Validated'
    app.save()
    
    # Create an Institution from the approved application
    inst, created = Institution.objects.get_or_create(
        name=app.name.split(' ')[0], # Simple code like "AB" or "RN"
        type="SCHOOL",
        planned_type="SCHOOL",
        contact_no=app.contact_number,
        email=app.email,
        defaults={
            'expired_date': timezone.now() + timedelta(days=365),
            'status': 'active',
            'school_code': f"SCH-{app.id:04d}",
            'plan': 'Premium'
        }
    )
    
    # Create a default first branch for the newly registered school
    from school_admin.models import Branch
    if created or not inst.branches.exists():
        Branch.objects.create(
            institution=inst,
            name="Main Branch",
            city=app.name.split(' ')[-1] if len(app.name.split(' ')) > 1 else "Gujarat",
            branch_code=f"BR-{inst.id:04d}-01",
            address="Main Campus Address",
            status="active"
        )
    
    # If a School Admin User registered prior, activate and link profile
    from django.contrib.auth.models import User
    try:
        user = User.objects.get(email=app.email)
        user.is_active = True
        user.save()
        if hasattr(user, 'school_profile'):
            profile = user.school_profile
            profile.institution = inst
            profile.save()
    except User.DoesNotExist:
        pass

    # Create PlatformUser entry
    PlatformUser.objects.get_or_create(
        email=app.email,
        defaults={
            'username': app.principal_name,
            'phone': app.contact_number,
            'date_joined': timezone.now(),
            'role': 'SCHOOL STAFF'
        }
    )
        
    return redirect('/login/dashboard/?approved=true')

@superadmin_required
def decline_application_view(request, app_id):
    app = get_object_or_404(SchoolApplication, id=app_id)
    app.status = 'Declined'
    app.save()
    return redirect('dashboard')

@superadmin_required
def all_institutions_view(request):
    institutions = Institution.objects.all().order_by('name')
    total_registered = institutions.count()
    
    context = {
        'institutions': institutions,
        'total_registered': total_registered,
        'current_tab': 'institutions'
    }
    return render(request, 'super_admin/institutions.html', context)

@superadmin_required
def toggle_institution_view(request, inst_id):
    inst = get_object_or_404(Institution, id=inst_id)
    if inst.status == 'active':
        inst.status = 'disabled'
    else:
        inst.status = 'active'
        inst.activation_requested = False
    inst.save()
    return redirect('all_institutions')

@superadmin_required
def platform_users_view(request):
    users = PlatformUser.objects.exclude(role='SUPER ADMIN').order_by('-date_joined')
    total_users = users.count()
    
    context = {
        'users': users,
        'total_users': total_users,
        'current_tab': 'users'
    }
    return render(request, 'super_admin/platform_users.html', context)

@superadmin_required
def inquiries_view(request):
    inquiries = Inquiry.objects.all().order_by('-last_active')
    applications = SchoolApplication.objects.all().order_by('-date_applied')
    
    context = {
        'inquiries': inquiries,
        'applications': applications,
        'current_tab': 'payment' # Mockup shows payment icon leads here
    }
    return render(request, 'super_admin/inquiries.html', context)

@superadmin_required
def inquiry_details_view(request, inq_id):
    inquiry = get_object_or_404(Inquiry, id=inq_id)
    subscriptions = Subscription.objects.filter(inquiry=inquiry).order_by('sr_no')
    
    # We load registered institutions to populate the "Institute" selector dropdown (RN, HD, VJ)
    institutions = Institution.objects.all()
    
    # Handle updating the inquiry's linked institute via dropdown
    selected_inst = request.GET.get('institute')
    if selected_inst:
        inquiry.school_name = selected_inst
        inquiry.save()
        return redirect('inquiry_details', inq_id=inquiry.id)
        
    context = {
        'inquiry': inquiry,
        'subscriptions': subscriptions,
        'institutions': institutions,
        'current_tab': 'payment'
    }
    return render(request, 'super_admin/inquiry_details.html', context)

@superadmin_required
def inquiry_review_view(request, inq_id):
    inquiry = get_object_or_404(Inquiry, id=inq_id)
    meetings = Meeting.objects.filter(inquiry=inquiry).order_by('meeting_no')
    
    context = {
        'inquiry': inquiry,
        'meetings': meetings,
        'current_tab': 'payment'
    }
    return render(request, 'super_admin/inquiry_review.html', context)

@superadmin_required
def inquiry_update_status_view(request, inq_id):
    inquiry = get_object_or_404(Inquiry, id=inq_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['Pending', 'Approved', 'Reject']:
            inquiry.status = new_status
            inquiry.save()
    return redirect('inquiry_review', inq_id=inquiry.id)

@superadmin_required
def inquiry_add_meeting_view(request, inq_id):
    inquiry = get_object_or_404(Inquiry, id=inq_id)
    if request.method == 'POST':
        meeting_no = Meeting.objects.filter(inquiry=inquiry).count() + 1
        title = request.POST.get('title', 'Follow-up Meeting')
        meeting_date = request.POST.get('date', timezone.now().date())
        start_time = request.POST.get('start_time', '10:00')
        end_time = request.POST.get('end_time', '11:00')
        next_date = request.POST.get('next_meeting_date')
        
        Meeting.objects.create(
            inquiry=inquiry,
            meeting_no=meeting_no,
            date=meeting_date,
            start_time=start_time,
            end_time=end_time,
            title=title,
            next_meeting_date=next_date if next_date else None
        )
    return redirect('inquiry_review', inq_id=inquiry.id)

@superadmin_required
def branch_requests_view(request):
    from school_admin.models import BranchRequest
    requests = BranchRequest.objects.all().order_by('-request_date')
    context = {
        'branch_requests': requests,
        'current_tab': 'branch_requests'
    }
    return render(request, 'super_admin/branch_requests.html', context)

@superadmin_required
def approve_branch_request_view(request, req_id):
    from school_admin.models import BranchRequest
    req = get_object_or_404(BranchRequest, id=req_id)
    req.status = 'Approved'
    req.approved_by = request.user
    req.approved_at = timezone.now()
    req.save()
    messages.success(request, f"Branch request for {req.institution.name} approved successfully.")
    return redirect('branch_requests')

@superadmin_required
def reject_branch_request_view(request, req_id):
    from school_admin.models import BranchRequest
    req = get_object_or_404(BranchRequest, id=req_id)
    req.status = 'Rejected'
    req.approved_by = request.user
    req.approved_at = timezone.now()
    req.save()
    messages.success(request, f"Branch request for {req.institution.name} rejected.")
    return redirect('branch_requests')

@superadmin_required
def toggle_branch_view(request, branch_id):
    from school_admin.models import Branch
    branch = get_object_or_404(Branch, id=branch_id)
    if branch.status == 'active':
        branch.status = 'disabled'
        messages.success(request, f"Branch '{branch.name}' disabled successfully.")
    else:
        branch.status = 'active'
        messages.success(request, f"Branch '{branch.name}' activated successfully.")
    branch.save()
    return redirect('all_institutions')

def pending_applications_context_processor(request):
    if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
        count = SchoolApplication.objects.filter(status='Awaiting Review').count()
        return {'pending_applications_count': count}
    return {'pending_applications_count': 0}

