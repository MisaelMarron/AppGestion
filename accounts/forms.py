from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    """
    Formulario de registro público.
    No muestra el campo rol — todo usuario se crea como OPERADOR.
    """

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'telefono', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de usuario',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'correo@ejemplo.com',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(Opcional)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Contraseña',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirmar contraseña',
        })

    def save(self, commit=True):
        """Fuerza rol OPERADOR al guardar, sin importar lo que envíen."""
        user = super().save(commit=False)
        user.rol = CustomUser.Rol.OPERADOR
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    """
    Formulario de edición de usuario (usado por administradores).
    Permite cambiar username, email, telefono, rol e is_active.
    """

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'telefono', 'rol', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(Opcional)',
            }),
            'rol': forms.Select(attrs={
                'class': 'form-select',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
