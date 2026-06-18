"""
URL configuration for OperaStock.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def root_redirect(request):
    """Redirige a dashboard si está autenticado, sino a login."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return redirect('accounts:login')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', root_redirect, name='root'),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
]

# Personalización del panel de administración
admin.site.site_header = 'OperaStock — Administración'
admin.site.site_title = 'OperaStock Admin'
admin.site.index_title = 'Panel de Administración'
