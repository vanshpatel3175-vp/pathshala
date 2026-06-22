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