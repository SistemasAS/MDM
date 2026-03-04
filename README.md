# MDM Backend — API REST (Flask)

Backend completo para la plataforma de Mobile Device Management.

## Estructura del Proyecto

```
mdm_backend/
├── src/
│   ├── main.py                  # Punto de entrada Flask
│   ├── auth.py                  # JWT y decoradores de autenticación
│   ├── models/
│   │   └── device.py            # Modelos SQLAlchemy (Device, Policy, LocationHistory)
│   ├── routes/
│   │   ├── device.py            # Endpoints para dispositivos Android (/api/v1)
│   │   └── admin.py             # Endpoints para el panel web (/admin/v1)
│   ├── static/
│   │   └── index.html           # Panel web (Frontend)
│   └── database/
│       └── app.db               # SQLite (auto-generado en desarrollo)
├── requirements.txt
├── .env.example                 # Plantilla de variables de entorno
└── README.md
```

## Instalación y Ejecución

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con valores reales
```

### 3. Ejecutar en desarrollo

```bash
cd src
python main.py
```

### 4. Ejecutar en producción (con Gunicorn)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 src.main:app
```

---

## Autenticación

### Para dispositivos Android (DPC)
Los dispositivos se autentican con un **JWT** obtenido al registrarse.

```
Authorization: Bearer <device_token>
```

### Para el panel de administración
El admin usa un token estático definido en `MDM_ADMIN_TOKEN`.

```
Authorization: Bearer <admin_token>
```

---

## Endpoints de Dispositivos (`/api/v1`)

### `POST /api/v1/devices/register`
Enrola un nuevo dispositivo (no requiere JWT previo).

**Body:**
```json
{
  "registration_key": "TU_CLAVE_DE_REGISTRO",
  "serial_number": "SN-ABC123",
  "manufacturer": "Samsung",
  "model": "Galaxy A54",
  "android_version": "14"
}
```

**Respuesta exitosa (201):**
```json
{
  "message": "Dispositivo registrado exitosamente",
  "device_token": "eyJ...",
  "device": { ... }
}
```

---

### `POST /api/v1/devices/{serial}/location`
El dispositivo reporta su ubicación. Requiere JWT.

**Body:**
```json
{
  "latitude": 14.6349,
  "longitude": -90.5069,
  "accuracy": 10.5,
  "altitude": 1500.0,
  "speed": 0.0,
  "timestamp": "2024-01-15T10:30:00"
}
```

---

### `GET /api/v1/devices/{serial}/config`
El dispositivo descarga su configuración/política actual. Requiere JWT.

**Respuesta:**
```json
{
  "serial_number": "SN-ABC123",
  "status": "active",
  "config": {
    "kiosk_mode_enabled": true,
    "allowed_apps": ["com.example.app"],
    "wifi_disabled": false,
    "data_disabled": false,
    "location_frequency_minutes": 5,
    "disallow_factory_reset": true,
    "disallow_safe_boot": true,
    "disallow_airplane_mode": false
  }
}
```

---

### `POST /api/v1/devices/{serial}/heartbeat`
Señal de vida periódica. Actualiza `last_seen`. Requiere JWT.

---

## Endpoints de Administración (`/admin/v1`)

### Dispositivos

| Método   | Endpoint                              | Descripción                           |
|----------|---------------------------------------|---------------------------------------|
| `GET`    | `/admin/v1/devices`                   | Listar todos los dispositivos         |
| `GET`    | `/admin/v1/devices/{serial}`          | Detalles + última ubicación           |
| `PATCH`  | `/admin/v1/devices/{serial}/status`   | Cambiar estado (active/inactive/blocked) |
| `POST`   | `/admin/v1/devices/{serial}/policy`   | Asignar política                      |
| `GET`    | `/admin/v1/devices/{serial}/history`  | Historial de ubicaciones              |
| `DELETE` | `/admin/v1/devices/{serial}`          | Eliminar dispositivo                  |

### Políticas (Plantillas)

| Método   | Endpoint                     | Descripción              |
|----------|------------------------------|--------------------------|
| `GET`    | `/admin/v1/policies`         | Listar plantillas        |
| `POST`   | `/admin/v1/policies`         | Crear plantilla          |
| `PUT`    | `/admin/v1/policies/{id}`    | Actualizar plantilla     |
| `DELETE` | `/admin/v1/policies/{id}`    | Eliminar plantilla       |

### Dashboard

| Método | Endpoint              | Descripción                      |
|--------|-----------------------|----------------------------------|
| `GET`  | `/admin/v1/dashboard` | Estadísticas generales           |

---

## Flujo de Comunicación Dispositivo ↔ Backend

```
1. [DISPOSITIVO] POST /api/v1/devices/register
        → Obtiene device_token (JWT)

2. [DISPOSITIVO] GET /api/v1/devices/{serial}/config   (cada N minutos)
        → Descarga política actual y aplica restricciones

3. [DISPOSITIVO] POST /api/v1/devices/{serial}/location  (cada X minutos)
        → Reporta GPS

4. [DISPOSITIVO] POST /api/v1/devices/{serial}/heartbeat  (cada ~5 min)
        → Señal de vida

5. [ADMIN WEB]  GET /admin/v1/devices
                GET /admin/v1/devices/{serial}/history
                POST /admin/v1/devices/{serial}/policy
        → Gestión completa
```

---

## Configuración de Política — Campos Disponibles

| Campo                         | Tipo        | Descripción                                    |
|-------------------------------|-------------|------------------------------------------------|
| `kiosk_mode_enabled`          | `bool`      | Activa el Lock Task Mode en el dispositivo     |
| `allowed_apps`                | `list[str]` | Package names de apps permitidas en kiosco     |
| `wifi_disabled`               | `bool`      | Bloquea configuración de Wi-Fi                 |
| `data_disabled`               | `bool`      | Bloquea configuración de datos móviles         |
| `location_frequency_minutes`  | `int`       | Cada cuántos minutos reportar GPS              |
| `disallow_factory_reset`      | `bool`      | Bloquea el restablecimiento de fábrica         |
| `disallow_safe_boot`          | `bool`      | Bloquea el modo seguro                         |
| `disallow_airplane_mode`      | `bool`      | Bloquea el modo avión                          |

---

## Variables de Entorno

| Variable              | Descripción                          | Default (solo dev)       |
|-----------------------|--------------------------------------|--------------------------|
| `SECRET_KEY`          | Clave para firmar JWT                | Valor hardcodeado inseguro |
| `MDM_ADMIN_TOKEN`     | Token del administrador              | Token aleatorio en cada inicio |
| `MDM_REGISTRATION_KEY`| Clave para enrolar dispositivos      | Valor hardcodeado inseguro |
| `DATABASE_URL`        | URL de PostgreSQL (opcional)         | SQLite local             |
| `FLASK_DEBUG`         | `true` / `false`                     | `true`                   |