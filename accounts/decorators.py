from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """
    Decorador que permite acceso solo a superusuarios o usuarios con rol ADMINISTRADOR.
    Si el usuario no cumple, redirige al dashboard con mensaje de error.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if request.user.is_superuser or request.user.rol == 'ADMINISTRADOR':
            return view_func(request, *args, **kwargs)
        messages.error(request, 'No tienes permisos para acceder a esta sección.')
        return redirect('dashboard:home')
    return _wrapped
