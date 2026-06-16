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
    city = serializers.CharField(source='school_profile.city', read_only=True, default='')
    state = serializers.CharField(source='school_profile.state', read_only=True, default='')
    phone_number = serializers.CharField(source='school_profile.phone', read_only=True, default='')
    school_name = serializers.CharField(source='school_profile.institution.name', read_only=True, default='')

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'city', 'state', 'phone_number', 'school_name', 'role']
