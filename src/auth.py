"""
Utilidades de autenticación para el MDM.
- JWT para dispositivos (firmado, expirable)
- Token estático para admin (en producción, usar JWT con login)
"""
import jwt
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app

# En producción, cargar desde variable de entorno
ADMIN_TOKEN = os.environ.get('MDM_ADMIN_TOKEN', 'CAMBIAR_EN_PRODUCCION_' + secrets.token_hex(16))
REGISTRATION_KEY = os.environ.get('MDM_REGISTRATION_KEY', 'REG_KEY_CAMBIAR_EN_PRODUCCION')


def generate_device_token(serial_number: str) -> str:
    """Genera un JWT firmado para un dispositivo."""
    payload = {
        'serial': serial_number,
        'type': 'device',
        'iat': datetime.utcnow(),
        # Los tokens de dispositivo duran 1 año (renovar al hacer heartbeat)
        'exp': datetime.utcnow() + timedelta(days=365),
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def decode_device_token(token: str) -> dict | None:
    """Decodifica y valida un JWT de dispositivo. Retorna payload o None."""
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        if payload.get('type') != 'device':
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_device_auth(f):
    """Decorador: requiere JWT válido de dispositivo en el header Authorization."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token de dispositivo requerido'}), 401

        token = auth_header.replace('Bearer ', '', 1)
        payload = decode_device_token(token)
        if not payload:
            return jsonify({'error': 'Token inválido o expirado'}), 401

        # Inyectar el serial del dispositivo en el contexto
        request.device_serial = payload['serial']
        return f(*args, **kwargs)
    return decorated


def require_admin_auth(f):
    """Decorador: requiere token de administrador en el header Authorization."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '', 1)

        if not token or token != ADMIN_TOKEN:
            return jsonify({'error': 'No autorizado'}), 401

        return f(*args, **kwargs)
    return decorated


def verify_registration_key(key: str) -> bool:
    """Verifica la clave de registro para nuevos dispositivos."""
    return key == REGISTRATION_KEY