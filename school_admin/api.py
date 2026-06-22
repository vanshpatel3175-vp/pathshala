from rest_framework.views import APIView
from rest_framework import status
from .serializer import SchoolSignupSerializer,UserResponseSerializer,schoolloginSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import get_user_model,authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import SchoolAdminProfile

User = get_user_model()

class SchoolSignupAPIView(APIView):
    def post(self, request):
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
    def post(self, request):
        serializer = schoolloginSerializer(data=request.data)
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return Response({
                "data": {
                    "success_key": 0,
                    "message": " Valid Email Id and password is required."
                }
            }, status=400)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user_obj = User.objects.filter(email=email).first()
        if not user_obj:
            user_obj = User.objects.filter(username=email).first()
            
        user = None
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
            
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                "data": {
                    "success_key": 1,
                    "message": "Login successful.",                    
                    "user": UserResponseSerializer(user).data,
                    "refresh token": str(refresh),
                    "access token": str(refresh.access_token),
                }
            }, status=200)
        else:
            return Response({
                "data": {
                    "success_key": 0,
                    "message": "Invalid email or password."
                }
            }, status=401)

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
        
        active_theme = ThemeSetting.objects.filter(is_active=True).first()
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
            
        theme, created = ThemeSetting.objects.get_or_create(name=db_code)
        theme.is_active = True
        theme.save()
        
        return Response({
            "data": {
                "success_key": 1,
                "message": "Theme updated successfully.",
                "active_theme": db_code
            }
        }, status=status.HTTP_200_OK)