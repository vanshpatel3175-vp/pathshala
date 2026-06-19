from .models import ThemeSetting

def global_theme(request):
    try:
        active_theme = ThemeSetting.objects.filter(is_active=True).first()
        if active_theme:
            return {'active_theme_code': active_theme.name}
    except Exception:
        pass
    return {'active_theme_code': 'default'}
