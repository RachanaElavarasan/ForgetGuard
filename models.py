from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(30), nullable=False)  # 'admin' or 'student'
    email = db.Column(db.String(120), nullable=False)
    assigned_room = db.Column(db.String(120), default='AI & Robotics Lab')
    created_at = db.Column(db.DateTime, default=get_utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'role': self.role,
            'email': self.email,
            'assigned_room': self.assigned_room
        }

class DeviceAuth(db.Model):
    __tablename__ = 'device_auth'
    id = db.Column(db.Integer, primary_key=True)
    api_key = db.Column(db.String(128), unique=True, nullable=False)
    device_name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'api_key': self.api_key,
            'device_name': self.device_name,
            'is_active': self.is_active
        }

class Room(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(50), nullable=False)
    is_occupied = db.Column(db.Boolean, default=True)
    last_motion_at = db.Column(db.DateTime, default=get_utc_now)
    empty_since = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)

    # Relationships
    objects = db.relationship('Object', backref='room', lazy=True, cascade='all, delete-orphan')
    devices = db.relationship('Device', backref='room', lazy=True, cascade='all, delete-orphan')
    alerts = db.relationship('Alert', backref='room', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'is_occupied': self.is_occupied,
            'last_motion_at': self.last_motion_at.isoformat() if self.last_motion_at else None,
            'empty_since': self.empty_since.isoformat() if self.empty_since else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'objects_count': len(self.objects),
            'present_objects_count': sum(1 for o in self.objects if o.is_present),
            'devices_count': len(self.devices),
            'active_devices_count': sum(1 for d in self.devices if d.power_state),
            'active_alerts_count': sum(1 for a in self.alerts if not a.is_resolved)
        }

class Object(db.Model):
    __tablename__ = 'objects'
    id = db.Column(db.Integer, primary_key=True)
    tag_id = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), default='Personal Item')
    priority = db.Column(db.String(20), default='HIGH')  # HIGH, MEDIUM, LOW
    is_checklist_item = db.Column(db.Boolean, default=True)
    checklist_checked = db.Column(db.Boolean, default=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    is_present = db.Column(db.Boolean, default=True)
    last_seen_at = db.Column(db.DateTime, default=get_utc_now)
    owner_name = db.Column(db.String(100), default='Anonymous User')
    owner_contact = db.Column(db.String(100), default='N/A')

    def to_dict(self):
        return {
            'id': self.id,
            'tag_id': self.tag_id,
            'name': self.name,
            'category': self.category,
            'priority': self.priority,
            'is_checklist_item': self.is_checklist_item,
            'checklist_checked': self.checklist_checked,
            'room_id': self.room_id,
            'room_name': self.room.name if self.room else 'Unknown',
            'is_present': self.is_present,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'owner_name': self.owner_name,
            'owner_contact': self.owner_contact
        }

class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    device_type = db.Column(db.String(60), default='Electrical')
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    power_state = db.Column(db.Boolean, default=False)
    power_watts = db.Column(db.Float, default=100.0)
    auto_shutoff_capable = db.Column(db.Boolean, default=True)
    is_critical = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'device_type': self.device_type,
            'room_id': self.room_id,
            'room_name': self.room.name if self.room else 'Unknown',
            'power_state': self.power_state,
            'power_watts': self.power_watts,
            'auto_shutoff_capable': self.auto_shutoff_capable,
            'is_critical': self.is_critical,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    alert_type = db.Column(db.String(60), nullable=False)  # FORGOTTEN_OBJECT, DEVICE_LEFT_ON, ROOM_EMPTY
    priority = db.Column(db.String(20), default='HIGH')    # HIGH, MEDIUM, LOW
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(30), default='warning')  # danger, warning, info
    related_item_name = db.Column(db.String(120), nullable=True)
    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'room_name': self.room.name if self.room else 'Unknown',
            'alert_type': self.alert_type,
            'priority': self.priority,
            'title': self.title,
            'message': self.message,
            'severity': self.severity,
            'related_item_name': self.related_item_name,
            'is_resolved': self.is_resolved,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }

class IncidentHistory(db.Model):
    __tablename__ = 'incident_history'
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), default='Personal Item')
    priority = db.Column(db.String(20), default='HIGH')
    room_name = db.Column(db.String(120), nullable=False)
    incident_type = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    resolved_at = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, default=5)

    def to_dict(self):
        return {
            'id': self.id,
            'item_name': self.item_name,
            'category': self.category,
            'priority': self.priority,
            'room_name': self.room_name,
            'incident_type': self.incident_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'duration_minutes': self.duration_minutes
        }

class TelemetryLog(db.Model):
    __tablename__ = 'telemetry_logs'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    occupancy_detected = db.Column(db.Boolean, default=False)
    tags_detected = db.Column(db.String(255), default='')
    devices_on = db.Column(db.String(255), default='')
    timestamp = db.Column(db.DateTime, default=get_utc_now)
