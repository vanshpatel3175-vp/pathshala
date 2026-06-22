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

    def get_phone_number(self, obj):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'role', '') == 'SUPER ADMIN':
            return ""
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
    def get_role(self, obj):
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
            if u.role == 'SCHOOL STAFF' and hasattr(u, 'school_profile') and u.school_profile:
                inst = u.school_profile.institution
                roles.append({
                    "role": "SCHOOL_ADMIN",
                    "institution_id": inst.id if inst else None,
                    "institution_name": inst.name if inst else "Pending Approval"
                })
            elif u.role == 'TEACHER' and hasattr(u, 'teacher_profile') and u.teacher_profile:
                inst = u.teacher_profile.institution
                roles.append({
                    "role": "TEACHER",
                    "institution_id": inst.id if inst else None,
                    "institution_name": inst.name if inst else "Pending Approval"
                })
            elif u.role == 'STUDENT' and hasattr(u, 'student_profile') and u.student_profile:
                inst = u.student_profile.institution
                roles.append({
                    "role": "STUDENT",
                    "institution_id": inst.id if inst else None,
                    "institution_name": inst.name if inst else "Pending Approval"
                })
            elif u.role == 'SUPER ADMIN':
                roles.append({
                    "role": "SUPER_ADMIN",
                    "institution_id": None,
                    "institution_name": "Super Admin Portal"
                })
        return roles

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
