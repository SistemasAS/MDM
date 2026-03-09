"""
Rutas de administración para el Panel Web.
Prefijo: /admin/v1
Todas las rutas requieren autenticación de administrador.
"""
from flask import Blueprint, request, jsonify
from src.models.device import db, Device, LocationHistory, Policy
from src.auth import require_admin_auth
from datetime import datetime

admin_bp = Blueprint('admin', __name__)


# ─────────────────────────────────────────────
# DISPOSITIVOS
# ─────────────────────────────────────────────

@admin_bp.route('/devices', methods=['GET'])
@require_admin_auth
def list_devices():
    status_filter = request.args.get('status')
    query = Device.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    devices = query.order_by(Device.last_seen.desc()).all()
    return jsonify({'devices': [d.to_dict() for d in devices], 'total': len(devices)}), 200


@admin_bp.route('/devices/<serial>', methods=['GET'])
@require_admin_auth
def get_device_details(serial):
    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    last_location = (
        LocationHistory.query
        .filter_by(device_id=device.id)
        .order_by(LocationHistory.timestamp.desc())
        .first()
    )

    return jsonify({
        'device': device.to_dict(),
        'last_location': last_location.to_dict() if last_location else None,
    }), 200


@admin_bp.route('/devices/<serial>/name', methods=['PATCH'])
@require_admin_auth
def update_device_name(serial):
    """Actualiza el nombre personalizado de un dispositivo."""
    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('device_name', '').strip()

    device.device_name = name
    db.session.commit()

    return jsonify({'message': 'Nombre actualizado', 'device': device.to_dict()}), 200


@admin_bp.route('/devices/<serial>/status', methods=['PATCH'])
@require_admin_auth
def update_device_status(serial):
    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    data = request.get_json(silent=True) or {}
    new_status = data.get('status')

    if new_status not in ('active', 'inactive', 'blocked'):
        return jsonify({'error': "Estado debe ser 'active', 'inactive' o 'blocked'"}), 400

    device.status = new_status
    db.session.commit()

    return jsonify({'message': f'Estado actualizado a {new_status}', 'device': device.to_dict()}), 200


@admin_bp.route('/devices/<serial>/policy', methods=['POST'])
@require_admin_auth
def assign_policy(serial):
    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Body JSON requerido'}), 400

    if 'policy_id' in data:
        policy = Policy.query.get(data['policy_id'])
        if not policy:
            return jsonify({'error': 'Política no encontrada'}), 404
        config = policy.get_config()
    else:
        current_config = device.get_config() or device.get_default_config()
        config = {
            'kiosk_mode_enabled': data.get('kiosk_mode_enabled', current_config.get('kiosk_mode_enabled', False)),
            'allowed_apps': data.get('allowed_apps', current_config.get('allowed_apps', [])),
            'wifi_disabled': data.get('wifi_disabled', current_config.get('wifi_disabled', False)),
            'data_disabled': data.get('data_disabled', current_config.get('data_disabled', False)),
            'location_frequency_minutes': int(data.get('location_frequency_minutes', current_config.get('location_frequency_minutes', 5))),
            'disallow_factory_reset': data.get('disallow_factory_reset', current_config.get('disallow_factory_reset', True)),
            'disallow_safe_boot': data.get('disallow_safe_boot', current_config.get('disallow_safe_boot', True)),
            'disallow_airplane_mode': data.get('disallow_airplane_mode', current_config.get('disallow_airplane_mode', False)),
        }

    device.set_config(config)
    db.session.commit()

    return jsonify({'message': 'Política asignada exitosamente', 'device': device.to_dict()}), 200


@admin_bp.route('/devices/<serial>/history', methods=['GET'])
@require_admin_auth
def get_location_history(serial):
    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = min(int(request.args.get('limit', 500)), 5000)

    query = LocationHistory.query.filter_by(device_id=device.id)

    if start_date:
        try:
            query = query.filter(LocationHistory.timestamp >= datetime.fromisoformat(start_date))
        except ValueError:
            return jsonify({'error': 'Formato de start_date inválido'}), 400

    if end_date:
        try:
            query = query.filter(LocationHistory.timestamp <= datetime.fromisoformat(end_date))
        except ValueError:
            return jsonify({'error': 'Formato de end_date inválido'}), 400

    locations = query.order_by(LocationHistory.timestamp.desc()).limit(limit).all()

    return jsonify({
        'device': device.to_dict(),
        'history': [loc.to_dict() for loc in locations],
        'total': len(locations),
    }), 200


@admin_bp.route('/devices/<serial>', methods=['DELETE'])
@require_admin_auth
def delete_device(serial):
    device = Device.query.filter_by(serial_number=serial).first()
    if not device:
        return jsonify({'error': 'Dispositivo no encontrado'}), 404

    db.session.delete(device)
    db.session.commit()
    return jsonify({'message': f'Dispositivo {serial} eliminado'}), 200


# ─────────────────────────────────────────────
# POLÍTICAS
# ─────────────────────────────────────────────

@admin_bp.route('/policies', methods=['GET'])
@require_admin_auth
def list_policies():
    policies = Policy.query.order_by(Policy.created_at.desc()).all()
    return jsonify({'policies': [p.to_dict() for p in policies], 'total': len(policies)}), 200


@admin_bp.route('/policies', methods=['POST'])
@require_admin_auth
def create_policy():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Body JSON requerido'}), 400

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'El campo name es requerido'}), 400

    if Policy.query.filter_by(name=name).first():
        return jsonify({'error': 'Ya existe una política con ese nombre'}), 409

    config = {
        'kiosk_mode_enabled': data.get('kiosk_mode_enabled', False),
        'allowed_apps': data.get('allowed_apps', []),
        'wifi_disabled': data.get('wifi_disabled', False),
        'data_disabled': data.get('data_disabled', False),
        'location_frequency_minutes': int(data.get('location_frequency_minutes', 5)),
        'disallow_factory_reset': data.get('disallow_factory_reset', True),
        'disallow_safe_boot': data.get('disallow_safe_boot', True),
        'disallow_airplane_mode': data.get('disallow_airplane_mode', False),
    }

    policy = Policy(name=name, description=data.get('description'))
    policy.set_config(config)
    db.session.add(policy)
    db.session.commit()

    return jsonify({'message': 'Política creada', 'policy': policy.to_dict()}), 201


@admin_bp.route('/policies/<int:policy_id>', methods=['PUT'])
@require_admin_auth
def update_policy(policy_id):
    policy = Policy.query.get(policy_id)
    if not policy:
        return jsonify({'error': 'Política no encontrada'}), 404

    data = request.get_json(silent=True) or {}
    current_config = policy.get_config()

    if 'name' in data:
        name = data['name'].strip()
        existing = Policy.query.filter_by(name=name).first()
        if existing and existing.id != policy_id:
            return jsonify({'error': 'Ya existe una política con ese nombre'}), 409
        policy.name = name

    if 'description' in data:
        policy.description = data['description']

    config = {
        'kiosk_mode_enabled': data.get('kiosk_mode_enabled', current_config.get('kiosk_mode_enabled', False)),
        'allowed_apps': data.get('allowed_apps', current_config.get('allowed_apps', [])),
        'wifi_disabled': data.get('wifi_disabled', current_config.get('wifi_disabled', False)),
        'data_disabled': data.get('data_disabled', current_config.get('data_disabled', False)),
        'location_frequency_minutes': int(data.get('location_frequency_minutes', current_config.get('location_frequency_minutes', 5))),
        'disallow_factory_reset': data.get('disallow_factory_reset', current_config.get('disallow_factory_reset', True)),
        'disallow_safe_boot': data.get('disallow_safe_boot', current_config.get('disallow_safe_boot', True)),
        'disallow_airplane_mode': data.get('disallow_airplane_mode', current_config.get('disallow_airplane_mode', False)),
    }

    policy.set_config(config)
    db.session.commit()

    return jsonify({'message': 'Política actualizada', 'policy': policy.to_dict()}), 200


@admin_bp.route('/policies/<int:policy_id>', methods=['DELETE'])
@require_admin_auth
def delete_policy(policy_id):
    policy = Policy.query.get(policy_id)
    if not policy:
        return jsonify({'error': 'Política no encontrada'}), 404

    db.session.delete(policy)
    db.session.commit()
    return jsonify({'message': f'Política "{policy.name}" eliminada'}), 200


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@admin_bp.route('/dashboard', methods=['GET'])
@require_admin_auth
def dashboard():
    from datetime import timedelta

    total = Device.query.count()
    active = Device.query.filter_by(status='active').count()
    inactive = Device.query.filter_by(status='inactive').count()
    blocked = Device.query.filter_by(status='blocked').count()

    ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
    online = Device.query.filter(
        Device.last_seen >= ten_min_ago,
        Device.status == 'active'
    ).count()

    total_locations = LocationHistory.query.count()

    return jsonify({
        'summary': {
            'total_devices': total,
            'active': active,
            'inactive': inactive,
            'blocked': blocked,
            'online_last_10min': online,
            'total_location_records': total_locations,
        }
    }), 200