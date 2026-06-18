from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.http import JsonResponse
from .forms import CustomUserCreationForm, UserEditForm
from .models import CustomUser, UserSession
from .decorators import admin_required


# ═══════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════

def register_view(request):
    """Vista de registro de nuevos usuarios. Siempre crea como OPERADOR."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f'Cuenta creada correctamente. Rol asignado: Operador.'
            )
            return redirect('dashboard:home')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """Vista de inicio de sesión."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido/a de nuevo, {user.username}!')
            next_url = request.GET.get('next', 'dashboard:home')
            return redirect(next_url)
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    """Vista de cierre de sesión."""
    # Marcar la sesión como inactiva antes de cerrar
    if request.user.is_authenticated and request.session.session_key:
        UserSession.objects.filter(
            session_key=request.session.session_key
        ).update(is_active=False)

    logout(request)
    messages.info(request, 'Has cerrado sesión correctamente.')
    return redirect('accounts:login')


# ═══════════════════════════════════════════════════════════
# PERFIL DE USUARIO (todos los usuarios autenticados)
# ═══════════════════════════════════════════════════════════

def profile_edit(request):
    """Permite al usuario autenticado editar su propia información."""
    if not request.user.is_authenticated:
        return redirect('accounts:login')

    usuario = request.user

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu información ha sido actualizada correctamente.')
            return redirect('accounts:profile_edit')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = UserEditForm(instance=usuario)

    return render(request, 'accounts/profile_edit.html', {
        'form': form,
        'usuario': usuario
    })


# ═══════════════════════════════════════════════════════════
# GESTIÓN DE USUARIOS (solo admin/superuser)
# ═══════════════════════════════════════════════════════════

@admin_required
def user_list(request):
    """Lista todos los usuarios registrados."""
    usuarios = CustomUser.objects.all().order_by('-fecha_creacion')
    return render(request, 'accounts/user_list.html', {'usuarios': usuarios})


@admin_required
def user_edit(request, pk):
    """Edita los datos básicos de un usuario."""
    usuario = get_object_or_404(CustomUser, pk=pk)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=usuario)
        if form.is_valid():
            # Validación: no permitir que se desactive a sí mismo
            if usuario == request.user and not form.cleaned_data['is_active']:
                messages.error(request, 'No puedes desactivarte a ti mismo.')
                return render(request, 'accounts/user_edit.html', {
                    'form': form, 'usuario': usuario
                })

            # Validación: no dejar sistema sin administradores
            nuevo_rol = form.cleaned_data['rol']
            if (
                usuario == request.user
                and usuario.rol == CustomUser.Rol.ADMINISTRADOR
                and nuevo_rol != CustomUser.Rol.ADMINISTRADOR
            ):
                otros_admins = CustomUser.objects.filter(
                    rol=CustomUser.Rol.ADMINISTRADOR, is_active=True
                ).exclude(pk=usuario.pk).count()

                if otros_admins == 0 and not CustomUser.objects.filter(
                    is_superuser=True, is_active=True
                ).exclude(pk=usuario.pk).exists():
                    messages.error(
                        request,
                        'No puedes quitarte el rol de Administrador porque '
                        'el sistema quedaría sin administradores.'
                    )
                    return render(request, 'accounts/user_edit.html', {
                        'form': form, 'usuario': usuario
                    })

            form.save()
            messages.success(request, f'Usuario "{usuario.username}" actualizado correctamente.')
            return redirect('accounts:user_list')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = UserEditForm(instance=usuario)

    return render(request, 'accounts/user_edit.html', {
        'form': form, 'usuario': usuario
    })


@admin_required
def user_activate(request, pk):
    """Activa un usuario (solo por POST)."""
    if request.method != 'POST':
        messages.error(request, 'Acción no permitida.')
        return redirect('accounts:user_list')

    usuario = get_object_or_404(CustomUser, pk=pk)
    usuario.is_active = True
    usuario.save()
    messages.success(request, f'Usuario "{usuario.username}" activado correctamente.')
    return redirect('accounts:user_list')


@admin_required
def user_deactivate(request, pk):
    """Desactiva un usuario (solo por POST)."""
    if request.method != 'POST':
        messages.error(request, 'Acción no permitida.')
        return redirect('accounts:user_list')

    usuario = get_object_or_404(CustomUser, pk=pk)

    if usuario == request.user:
        messages.error(request, 'No puedes desactivarte a ti mismo.')
        return redirect('accounts:user_list')

    usuario.is_active = False
    usuario.save()
    messages.success(request, f'Usuario "{usuario.username}" desactivado correctamente.')
    return redirect('accounts:user_list')


@admin_required
def user_change_role(request, pk):
    """Cambia el rol de un usuario entre OPERADOR y ADMINISTRADOR (solo por POST)."""
    if request.method != 'POST':
        messages.error(request, 'Acción no permitida.')
        return redirect('accounts:user_list')

    usuario = get_object_or_404(CustomUser, pk=pk)
    nuevo_rol = request.POST.get('rol')

    if nuevo_rol not in [CustomUser.Rol.ADMINISTRADOR, CustomUser.Rol.OPERADOR]:
        messages.error(request, 'Rol no válido.')
        return redirect('accounts:user_list')

    # Validación: no dejar sistema sin administradores
    if (
        usuario == request.user
        and usuario.rol == CustomUser.Rol.ADMINISTRADOR
        and nuevo_rol == CustomUser.Rol.OPERADOR
    ):
        otros_admins = CustomUser.objects.filter(
            rol=CustomUser.Rol.ADMINISTRADOR, is_active=True
        ).exclude(pk=usuario.pk).count()

        if otros_admins == 0 and not CustomUser.objects.filter(
            is_superuser=True, is_active=True
        ).exclude(pk=usuario.pk).exists():
            messages.error(
                request,
                'No puedes quitarte el rol de Administrador porque '
                'el sistema quedaría sin administradores.'
            )
            return redirect('accounts:user_list')

    rol_anterior = usuario.get_rol_display()
    usuario.rol = nuevo_rol
    usuario.save()
    messages.success(
        request,
        f'Rol de "{usuario.username}" cambiado de {rol_anterior} a {usuario.get_rol_display()}.'
    )
    return redirect('accounts:user_list')


# ═══════════════════════════════════════════════════════════
# GESTIÓN DE SESIONES (solo admin/superuser)
# ═══════════════════════════════════════════════════════════

@admin_required
def session_list(request):
    """Lista todas las sesiones registradas."""
    sesiones = UserSession.objects.select_related('user').all().order_by('-last_activity')
    return render(request, 'accounts/session_list.html', {'sesiones': sesiones})


@admin_required
def session_close(request, pk):
    """Cierra la sesión de un usuario (solo por POST)."""
    if request.method != 'POST':
        messages.error(request, 'Acción no permitida.')
        return redirect('accounts:session_list')

    sesion = get_object_or_404(UserSession, pk=pk)

    # Intentar eliminar la sesión de Django
    try:
        session = Session.objects.get(session_key=sesion.session_key)
        session.delete()
        message = 'Sesión cerrada correctamente.'
    except Session.DoesNotExist:
        message = 'La sesión ya no existía en el servidor. Se marcó como inactiva.'

    # Marcar como inactiva en nuestro registro
    sesion.is_active = False
    sesion.save()

    # Detectar si es una solicitud AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'session_id': pk,
        })

    messages.success(request, message)
    return redirect('accounts:session_list')
