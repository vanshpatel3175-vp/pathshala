
from django.contrib.auth import authenticate
from rest_framework import serializers
from django.contrib.auth import get_user_model
from super_admin.models import Institution
from .models import SchoolAdminProfile
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class SchoolSignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    state = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    school_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists() or User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        # 1. Create User
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            role='SCHOOL STAFF'
        )
        
        # 2. Create Institution
        institution = Institution.objects.create(
            name=validated_data['school_name'],
            contact_no=validated_data['phone_number'],
            email=validated_data['email'],
            expired_date=timezone.now() + timedelta(days=365)
        )
        
        # 3. Create Profile
        SchoolAdminProfile.objects.create(
            user=user,
            institution=institution,
            phone=validated_data['phone_number'],
            state=validated_data['state'],
            city=validated_data['city']
        )
        
        return user

class schoolloginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class UserResponseSerializer(serializers.ModelSerializer):
    city = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role', 'city', 'state', 'phone_number', 'school_name']

    def get_city(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return ""
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.city
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.city
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.city
            
        from .models import SchoolUser
        school_user = SchoolUser.objects.filter(email=obj.email).first()
        if school_user:
            return school_user.city
            
        return ""

    def get_state(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return ""
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.state
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.state
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.state
            
        from .models import SchoolUser
        school_user = SchoolUser.objects.filter(email=obj.email).first()
        if school_user:
            return school_user.state
            
        return ""

    def get_phone_number(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return ""
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.phone
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.mobile_number or ""
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.mobile_number or ""
            
        from .models import SchoolUser
        school_user = SchoolUser.objects.filter(email=obj.email).first()
        if school_user:
            return school_user.mobile_number or ""
            
        return ""

    def get_school_name(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return "Super Admin Portal"
        if hasattr(obj, 'school_profile') and obj.school_profile.institution:
            return obj.school_profile.institution.name
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.institution:
            return obj.teacher_profile.institution.name
        if hasattr(obj, 'student_profile') and obj.student_profile.institution:
            return obj.student_profile.institution.name
            
        from .models import SchoolUser
        school_user = SchoolUser.objects.filter(email=obj.email).first()
        if school_user and school_user.institution:
            return school_user.institution.name
            
        return ""
    def get_role(self, obj):
        if obj.role == 'SCHOOL STAFF':
            from .models import StaffMember
            staff_member = StaffMember.objects.filter(email=obj.email).first()
            if staff_member and staff_member.role:
                return staff_member.role
        return obj.role

class SchoolLoginSerializer(serializers.Serializer):
    email = serializers.CharField(
        required=True,
        error_messages={
            'required': 'Email is required.',
            'blank': 'Email is required.'
        }
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        error_messages={
            'required': 'Password is required.',
            'blank': 'Password is required.'
        }
    )
    role = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        email = attrs.get('email', '').strip()
        password = attrs.get('password', '').strip()
        role = attrs.get('role', '').strip()

        if not email or not password:
            raise serializers.ValidationError("Email/Username and password are required.")

        # Find matching users by email
        users = list(User.objects.filter(email=email))
        # Also fall back to username search if no users found by email
        if not users:
            user_by_username = User.objects.filter(username=email).first()
            if user_by_username:
                users = [user_by_username]

        if not users:
            raise serializers.ValidationError("Invalid email or password.")

        # Filter by active users
        active_users = [u for u in users if u.is_active]
        if not active_users:
            raise serializers.ValidationError("This account is inactive.")

        # If a role is specified, filter by that role
        if role:
            role_users = [u for u in active_users if getattr(u, 'role', '').upper() == role.upper()]
            if not role_users:
                raise serializers.ValidationError(f"No active account found with role {role} for this email.")
            active_users = role_users

        # Authenticate each matching active user
        authenticated_users = []
        for u in active_users:
            authenticated_user = authenticate(username=u.username, password=password)
            if authenticated_user:
                authenticated_users.append(authenticated_user)

        if not authenticated_users:
            raise serializers.ValidationError("Invalid email or password.")

        # If multiple users authenticated successfully, we need the client to specify a role
        if len(authenticated_users) > 1:
            roles = [getattr(u, 'role', '') for u in authenticated_users]
            self.context['multiple_roles'] = roles
            raise serializers.ValidationError("Multiple roles associated with this email.")

        attrs['user'] = authenticated_users[0]
        return attrs

class SchoolUserResponseSerializer(serializers.ModelSerializer):
    institution_id = serializers.SerializerMethodField()
    institution_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'institution_id',
            'institution_name',
            'phone',
            'city',
            'state'
        ]

    def get_institution_id(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return None
        if hasattr(obj, 'school_profile') and obj.school_profile.institution:
            return obj.school_profile.institution.id
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.institution:
            return obj.teacher_profile.institution.id
        if hasattr(obj, 'student_profile') and obj.student_profile.institution:
            return obj.student_profile.institution.id
        return None

    def get_institution_name(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return "Super Admin Portal"
        if hasattr(obj, 'school_profile') and obj.school_profile.institution:
            return obj.school_profile.institution.name
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.institution:
            return obj.teacher_profile.institution.name
        if hasattr(obj, 'student_profile') and obj.student_profile.institution:
            return obj.student_profile.institution.name
        return ""

    def get_phone(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return ""
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.phone
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.mobile_number or ""
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.mobile_number or ""
        return ""

    def get_city(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return ""
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.city
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.city
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.city
        return ""

    def get_state(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return ""
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.state
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.state
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.state
        return ""

    def get_role(self, obj):
        role = getattr(obj, 'role', '')
        if role == 'SCHOOL STAFF':
            return 'SCHOOL_ADMIN'
        elif role == 'SUPER ADMIN':
            return 'SUPER_ADMIN'
        return role

class SchoolLoginAPISerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required.',
            'blank': 'Email is required.',
            'invalid': 'Enter a valid email address.'
        }
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        error_messages={
            'required': 'Password is required.',
            'blank': 'Password is required.'
        }
    )

    def validate(self, attrs):
        email = attrs.get('email', '').strip()
        password = attrs.get('password', '').strip()

        # Find matching users by email
        users = list(User.objects.filter(email=email))
        if not users:
            # Try username login fallback
            user_by_username = User.objects.filter(username=email).first()
            if user_by_username:
                users = [user_by_username]

        if not users:
            raise serializers.ValidationError("Invalid email or password.")

        # Filter active users
        active_users = [u for u in users if u.is_active]
        if not active_users:
            raise serializers.ValidationError("This account is inactive.")

        # Authenticate users using password
        authenticated_users = []
        for u in active_users:
            authenticated_user = authenticate(username=u.username, password=password)
            if authenticated_user:
                authenticated_users.append(authenticated_user)

        if not authenticated_users:
            raise serializers.ValidationError("Invalid email or password.")

        # Discover all available roles for the authenticated users
        user_email = authenticated_users[0].email
        roles = self.discover_user_roles(user_email)

        if not roles:
            raise serializers.ValidationError("No roles associated with this account.")

        attrs['authenticated_users'] = authenticated_users
        attrs['roles'] = roles
        attrs['primary_user'] = authenticated_users[0]
        return attrs

    def discover_user_roles(self, email):
        users = User.objects.filter(email=email, is_active=True)
        roles = []
        for u in users:
            if hasattr(u, 'school_profile') and u.school_profile:
                inst = u.school_profile.institution
                roles.append({
                    "role": "SCHOOL_ADMIN",
                    "institution_id": inst.id if inst else None,
                    "institution_name": inst.name if inst else "Pending Approval"
                })
            
            for rp in u.role_profiles.all():
                role_name = rp.role_name
                inst = rp.institution
                if role_name == 'TEACHER':
                    roles.append({
                        "role": "TEACHER",
                        "institution_id": inst.id,
                        "institution_name": inst.name
                    })
                elif role_name == 'STUDENT':
                    roles.append({
                        "role": "STUDENT",
                        "institution_id": inst.id,
                        "institution_name": inst.name
                    })

            if u.is_superuser:
                roles.append({
                    "role": "SUPER_ADMIN",
                    "institution_id": None,
                    "institution_name": "Super Admin Portal"
                })
        # Remove duplicate role-institution entries if any
        unique_roles = []
        seen = set()
        for r in roles:
            key = (r['role'], r['institution_id'])
            if key not in seen:
                seen.add(key)
                unique_roles.append(r)
        return unique_roles

class RoleSelectionSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    role = serializers.CharField(required=True)

    def validate(self, attrs):
        user_id = attrs.get('user_id')
        role = attrs.get('role', '').strip()

        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is missing.")

        # Retrieve and validate pre_auth_token from headers
        auth_header = request.headers.get('Authorization', '').strip()
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()
        if not token:
            token = request.headers.get('X-Pre-Auth-Token', '').strip()

        if not token:
            raise serializers.ValidationError("Authentication credentials (pre-auth token) were not provided.")

        from django.core import signing
        try:
            # Valid for 5 minutes
            token_data = signing.loads(token, salt="pre-auth", max_age=300)
        except signing.SignatureExpired:
            raise serializers.ValidationError("Authentication credentials expired.")
        except signing.BadSignature:
            raise serializers.ValidationError("Invalid authentication credentials.")

        # Find the target user
        try:
            target_user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found or inactive.")

        # Security check: the user_id's email must match the signed token email
        if target_user.email != token_data.get('email'):
            raise serializers.ValidationError("Access denied for this user profile.")

        # Map role representation to database role choice
        db_role = None
        role_upper = role.upper()
        if role_upper == 'SCHOOL_ADMIN':
            db_role = 'SCHOOL STAFF'
        elif role_upper == 'TEACHER':
            db_role = 'TEACHER'
        elif role_upper == 'STUDENT':
            db_role = 'STUDENT'
        elif role_upper == 'SUPER_ADMIN':
            db_role = 'SUPER ADMIN'
        else:
            raise serializers.ValidationError("Invalid role choice.")

        # Find the specific user account with that email and that role
        selected_user = User.objects.filter(email=target_user.email, role=db_role, is_active=True).first()
        if not selected_user:
            raise serializers.ValidationError(f"This user does not have the role {role}.")

        attrs['selected_user'] = selected_user
        attrs['role_name'] = role_upper
        return attrs

class LegacyLoginUserSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'date_of_birth',
            'role',
            'city',
            'state',
            'address',
            'phone_number',
            'school_name'
        ]

    def get_role(self, obj):
        role = getattr(obj, 'role', '')
        if role == 'SCHOOL STAFF':
            return 'SCHOOL_ADMIN'
        elif role == 'SUPER ADMIN':
            return 'SUPER_ADMIN'
        return role

    def get_date_of_birth(self, obj):
        if hasattr(obj, 'school_profile') and obj.school_profile.institution:
            return ""
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            dob = obj.teacher_profile.school_user.dob
            return dob.strftime('%Y-%m-%d') if dob else ""
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            dob = obj.student_profile.school_user.dob
            return dob.strftime('%Y-%m-%d') if dob else ""
        return ""

    def get_phone_number(self, obj):
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.phone
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.mobile_number or ""
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.mobile_number or ""
        return ""

    def get_school_name(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return "Super Admin Portal"
        if hasattr(obj, 'school_profile') and obj.school_profile.institution:
            return obj.school_profile.institution.name
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.institution:
            return obj.teacher_profile.institution.name
        if hasattr(obj, 'student_profile') and obj.student_profile.institution:
            return obj.student_profile.institution.name
        return ""

    def get_city(self, obj):
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.city
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.city
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.city
        return ""

    def get_state(self, obj):
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.state
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.state
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.state
        return ""
    
    def get_address(self, obj):
        if hasattr(obj, 'school_profile'):
            return obj.school_profile.address
        if hasattr(obj, 'teacher_profile') and obj.teacher_profile.school_user:
            return obj.teacher_profile.school_user.address
        if hasattr(obj, 'student_profile') and obj.student_profile.school_user:
            return obj.student_profile.school_user.address
        return ""


# ---------------------------------------------------------------------------
# New Login & Verify Serializers
# ---------------------------------------------------------------------------

class LoginSerializer(serializers.Serializer):
    """
    Minimal serializer for the new LoginAPIView.
    Accepts email + password, returns authenticated user + all_roles list.
    """
    email = serializers.EmailField(
        required=True,
        error_messages={'required': 'Email is required.', 'blank': 'Email is required.'}
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        error_messages={'required': 'Password is required.', 'blank': 'Password is required.'}
    )

    def validate(self, attrs):
        email = attrs.get('email', '').strip()
        password = attrs.get('password', '').strip()

        # Look up users by email (or username fallback)
        users = list(User.objects.filter(email=email))
        if not users:
            user_by_username = User.objects.filter(username=email).first()
            if user_by_username:
                users = [user_by_username]

        if not users:
            raise serializers.ValidationError("Invalid email or password.")

        active_users = [u for u in users if u.is_active]
        if not active_users:
            raise serializers.ValidationError("This account is inactive.")

        # Authenticate against password
        authenticated_user = None
        for u in active_users:
            auth_user = authenticate(username=u.username, password=password)
            if auth_user:
                authenticated_user = auth_user
                break

        if not authenticated_user:
            raise serializers.ValidationError("Invalid email or password.")

        attrs['user'] = authenticated_user
        return attrs


class VerifyProfileSerializer(serializers.ModelSerializer):
    """
    Returns full profile details for the authenticated user.
    Pulls data from User, RoleProfile, UserProfile and related tables.
    """
    first_name   = serializers.CharField(source='user.first_name', read_only=True)
    last_name    = serializers.CharField(source='user.last_name', read_only=True)
    middle_name  = serializers.SerializerMethodField()
    mobile_no    = serializers.CharField(source='mobile_no', read_only=True)
    email        = serializers.CharField(source='email_id', read_only=True)
    role_name    = serializers.CharField(read_only=True)
    institution  = serializers.SerializerMethodField()
    branch       = serializers.SerializerMethodField()
    address      = serializers.SerializerMethodField()

    # Student-specific fields (null for other roles)
    roll_no      = serializers.SerializerMethodField()
    uid_no       = serializers.SerializerMethodField()
    grno         = serializers.SerializerMethodField()
    school_class = serializers.SerializerMethodField()
    parent_full_name   = serializers.SerializerMethodField()
    parent_mobile_no   = serializers.SerializerMethodField()
    gardian_name       = serializers.SerializerMethodField()
    gardian_mobile_no  = serializers.SerializerMethodField()
    date_of_birth      = serializers.SerializerMethodField()

    # Teacher-specific fields (null for other roles)
    teacher_qualification = serializers.SerializerMethodField()

    class Meta:
        from school_admin.models import RoleProfile
        model = RoleProfile
        fields = [
            'id', 'email', 'first_name', 'last_name', 'middle_name',
            'mobile_no', 'role_name',
            'institution', 'branch', 'address',
            'date_of_birth',
            # Student
            'roll_no', 'uid_no', 'grno', 'school_class',
            'parent_full_name', 'parent_mobile_no',
            'gardian_name', 'gardian_mobile_no',
            # Teacher
            'teacher_qualification',
        ]

    def get_middle_name(self, obj):
        return getattr(obj.user, 'middle_name', None) or ""

    def get_institution(self, obj):
        if obj.institution:
            return {'id': obj.institution.id, 'name': obj.institution.name}
        return None

    def get_branch(self, obj):
        if obj.branch:
            return {'id': obj.branch.id, 'name': obj.branch.name}
        return None

    def get_address(self, obj):
        if obj.address_record:
            return {
                'addressline1': obj.address_record.addressline1 or "",
                'addressline2': obj.address_record.addressline2 or "",
                'city':         obj.address_record.city or "",
                'state':        obj.address_record.state or "",
                'pincode':      obj.address_record.pincode or "",
            }
        return None

    def _get_user_profile(self, obj):
        """Return the linked UserProfile if exists, else None."""
        return getattr(obj, 'user_profile', None)

    def get_date_of_birth(self, obj):
        dob = getattr(obj.user, 'date_of_birth', None)
        return dob.strftime('%Y-%m-%d') if dob else None

    # --- Student fields ---
    def get_roll_no(self, obj):
        up = self._get_user_profile(obj)
        return up.roll_no if up else None

    def get_uid_no(self, obj):
        up = self._get_user_profile(obj)
        return up.uid_no if up else None

    def get_grno(self, obj):
        up = self._get_user_profile(obj)
        return up.grno if up else None

    def get_school_class(self, obj):
        up = self._get_user_profile(obj)
        if up and up.school_class:
            return {'id': up.school_class.id, 'name': up.school_class.name}
        return None

    def get_parent_full_name(self, obj):
        up = self._get_user_profile(obj)
        return up.parent_full_name if up else None

    def get_parent_mobile_no(self, obj):
        up = self._get_user_profile(obj)
        return up.parent_mobile_no if up else None

    def get_gardian_name(self, obj):
        up = self._get_user_profile(obj)
        return up.gardian_name if up else None

    def get_gardian_mobile_no(self, obj):
        up = self._get_user_profile(obj)
        return up.gardian_mobile_no if up else None

    # --- Teacher fields ---
    def get_teacher_qualification(self, obj):
        # Reserved for teacher qualification field if added later
        return None
