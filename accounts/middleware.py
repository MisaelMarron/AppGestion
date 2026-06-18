from django.utils import timezone
from .models import UserSession


class UserSessionMiddleware:
    """
    Middleware que registra y actualiza las sesiones activas de usuarios autenticados.
    Crea o actualiza un registro UserSession por cada sesión activa.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Solo procesar si hay un usuario autenticado y una sesión activa
        if (
            hasattr(request, 'user')
            and request.user.is_authenticated
            and hasattr(request, 'session')
            and request.session.session_key
        ):
            session_key = request.session.session_key
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

            # Crear o actualizar la sesión del usuario
            session, created = UserSession.objects.update_or_create(
                session_key=session_key,
                defaults={
                    'user': request.user,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'is_active': True,
                    'last_activity': timezone.now(),
                },
            )

        return response

    @staticmethod
    def _get_client_ip(request):
        """Obtiene la IP del cliente desde los headers del request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
