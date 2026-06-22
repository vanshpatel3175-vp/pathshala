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
    date_of_birth = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name','date_of_birth', 'role', 'city', 'state', 'phone_number', 'school_name']

    def get_date_of_birth(self, obj):
        return obj.date_of_birth if hasattr(obj, "date_of_birth") else ""

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
