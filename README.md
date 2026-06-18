# 🏭 OperaStock

**Sistema inteligente de gestión operativa para el control de inventarios, producción y abastecimiento en pequeñas empresas alimentarias.**

---

## 📋 Descripción

OperaStock es un sistema web desarrollado en Django que permite a pequeñas empresas alimentarias gestionar de manera integral sus procesos de:

- **Inventario**: Control de materias primas y productos terminados.
- **Proveedores**: Gestión de proveedores y abastecimiento.
- **Producción**: Fórmulas de producción y órdenes de fabricación.
- **Alertas**: Detección de stock crítico.
- **Usuarios**: Autenticación con roles (Administrador, Operador, Almacén).

---

## 🛠️ Tecnologías

| Componente   | Tecnología       |
|-------------|------------------|
| Backend     | Python 3 + Django 5 |
| Base de datos | SQLite (desarrollo) |
| Frontend    | Bootstrap 5       |
| Servidor    | Django Dev Server  |

---

## 🚀 Instalación y ejecución

### 1. Clonar el repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd AppGestion
```

### 2. Crear entorno virtual

```bash
python -m venv venv
```

### 3. Activar entorno virtual

**Windows (cmd):**
```bash
venv\Scripts\activate
```

**Windows (PowerShell):**
```bash
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Ejecutar migraciones

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Crear superusuario

```bash
python manage.py createsuperuser
```

### 7. Ejecutar el servidor

```bash
python manage.py runserver
```

Abrir en el navegador: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🔑 Rutas principales

| Ruta                | Descripción              |
|--------------------|--------------------------|
| `/`                | Redirección automática   |
| `/accounts/login/` | Inicio de sesión         |
| `/accounts/register/` | Registro de usuario   |
| `/accounts/logout/` | Cerrar sesión           |
| `/dashboard/`      | Panel principal (protegido) |
| `/admin/`          | Panel de administración  |

---

## 📁 Estructura del proyecto

```
AppGestion/
├── config/            # Configuración principal de Django
├── accounts/          # Autenticación y usuarios
├── empresas/          # Gestión de empresas
├── inventario/        # Inventario, proveedores, movimientos
├── produccion/        # Fórmulas y órdenes de producción
├── dashboard/         # Panel principal con indicadores
├── templates/         # Plantillas HTML
├── static/            # Archivos estáticos
├── manage.py
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 📌 Avance actual (v0.1)

- [x] Estructura del proyecto Django
- [x] Modelo de usuario personalizado con roles
- [x] Registro, login y logout
- [x] Dashboard protegido con indicadores
- [x] Modelos: Empresa, Proveedor, MateriaPrima, ProductoTerminado, MovimientoInventario
- [x] Modelos: FormulaProducto, DetalleFormula, OrdenProduccion
- [x] Panel de administración configurado
- [x] Interfaz en español con Bootstrap 5

## 🔜 Próximo avance (v0.2)

- [ ] CRUD completo de inventario (Materias primas, Productos, Proveedores)
- [ ] Alertas de stock bajo / stock crítico
- [ ] Producción con descuento automático de materias primas
- [ ] Contacto y gestión de proveedores
- [ ] Reportes en PDF
- [ ] Dashboard avanzado con gráficos

---

## 👤 Autor

Proyecto de tesis — Sistema inteligente de gestión operativa.

---

## 📄 Licencia

Este proyecto es de uso académico.
