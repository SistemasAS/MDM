from flask import Blueprint
from src.models.device import db
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json
db = SQLAlchemy()

device_bp = Blueprint('device', __name__)


class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(100), unique=True, nullable=False, index=True)
    device_name = db.Column(db.String(100), nullable=True)  # Nombre personalizado
    device_token = db.Column(db.String(200), unique=True, nullable=True)
    manufacturer = db.Column(db.String(100), nullable=True)
    model = db.Column(db.String(100), nullable=True)
    android_version = db.Column(db.String(20), nullable=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')
    config_json = db.Column(db.Text, default='{}')

    location_history = db.relationship(
        'LocationHistory', backref='device', lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self, include_token=False):
        result = {
            'id': self.id,
            'serial_number': self.serial_number,
            'device_name': self.device_name or '',
            'manufacturer': self.manufacturer,
            'model': self.model,
            'android_version': self.android_version,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'status': self.status,
            'config': self.get_config(),
        }
        if include_token:
            result['device_token'] = self.device_token
        return result

    def get_config(self):
        try:
            return json.loads(self.config_json) if self.config_json else {}
        except json.JSONDecodeError:
            return {}

    def set_config(self, config_dict):
        self.config_json = json.dumps(config_dict)

    def get_default_config(self):
        return {
            'kiosk_mode_enabled': False,
            'allowed_apps': [],
            'wifi_disabled': False,
            'data_disabled': False,
            'location_frequency_minutes': 5,
            'disallow_factory_reset': True,
            'disallow_safe_boot': True,
            'disallow_airplane_mode': False,
        }


class Policy(db.Model):
    __tablename__ = 'policies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    config_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'config': self.get_config(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def get_config(self):
        try:
            return json.loads(self.config_json) if self.config_json else {}
        except json.JSONDecodeError:
            return {}

    def set_config(self, config_dict):
        self.config_json = json.dumps(config_dict)


class LocationHistory(db.Model):
    __tablename__ = 'location_history'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float, nullable=True)
    altitude = db.Column(db.Float, nullable=True)
    speed = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'accuracy': self.accuracy,
            'altitude': self.altitude,
            'speed': self.speed,
            'timestamp': self.timestamp.isoformat(),
        }