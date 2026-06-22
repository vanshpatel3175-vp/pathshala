from rest_framework.views import APIView
from rest_framework import status
from .serializer import (
    SchoolSignupSerializer, SchoolLoginAPISerializer, LegacyLoginUserSerializer
)
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import get_user_model,authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import SchoolAdminProfile

User = get_user_model()

@api_view(['POST'])
def school_signup_api(request):
    serializer = SchoolSignupSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        # Remove password from the response data
        user_data = dict(serializer.validated_data)
        user_data.pop('password', None)
        
        return Response({
            
            'user': user_data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=201)
    return Response(serializer.errors, status=400)

class SchoolLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = SchoolLoginAPISerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            message = "Invalid email or password."
            if 'non_field_errors' in errors:
                message = errors['non_field_errors'][0]
            elif 'email' in errors:
                message = errors['email'][0]
            elif 'password' in errors:
                message = errors['password'][0]

            status_code = status.HTTP_400_BAD_REQUEST
            if "Invalid email or password" in str(message):
                status_code = status.HTTP_401_UNAUTHORIZED
            elif "inactive" in str(message).lower():
                status_code = status.HTTP_403_FORBIDDEN

            return Response({
                "data": {
                    "success_key": 0,
                    "message": message
                }
            }, status=status_code)

        authenticated_users = serializer.validated_data['authenticated_users']
        primary_user = authenticated_users[0]

        # Generate JWT and embed custom claims for the primary user
        refresh = RefreshToken.for_user(primary_user)
        role_name = getattr(primary_user, 'role', '')
        if role_name == 'SCHOOL STAFF':
            role_name = 'SCHOOL_ADMIN'
        elif role_name == 'SUPER ADMIN':
            role_name = 'SUPER_ADMIN'

        inst_id = None
        inst_name = ""
        if role_name == 'SCHOOL_ADMIN':
            if hasattr(primary_user, 'school_profile') and primary_user.school_profile.institution:
                inst_id = primary_user.school_profile.institution.id
                inst_name = primary_user.school_profile.institution.name
        elif role_name == 'TEACHER':
            if hasattr(primary_user, 'teacher_profile') and primary_user.teacher_profile.institution:
                inst_id = primary_user.teacher_profile.institution.id
                inst_name = primary_user.teacher_profile.institution.name
        elif role_name == 'STUDENT':
            if hasattr(primary_user, 'student_profile') and primary_user.student_profile.institution:
                inst_id = primary_user.student_profile.institution.id
                inst_name = primary_user.student_profile.institution.name

        refresh['role'] = role_name
        refresh['institution_id'] = inst_id
        refresh['institution_name'] = inst_name

        # Serialize user data - list if multiple profiles, dict if single profile
        if len(authenticated_users) > 1:
            user_data = LegacyLoginUserSerializer(authenticated_users, many=True).data
        else:
            user_data = LegacyLoginUserSerializer(primary_user).data

        return Response({
            "data": {
                "success_key": 1,
                "message": "Login successful.",
                "user": user_data,
                "refresh token": str(refresh),
                "access token": str(refresh.access_token)
            }
        }, status=status.HTTP_200_OK)

class SchoolLogoutAPIView(APIView):
    def post(self, request):
        try:
            email = request.data.get('email')
            if not email:
                return Response({
                    "data": {
                        "success_key": 0,
                        "message": "Email is required."
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                "data": {
                    "success_key": 1,
                    "message": "Logout successful."
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "data": {
                    "success_key": 0,
                    "message": str(e)
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)