from .models import ThemeSetting

def global_theme(request):
    # Always apply default theme for login and signup pages
    login_signup_paths = ['/', '/login', '/login/', '/school/signup/', '/school/signup']
    if request.path in login_signup_paths or request.path.startswith('/login/') or request.path.startswith('/school/signup/'):
        return {'active_theme_code': 'default'}
        
    try:
        institution = None
        if request.user.is_authenticated:
            # Check school admin profile
            if hasattr(request.user, 'school_profile') and request.user.school_profile and request.user.school_profile.institution:
                institution = request.user.school_profile.institution
            else:
                # Check other roles
                first_role = request.user.role_profiles.first()
                if first_role and first_role.institution:
                    institution = first_role.institution

        if institution:
            # Institution specific theme
            active_theme = ThemeSetting.objects.filter(institution=institution, is_active=True).first()
            if active_theme:
                return {'active_theme_code': active_theme.name}
                
        # Global fallback
        global_theme = ThemeSetting.objects.filter(institution__isnull=True, is_active=True).first()
        if global_theme:
            return {'active_theme_code': global_theme.name}
            
    except Exception:
        pass
    return {'active_theme_code': 'default'}
