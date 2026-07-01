from rest_framework.views import APIView
from rest_framework import status
from .serializer import (
    SchoolSignupSerializer, SchoolLoginAPISerializer, LegacyLoginUserSerializer,
    LoginSerializer, StudentProfileSerializer, TeacherProfileSerializer, TrusteeProfileSerializer
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

class ThemeAPIView(APIView):
    def get(self, request):
        from super_admin.models import ThemeSetting
        from .serializer import themeserializer
        
        themes_data = [
            {'code': 'default', 'name': 'Default Dark Theme', 'color': '#26a69a'},
            {'code': 'ocean-cyan', 'name': 'Ocean Cyan', 'color': '#00BCD4'},
            {'code': 'royal-blue', 'name': 'Royal Blue', 'color': '#2563EB'},
            {'code': 'premium-pink', 'name': 'Premium Pink', 'color': '#EC4899'},
        ]
        
        institution = None
        if request.user and request.user.is_authenticated:
            if hasattr(request.user, 'school_profile') and request.user.school_profile and request.user.school_profile.institution:
                institution = request.user.school_profile.institution
            else:
                first_role = request.user.role_profiles.first()
                if first_role and first_role.institution:
                    institution = first_role.institution
                    
        active_theme = None
        if institution:
            active_theme = ThemeSetting.objects.filter(institution=institution, is_active=True).first()
            
        if not active_theme:
            active_theme = ThemeSetting.objects.filter(institution__isnull=True, is_active=True).first()
            
        active_code = active_theme.name if active_theme else 'default'
        
        for theme in themes_data:
            theme['is_active'] = (theme['code'] == active_code)
            
        serializer = themeserializer(themes_data, many=True)
            
        return Response({
            "data": {
                "success_key": 1,
                "message": "Themes fetched successfully.",
                "themes": serializer.data
            }
        }, status=status.HTTP_200_OK)

    def post(self, request):
        from super_admin.models import ThemeSetting
        
        institution = None
        if request.user and request.user.is_authenticated:
            if hasattr(request.user, 'school_profile') and request.user.school_profile and request.user.school_profile.institution:
                institution = request.user.school_profile.institution
            else:
                first_role = request.user.role_profiles.first()
                if first_role and first_role.institution:
                    institution = first_role.institution
        
        # User might send "theme_code" or "code"
        theme_input = request.data.get('theme_code') or request.data.get('code')
        if not theme_input:
            return Response({
                "data": {
                    "success_key": 0,
                    "message": "theme_code is required."
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        theme_input = str(theme_input).strip()
        
        # If user passed hex code without #, add it
        if len(theme_input) == 6 and all(c in '0123456789ABCDEFabcdef' for c in theme_input):
            theme_input = '#' + theme_input
            
        # Map colors to codes
        color_mapping = {
            '#26A69A': 'default',
            '#00BCD4': 'ocean-cyan',
            '#2563EB': 'royal-blue',
            '#EC4899': 'premium-pink'
        }
        
        db_code = None
        # Check if they passed a color
        if theme_input.upper() in color_mapping:
            db_code = color_mapping[theme_input.upper()]
        else:
            # Check if they passed the string code directly
            valid_codes = [c[0] for c in ThemeSetting.THEME_CHOICES]
            if theme_input.lower() in valid_codes:
                db_code = theme_input.lower()
                
        if not db_code:
            return Response({
                "data": {
                    "success_key": 0,
                    "message": "Invalid theme code or color."
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        theme, created = ThemeSetting.objects.get_or_create(name=db_code, institution=institution)
        theme.is_active = True
        theme.save()
        
        return Response({
            "data": {
                "success_key": 1,
                "message": "Theme updated successfully.",
                "active_theme": db_code
            }
        }, status=status.HTTP_200_OK)

class LoginAPIView(APIView):
    """
    POST /api/login/
    Body: { "email": "...", "password": "..." }
    Response: { email, all_roles, access_token, refresh_token }
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            message = "Invalid email or password."
            if 'non_field_errors' in errors:
                message = errors['non_field_errors'][0]
            elif 'email' in errors:
                message = errors['email'][0]
            elif 'password' in errors:
                message = errors['password'][0]

            http_status = status.HTTP_400_BAD_REQUEST
            if "Invalid email or password" in str(message):
                http_status = status.HTTP_401_UNAUTHORIZED
            elif "inactive" in str(message).lower():
                http_status = status.HTTP_403_FORBIDDEN

            return Response({
                "success_key": 0,
                "message": message
            }, status=http_status)

        user = serializer.validated_data['user']

        # Collect all roles from role_profiles
        all_roles = []
        for rp in user.role_profiles.select_related('role', 'institution', 'branch').all():
            if rp.role_name and rp.role_name.upper() != 'USER':
                all_roles.append(rp.role_name)

        # Check if the user has a Student or Teacher role
        has_student_or_teacher = any(r.upper() in ('STUDENT', 'TEACHER') for r in all_roles)

        if has_student_or_teacher:
            all_roles = [r for r in all_roles if r.upper() not in ('SCHOOL_ADMIN', 'SUPER_ADMIN')]
        else:
            # Also include SCHOOL_ADMIN if user has a school_profile
            try:
                sp = user.school_profile
                if sp:
                    all_roles.append('SCHOOL_ADMIN')
            except Exception:
                pass

            # Include SUPER_ADMIN if superuser
            if user.is_superuser:
                all_roles.append('SUPER_ADMIN')

        # Remove duplicates while preserving order
        seen = set()
        unique_roles = []
        for r in all_roles:
            if r not in seen:
                seen.add(r)
                unique_roles.append(r)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            "success_key": 1,
            "message": "Login successful.",
            "email": user.email,
            "all_roles": unique_roles,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        }, status=status.HTTP_200_OK)


class VerifyProfileAPIView(APIView):
    """
    POST /api/auth/verify
    Body: { "access": "<jwt>", "refresh": "<jwt>" }   (refresh is optional)

    Returns profile details for every STUDENT and TEACHER role the authenticated
    user holds.  SCHOOL_ADMIN and SUPER_ADMIN roles are silently excluded —
    users with those roles cannot access profile data through this endpoint.

    If the user holds both STUDENT and TEACHER roles, both profiles appear
    in the `profiles` array.
    """
    authentication_classes = []
    permission_classes = []

    # Roles that this API exposes — anything else is silently skipped.
    ALLOWED_ROLES = {'STUDENT', 'TEACHER', "TRUSTEE"}

    def post(self, request):
        access_token  = request.data.get('access') or request.data.get('access_token')
        refresh_token = request.data.get('refresh') or request.data.get('refresh_token')

        if not access_token:
            return Response({
                "success_key": 0,
                "message": "Access token is required."
            }, status=status.HTTP_400_BAD_REQUEST)

        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.settings import api_settings
        from django.contrib.auth import get_user_model

        authenticator = JWTAuthentication()
        user = None
        try:
            validated_token = authenticator.get_validated_token(access_token)
            user = authenticator.get_user(validated_token)
        except (InvalidToken, TokenError):
            if refresh_token:
                try:
                    refresh = RefreshToken(refresh_token)
                    user_id = refresh.payload.get(api_settings.USER_ID_CLAIM, 'user_id')
                    User = get_user_model()
                    user = User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
                    
                    # Generate a new token pair and update variables so they are returned to client
                    new_refresh = RefreshToken.for_user(user)
                    access_token = str(new_refresh.access_token)
                    refresh_token = str(new_refresh)
                except Exception:
                    pass

        if not user or not user.is_active:
            return Response({
                "success_key": 0,
                "message": "Authentication credentials were not provided or are invalid."
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Check if the user has any allowed role profiles (STUDENT or TEACHER)
        # Exclude users with only SCHOOL_ADMIN or SUPER_ADMIN roles
        role_profiles = user.role_profiles.select_related(
            'role', 'institution', 'branch', 'address_record'
        ).all()

        has_allowed_role = any((rp.role_name or '').upper() in self.ALLOWED_ROLES for rp in role_profiles)
        if not has_allowed_role:
            return Response({
                "success_key": 0,
                "message": "Access denied for this role profile."
            }, status=status.HTTP_403_FORBIDDEN)

        profiles_data = []
        for rp in role_profiles:
            role_upper = (rp.role_name or '').upper()

            if role_upper not in self.ALLOWED_ROLES:
                # Silently skip USER, SCHOOL_ADMIN, SUPER_ADMIN, etc.
                continue

            if role_upper == 'STUDENT':
                serialized = StudentProfileSerializer(rp).data
            elif role_upper == 'TEACHER':
                serialized = TeacherProfileSerializer(rp).data
            elif role_upper == 'TRUSTEE':
                serialized = TrusteeProfileSerializer(rp).data
            else:
                continue

            profiles_data.append(serialized)

        return Response({
            "success_key": 1,
            "email": user.email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "profiles": profiles_data,
        }, status=status.HTTP_200_OK)
