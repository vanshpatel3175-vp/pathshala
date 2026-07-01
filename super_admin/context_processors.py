from .models import ThemeSetting, AcademicYear

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


def academic_year_context(request):
    """Injects academic year data into every template for the year-switcher dropdown."""
    try:
        active_years = list(AcademicYear.objects.filter(is_active=True))
        selected_year_id = request.session.get('academic_year_id')
        selected_year = None

        if selected_year_id:
            selected_year = AcademicYear.objects.filter(pk=selected_year_id).first()

        if not selected_year and request.user.is_authenticated:
            # Fall back to the institution's configured current year
            institution = None
            try:
                if hasattr(request.user, 'school_profile') and request.user.school_profile and request.user.school_profile.institution:
                    institution = request.user.school_profile.institution
                else:
                    rp = request.user.role_profiles.select_related('institution__current_academic_year').first()
                    if rp:
                        institution = rp.institution
            except Exception:
                pass

            if institution and institution.current_academic_year:
                selected_year = institution.current_academic_year

        return {
            'active_academic_years': active_years,
            'selected_academic_year': selected_year,
        }
    except Exception:
        return {
            'active_academic_years': [],
            'selected_academic_year': None,
        }
