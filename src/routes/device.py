"""
Rutas del dispositivo Android.
Prefijo: /api/v1
"""
from flask import Blueprint, request, jsonify
from src.models.device import db, Device, LocationHistory
from src.auth import require_device_auth
from datetime import datetime

device_bp = Blueprint('device', __name__)


@device_bp.route('/devices/register', methods=['POST'])
def register_device():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Body JSON requerido'}), 400

    from src.auth import verify_registration_key, generate_device_token
    if not verify_registration_key(data.get('registration_key', '')):
        return jsonify({'error': 'Clave de registro inválida'}), 401

    serial = data.get('serial_number', '').strip()
    if not serial:
        return jsonify({'error': 'serial_number requerido'}), 400

    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        device = Device(serial_number=serial)
        db.session.add(device)

    device.manufacturer = data.get('manufacturer')
    device.model = data.get('model')
    device.android_version = data.get('android_version')
    device.last_seen = datetime.utcnow()
    device.status = 'active'

    token = generate_device_token(serial)
    device.device_token = token
    db.session.commit()

    message = 'Dispositivo re-enrolado exitosamente' if device.id else 'Dispositivo registrado exitosamente'

    return jsonify({
        'message': message,
        'device_token': token,
        'device': device.to_dict(),
    }), 201


@device_bp.route('/devices/<serial>/location', methods=['POST'])
@require_device_auth
def report_location(serial):
    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Body JSON requerido'}), 400

    lat = data.get('latitude')
    lng = data.get('longitude')
    if lat is None or lng is None:
        return jsonify({'error': 'latitude y longitude requeridos'}), 400

    location = LocationHistory(
        device_id=device.id,
        latitude=float(lat),
        longitude=float(lng),
        accuracy=data.get('accuracy'),
        altitude=data.get('altitude'),
        speed=data.get('speed'),
    )
    db.session.add(location)
    device.last_seen = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Ubicación registrada'}), 201


@device_bp.route('/devices/<serial>/config', methods=['GET'])
@require_device_auth
def get_config(serial):
    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    device.last_seen = datetime.utcnow()
    db.session.commit()

    config = device.get_config()
    if not config:
        config = device.get_default_config()

    return jsonify({
        'serial_number': serial,
        'status': device.status,
        'config': config,
    }), 200


@device_bp.route('/devices/<serial>/heartbeat', methods=['POST'])
@require_device_auth
def heartbeat(serial):
    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    device.last_seen = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'OK', 'status': device.status}), 200