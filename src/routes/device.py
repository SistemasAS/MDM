"""
Rutas para los dispositivos Android (DPC).
Prefijo: /api/v1
"""
from flask import Blueprint, request, jsonify
from src.models.device import db, Device, LocationHistory
from src.auth import require_device_auth, generate_device_token, verify_registration_key
from datetime import datetime

device_bp = Blueprint('device', __name__)


@device_bp.route('/devices/register', methods=['POST'])
def register_device():
    """
    Registro inicial del dispositivo.
    
    Body JSON:
        registration_key (str): Clave secreta de registro
        serial_number    (str): Número de serie del dispositivo
        manufacturer     (str, opcional): Fabricante
        model            (str, opcional): Modelo
        android_version  (str, opcional): Versión de Android

    Retorna:
        device_token (str): JWT para autenticar futuras requests
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Body JSON requerido'}), 400

    # Validar clave de registro
    reg_key = data.get('registration_key', '')
    if not verify_registration_key(reg_key):
        return jsonify({'error': 'Clave de registro inválida'}), 403

    serial_number = data.get('serial_number', '').strip()
    if not serial_number:
        return jsonify({'error': 'serial_number es requerido'}), 400

    # Si el dispositivo ya existe, renovar token (re-enrolamiento)
    device = Device.query.filter_by(serial_number=serial_number).first()

    if device:
        # Re-enrolamiento: actualizar datos y renovar token
        device.manufacturer = data.get('manufacturer', device.manufacturer)
        device.model = data.get('model', device.model)
        device.android_version = data.get('android_version', device.android_version)
        device.last_seen = datetime.utcnow()
        device.status = 'active'
        token = generate_device_token(serial_number)
        device.device_token = token
        db.session.commit()
        return jsonify({
            'message': 'Dispositivo re-enrolado exitosamente',
            'device_token': token,
            'device': device.to_dict(),
        }), 200

    # Nuevo dispositivo
    new_device = Device(
        serial_number=serial_number,
        manufacturer=data.get('manufacturer'),
        model=data.get('model'),
        android_version=data.get('android_version'),
        status='active',
    )
    # Configuración por defecto
    new_device.set_config(new_device.get_default_config())

    token = generate_device_token(serial_number)
    new_device.device_token = token

    db.session.add(new_device)
    db.session.commit()

    return jsonify({
        'message': 'Dispositivo registrado exitosamente',
        'device_token': token,
        'device': new_device.to_dict(),
    }), 201


@device_bp.route('/devices/<serial>/location', methods=['POST'])
@require_device_auth
def report_location(serial):
    """
    El dispositivo reporta su ubicación actual.
    Solo puede reportar su propia ubicación (validado por JWT).
    
    Body JSON:
        latitude  (float): Latitud
        longitude (float): Longitud
        accuracy  (float, opcional): Precisión en metros
        altitude  (float, opcional): Altitud en metros
        speed     (float, opcional): Velocidad en m/s
        timestamp (str,   opcional): ISO 8601, si se omite se usa la hora del servidor
    """
    # Verificar que el token corresponde al serial del path
    if request.device_serial != serial:
        return jsonify({'error': 'No autorizado para este dispositivo'}), 403

    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    if device.status == 'blocked':
        return jsonify({'error': 'Dispositivo bloqueado'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Body JSON requerido'}), 400

    try:
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
    except (KeyError, ValueError, TypeError):
        return jsonify({'error': 'latitude y longitude son requeridos y deben ser numéricos'}), 400

    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return jsonify({'error': 'Coordenadas fuera de rango'}), 400

    # Parsear timestamp opcional
    timestamp = datetime.utcnow()
    if 'timestamp' in data:
        try:
            timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass  # Usar hora del servidor si el formato es inválido

    location = LocationHistory(
        device_id=device.id,
        latitude=latitude,
        longitude=longitude,
        accuracy=data.get('accuracy'),
        altitude=data.get('altitude'),
        speed=data.get('speed'),
        timestamp=timestamp,
    )

    # Actualizar last_seen del dispositivo
    device.last_seen = datetime.utcnow()

    db.session.add(location)
    db.session.commit()

    return jsonify({'message': 'Ubicación registrada', 'location_id': location.id}), 201


@device_bp.route('/devices/<serial>/config', methods=['GET'])
@require_device_auth
def get_device_config(serial):
    """
    El dispositivo descarga su configuración actual (políticas, restricciones, etc).
    Solo puede leer su propia configuración.
    """
    if request.device_serial != serial:
        return jsonify({'error': 'No autorizado para este dispositivo'}), 403

    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    # Actualizar last_seen (heartbeat)
    device.last_seen = datetime.utcnow()
    db.session.commit()

    config = device.get_config()
    if not config:
        config = device.get_default_config()

    return jsonify({
        'serial_number': serial,
        'config': config,
        'status': device.status,
    }), 200


@device_bp.route('/devices/<serial>/heartbeat', methods=['POST'])
@require_device_auth
def heartbeat(serial):
    """
    Señal periódica del dispositivo para marcar que está activo.
    Puede incluir información de estado adicional.
    """
    if request.device_serial != serial:
        return jsonify({'error': 'No autorizado para este dispositivo'}), 403

    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    device.last_seen = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'OK', 'server_time': datetime.utcnow().isoformat()}), 200