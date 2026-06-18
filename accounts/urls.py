from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # ─── Autenticación ───
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ─── Gestión de usuarios ───
    path('usuarios/', views.user_list, name='user_list'),
    path('usuarios/<int:pk>/editar/', views.user_edit, name='user_edit'),
    path('usuarios/<int:pk>/activar/', views.user_activate, name='user_activate'),
    path('usuarios/<int:pk>/desactivar/', views.user_deactivate, name='user_deactivate'),
    path('usuarios/<int:pk>/cambiar-rol/', views.user_change_role, name='user_change_role'),

    # ─── Gestión de sesiones ───
    path('sesiones/', views.session_list, name='session_list'),
    path('sesiones/<int:pk>/cerrar/', views.session_close, name='session_close'),
]
