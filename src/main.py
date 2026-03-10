import os
import sys


# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from src.models.device import db
from src.routes.device import device_bp
from src.routes.admin import admin_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# ── Configuración ──────────────────────────────────────────────────────────────
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'CAMBIAR_EN_PRODUCCION_clave_muy_larga_y_aleatoria')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Base de datos: SQLite para desarrollo, PostgreSQL para producción
db_url = os.environ.get('DATABASE_URL')
if db_url:
    # Render/Heroku usan postgres://, SQLAlchemy necesita postgresql://
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'app.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

# ── CORS (permitir llamadas desde el frontend) ─────────────────────────────────
# En producción, cambiar '*' por el dominio real del frontend
CORS(app, resources={r'/api/*': {'origins': '*'}, r'/admin/*': {'origins': '*'}})

# ── Blueprints ─────────────────────────────────────────────────────────────────
app.register_blueprint(device_bp, url_prefix='/api/v1')
app.register_blueprint(admin_bp, url_prefix='/admin/v1')

# ── Base de datos ──────────────────────────────────────────────────────────────
db.init_app(app)
with app.app_context():
    db.create_all()
    # Migración manual: agregar columna device_name si no existe
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE devices ADD COLUMN device_name VARCHAR(100)'))
            conn.commit()
    except Exception:
        pass  # La columna ya existe, ignorar

# ── Manejo de errores global ───────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Recurso no encontrado'}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'Método no permitido'}), 405

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return jsonify({'error': 'Error interno del servidor'}), 500

# ── Frontend estático ──────────────────────────────────────────────────────────
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return 'Static folder not configured', 404

    if path and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        return jsonify({'message': 'MDM Backend API está corriendo ✓', 'version': '1.0'}), 200


if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=debug)