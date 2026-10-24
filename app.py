import os
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from models import db, User, Room, Object, Device, Alert, DeviceAuth, TelemetryLog, IncidentHistory, get_utc_now
import config

app = Flask(__name__)
app.config.from_object('config')

db.init_app(app)

# -------------------------------------------------------------------
# Core Detection & Alert Engine
# -------------------------------------------------------------------
def evaluate_room_security(room, force_trigger=False):
    now = get_utc_now()
    alerts_created = []

    if room.is_occupied:
        if room.empty_since is not None:
            room.empty_since = None
            db.session.commit()
        return alerts_created

    if room.empty_since is None:
        room.empty_since = now
        db.session.commit()

    empty_since = room.empty_since.replace(tzinfo=None) if (room.empty_since and getattr(room.empty_since, 'tzinfo', None)) else room.empty_since
    elapsed = (now - empty_since).total_seconds()
    wait_period = app.config.get('WAIT_PERIOD_SECONDS', 30)

    if elapsed >= wait_period or force_trigger:
        present_objects = Object.query.filter_by(room_id=room.id, is_present=True).all()
        for obj in present_objects:
            existing_alert = Alert.query.filter_by(
                room_id=room.id,
                alert_type='FORGOTTEN_OBJECT',
                related_item_name=obj.name,
                is_resolved=False
            ).first()

            if not existing_alert:
                severity = 'danger' if obj.priority == 'HIGH' else 'warning'
                alert = Alert(
                    room_id=room.id,
                    alert_type='FORGOTTEN_OBJECT',
                    priority=obj.priority,
                    severity=severity,
                    related_item_name=obj.name,
                    title=f"Forgotten Item ({obj.priority} Priority): {obj.name}",
                    message=(
                        f"Room '{room.name}' ({room.code}) has been vacant for {int(elapsed)}s, "
                        f"but item '{obj.name}' (Tag ID: {obj.tag_id}) was left behind! "
                        f"Owner: {obj.owner_name} ({obj.owner_contact})."
                    ),
                    created_at=now
                )
                db.session.add(alert)
                alerts_created.append(alert)

                hist = IncidentHistory(
                    item_name=obj.name,
                    category=obj.category,
                    priority=obj.priority,
                    room_name=room.name,
                    incident_type='FORGOTTEN_OBJECT',
                    created_at=now,
                    duration_minutes=int(elapsed // 60) + 1
                )
                db.session.add(hist)

        active_devices = Device.query.filter_by(room_id=room.id, power_state=True).all()
        for dev in active_devices:
            existing_alert = Alert.query.filter_by(
                room_id=room.id,
                alert_type='DEVICE_LEFT_ON',
                related_item_name=dev.name,
                is_resolved=False
            ).first()

            if not existing_alert:
                severity = 'danger' if dev.is_critical or dev.power_watts > 500 else 'warning'
                alert = Alert(
                    room_id=room.id,
                    alert_type='DEVICE_LEFT_ON',
                    priority='HIGH' if dev.is_critical else 'MEDIUM',
                    severity=severity,
                    related_item_name=dev.name,
                    title=f"Appliance Left ON: {dev.name}",
                    message=(
                        f"Room '{room.name}' ({room.code}) is vacant, but '{dev.name}' "
                        f"({dev.power_watts}W) is still running. High risk of energy waste / fire hazard."
                    ),
                    created_at=now
                )
                db.session.add(alert)
                alerts_created.append(alert)

                hist = IncidentHistory(
                    item_name=dev.name,
                    category=dev.device_type,
                    priority='HIGH' if dev.is_critical else 'MEDIUM',
                    room_name=room.name,
                    incident_type='DEVICE_LEFT_ON',
                    created_at=now,
                    duration_minutes=int(elapsed // 60) + 1
                )
                db.session.add(hist)

        db.session.commit()

    return alerts_created

# -------------------------------------------------------------------
# Helper: Authentication for IoT / Simulator
# -------------------------------------------------------------------
def verify_api_key(req):
    key = req.headers.get('X-API-Key') or (req.json.get('api_key') if req.is_json else None)
    if not key:
        return False
    configured_key = app.config.get('API_KEY', 'sample_key_123')
    if key == configured_key:
        return True
    auth = DeviceAuth.query.filter_by(api_key=key, is_active=True).first()
    return auth is not None

# -------------------------------------------------------------------
# User Authentication Routes (Admin & Student / Employee)
# -------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    success_msg = "Account created successfully! Please sign in with your credentials." if request.args.get('registered') else None

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'admin').strip()

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            session['user_id'] = user.id
            session['username'] = user.username
            session['name'] = user.name
            session['role'] = user.role
            session['email'] = user.email
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password. Please try again.')

    # If already logged in, redirect to dashboard
    if session.get('user_id'):
        return redirect(url_for('index'))

    return render_template('login.html', success=success_msg)

@app.route('/register', methods=['GET', 'POST'])
def register():
    rooms = Room.query.order_by(Room.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', 'student').strip()
        assigned_room = request.form.get('assigned_room', 'AI & Robotics Lab').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not name or not username or not email or not password:
            return render_template('register.html', rooms=rooms, error='Please fill out all required fields.')

        if password != confirm_password:
            return render_template('register.html', rooms=rooms, error='Passwords do not match. Please verify and try again.')

        if len(password) < 4:
            return render_template('register.html', rooms=rooms, error='Password must be at least 4 characters long.')

        # Check existing username
        if User.query.filter_by(username=username).first():
            return render_template('register.html', rooms=rooms, error=f"Username '{username}' is already taken. Please choose another username.")

        # Check existing email
        if User.query.filter_by(email=email).first():
            return render_template('register.html', rooms=rooms, error=f"An account with email '{email}' already exists.")

        # Create new user
        new_user = User(
            username=username,
            password=password,
            name=name,
            role=role,
            email=email,
            assigned_room=assigned_room
        )
        db.session.add(new_user)
        db.session.commit()

        # Seamless auto-login like modern apps!
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        session['name'] = new_user.name
        session['role'] = new_user.role
        session['email'] = new_user.email

        return redirect(url_for('index'))

    # If already logged in, redirect to dashboard
    if session.get('user_id'):
        return redirect(url_for('index'))

    return render_template('register.html', rooms=rooms)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/me')
def get_current_user():
    if not session.get('user_id'):
        return jsonify({'logged_in': False, 'user': None})
    return jsonify({
        'logged_in': True,
        'user': {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'name': session.get('name'),
            'role': session.get('role'),
            'email': session.get('email')
        }
    })

# -------------------------------------------------------------------
# Frontend Route
# -------------------------------------------------------------------
@app.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_info = {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'name': session.get('name', 'User'),
        'role': session.get('role', 'admin'),
        'email': session.get('email', '')
    }
    return render_template('index.html', user=user_info)

# -------------------------------------------------------------------
# API: Dashboard Summary & Departure Readiness Score
# -------------------------------------------------------------------
@app.route('/api/overview')
def get_overview():
    now = get_utc_now()
    rooms = Room.query.all()
    for r in rooms:
        evaluate_room_security(r)

    total_rooms = len(rooms)
    occupied_rooms = sum(1 for r in rooms if r.is_occupied)
    empty_rooms = total_rooms - occupied_rooms

    all_objects = Object.query.all()
    total_objects = len(all_objects)
    
    forgotten_at_risk = 0
    high_priority_forgotten = 0
    for r in rooms:
        if not r.is_occupied:
            for o in r.objects:
                if o.is_present:
                    forgotten_at_risk += 1
                    if o.priority == 'HIGH':
                        high_priority_forgotten += 1

    all_devices = Device.query.all()
    total_devices = len(all_devices)
    devices_on_empty = 0
    for r in rooms:
        if not r.is_occupied:
            devices_on_empty += sum(1 for d in r.devices if d.power_state)

    active_alerts = Alert.query.filter_by(is_resolved=False).count()

    score = 100
    score -= (high_priority_forgotten * 30)
    score -= ((forgotten_at_risk - high_priority_forgotten) * 15)
    score -= (devices_on_empty * 20)
    score = max(0, min(100, score))

    buzzer_active = (active_alerts > 0)
    led_state = 'RED_BLINKING' if active_alerts > 0 else 'GREEN_STEADY'

    return jsonify({
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'empty_rooms': empty_rooms,
        'total_objects': total_objects,
        'forgotten_at_risk': forgotten_at_risk,
        'high_priority_forgotten': high_priority_forgotten,
        'total_devices': total_devices,
        'devices_on_in_empty': devices_on_empty,
        'active_alerts': active_alerts,
        'readiness_score': score,
        'hardware_buzzer': buzzer_active,
        'hardware_led': led_state,
        'wait_period_seconds': app.config.get('WAIT_PERIOD_SECONDS', 30),
        'server_time': now.isoformat()
    })

# -------------------------------------------------------------------
# API: Smart Exit Checklist
# -------------------------------------------------------------------
@app.route('/api/checklist', methods=['GET'])
def get_checklist():
    items = Object.query.filter_by(is_checklist_item=True).order_by(Object.priority.desc(), Object.id).all()
    return jsonify([o.to_dict() for o in items])

@app.route('/api/checklist/<int:item_id>/toggle', methods=['POST'])
def toggle_checklist(item_id):
    item = Object.query.get_or_404(item_id)
    item.checklist_checked = not item.checklist_checked
    db.session.commit()
    return jsonify({
        'status': 'success',
        'item': item.to_dict(),
        'message': f"Checklist item '{item.name}' marked {'Completed' if item.checklist_checked else 'Pending'}"
    })

@app.route('/api/checklist/reset', methods=['POST'])
def reset_checklist():
    Object.query.update({'checklist_checked': False})
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Exit checklist reset for all users.'})

# -------------------------------------------------------------------
# API: Forgotten Object History & Analytics
# -------------------------------------------------------------------
@app.route('/api/history', methods=['GET'])
def get_history():
    history_records = IncidentHistory.query.order_by(IncidentHistory.created_at.desc()).limit(50).all()
    
    category_counts = {}
    for h in history_records:
        cat = h.category or 'General'
        category_counts[cat] = category_counts.get(cat, 0) + 1

    total_incidents = IncidentHistory.query.count()

    return jsonify({
        'total_incidents': total_incidents,
        'category_stats': category_counts,
        'records': [h.to_dict() for h in history_records]
    })

# -------------------------------------------------------------------
# API: Rooms Management
# -------------------------------------------------------------------
@app.route('/api/rooms', methods=['GET', 'POST'])
def handle_rooms():
    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        code = data.get('code', '').strip()
        if not name or not code:
            return jsonify({'error': 'Room name and code are required'}), 400

        room = Room(name=name, code=code, is_occupied=True)
        db.session.add(room)
        db.session.commit()
        return jsonify(room.to_dict()), 201

    rooms = Room.query.order_by(Room.id).all()
    result = []
    for r in rooms:
        data = r.to_dict()
        data['objects'] = [o.to_dict() for o in r.objects]
        data['devices'] = [d.to_dict() for d in r.devices]
        data['unresolved_alerts'] = [a.to_dict() for a in r.alerts if not a.is_resolved]
        result.append(data)
    return jsonify(result)

@app.route('/api/rooms/<int:room_id>/toggle-occupancy', methods=['POST'])
def toggle_room_occupancy(room_id):
    room = Room.query.get_or_404(room_id)
    room.is_occupied = not room.is_occupied
    now = get_utc_now()
    if room.is_occupied:
        room.last_motion_at = now
        room.empty_since = None
    else:
        room.empty_since = now
    db.session.commit()

    evaluate_room_security(room)
    return jsonify({
        'room': room.to_dict(),
        'message': f"Room '{room.name}' occupancy set to {'Occupied' if room.is_occupied else 'Vacant (Empty)'}"
    })

# -------------------------------------------------------------------
# API: Objects Management
# -------------------------------------------------------------------
@app.route('/api/objects', methods=['GET', 'POST'])
def handle_objects():
    if request.method == 'POST':
        data = request.get_json() or {}
        tag_id = data.get('tag_id', '').strip()
        name = data.get('name', '').strip()
        room_id = data.get('room_id')
        category = data.get('category', 'Personal Item')
        priority = data.get('priority', 'HIGH').upper()
        owner_name = data.get('owner_name', 'Student')
        owner_contact = data.get('owner_contact', 'student@campus.edu')

        if not tag_id or not name or not room_id:
            return jsonify({'error': 'tag_id, name, and room_id are required'}), 400

        obj = Object(
            tag_id=tag_id,
            name=name,
            room_id=room_id,
            category=category,
            priority=priority,
            owner_name=owner_name,
            owner_contact=owner_contact,
            is_present=True
        )
        db.session.add(obj)
        db.session.commit()
        return jsonify(obj.to_dict()), 201

    objects = Object.query.order_by(Object.id).all()
    return jsonify([o.to_dict() for o in objects])

@app.route('/api/objects/<int:obj_id>/toggle-presence', methods=['POST'])
def toggle_object_presence(obj_id):
    obj = Object.query.get_or_404(obj_id)
    obj.is_present = not obj.is_present
    obj.last_seen_at = get_utc_now()
    db.session.commit()

    evaluate_room_security(obj.room)
    return jsonify({
        'object': obj.to_dict(),
        'message': f"Item '{obj.name}' is now marked as {'Present' if obj.is_present else 'Removed'}"
    })

# -------------------------------------------------------------------
# API: Devices Management & Remote Cutoff
# -------------------------------------------------------------------
@app.route('/api/devices', methods=['GET', 'POST'])
def handle_devices():
    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        device_type = data.get('device_type', 'Electrical')
        room_id = data.get('room_id')
        power_watts = float(data.get('power_watts', 100.0))
        is_critical = bool(data.get('is_critical', False))

        if not name or not room_id:
            return jsonify({'error': 'name and room_id are required'}), 400

        dev = Device(
            name=name,
            device_type=device_type,
            room_id=room_id,
            power_watts=power_watts,
            is_critical=is_critical,
            power_state=True
        )
        db.session.add(dev)
        db.session.commit()
        return jsonify(dev.to_dict()), 201

    devices = Device.query.order_by(Device.id).all()
    return jsonify([d.to_dict() for d in devices])

@app.route('/api/devices/<int:dev_id>/toggle-power', methods=['POST'])
def toggle_device_power(dev_id):
    dev = Device.query.get_or_404(dev_id)
    dev.power_state = not dev.power_state
    dev.updated_at = get_utc_now()
    db.session.commit()

    evaluate_room_security(dev.room)
    return jsonify({
        'device': dev.to_dict(),
        'message': f"Device '{dev.name}' turned {'ON' if dev.power_state else 'OFF'}"
    })

# -------------------------------------------------------------------
# API: Alerts Management
# -------------------------------------------------------------------
@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    rooms = Room.query.all()
    for r in rooms:
        evaluate_room_security(r)

    unresolved_only = request.args.get('unresolved', 'false').lower() == 'true'
    query = Alert.query
    if unresolved_only:
        query = query.filter_by(is_resolved=False)
    alerts = query.order_by(Alert.created_at.desc()).all()
    return jsonify([a.to_dict() for a in alerts])

@app.route('/api/alerts/<int:alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.is_resolved = True
    alert.resolved_at = get_utc_now()
    db.session.commit()
    return jsonify({'alert': alert.to_dict(), 'message': 'Alert resolved successfully'})

@app.route('/api/alerts/resolve-all', methods=['POST'])
def resolve_all_alerts():
    Alert.query.filter_by(is_resolved=False).update({
        'is_resolved': True,
        'resolved_at': get_utc_now()
    })
    db.session.commit()
    return jsonify({'message': 'All alerts resolved'})

# -------------------------------------------------------------------
# API: IoT Hardware / Sensor Ingestion Endpoint
# -------------------------------------------------------------------
@app.route('/api/sensor-data', methods=['POST'])
def ingest_sensor_data():
    if not verify_api_key(request):
        return jsonify({'error': 'Unauthorized: Invalid or missing API key'}), 401

    data = request.get_json() or {}
    room_code = data.get('room_code')
    if not room_code:
        return jsonify({'error': 'room_code is required'}), 400

    room = Room.query.filter_by(code=room_code).first()
    if not room:
        return jsonify({'error': f"Room with code '{room_code}' not found"}), 404

    now = get_utc_now()

    if 'is_occupied' in data:
        was_occupied = room.is_occupied
        room.is_occupied = bool(data['is_occupied'])
        if room.is_occupied:
            room.last_motion_at = now
            room.empty_since = None
        else:
            if was_occupied or room.empty_since is None:
                room.empty_since = now

    rfid_tags = data.get('rfid_tags')
    if isinstance(rfid_tags, list):
        for obj in room.objects:
            obj.is_present = (obj.tag_id in rfid_tags)
            if obj.is_present:
                obj.last_seen_at = now

    device_states = data.get('device_states')
    if isinstance(device_states, dict):
        for dev in room.devices:
            if dev.name in device_states:
                dev.power_state = bool(device_states[dev.name])

    log = TelemetryLog(
        room_id=room.id,
        occupancy_detected=room.is_occupied,
        tags_detected=",".join(rfid_tags) if isinstance(rfid_tags, list) else '',
        devices_on=",".join([d.name for d in room.devices if d.power_state]),
        timestamp=now
    )
    db.session.add(log)
    db.session.commit()

    alerts = evaluate_room_security(room)

    return jsonify({
        'status': 'success',
        'room': room.to_dict(),
        'new_alerts_triggered': len(alerts)
    })

# -------------------------------------------------------------------
# Simulation Triggers for Instant Testing & Demo
# -------------------------------------------------------------------
@app.route('/api/simulate/last-person-out', methods=['POST'])
def trigger_last_person_out_simulation():
    room = Room.query.first()
    if not room:
        return jsonify({'error': 'No rooms available'}), 400

    now = get_utc_now()
    room.is_occupied = False
    room.empty_since = now - timedelta(seconds=app.config.get('WAIT_PERIOD_SECONDS', 30) + 5)

    if room.objects:
        room.objects[0].is_present = True
    if room.devices:
        room.devices[0].power_state = True

    db.session.commit()
    alerts = evaluate_room_security(room, force_trigger=True)

    return jsonify({
        'status': 'triggered',
        'room': room.name,
        'message': f"Simulated Last-Person-Out in '{room.name}'. Empty wait time exceeded. {len(alerts)} alerts generated!",
        'alerts': [a.to_dict() for a in alerts]
    })

@app.route('/api/simulate/reset-demo', methods=['POST'])
def reset_demo_data():
    init_db(force_reseed=True)
    return jsonify({'status': 'success', 'message': 'Demo database reseeded with realistic classrooms, objects, priority levels & incident history.'})

# -------------------------------------------------------------------
# Database Initialization & Seeding
# -------------------------------------------------------------------
def init_db(force_reseed=False):
    with app.app_context():
        if force_reseed:
            db.drop_all()
        db.create_all()

        # Seed Users (Admin, Student, Faculty)
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(
                username='admin',
                password='admin123',
                name='Chief Administrator',
                role='admin',
                email='admin@forgetguard.internal',
                assigned_room='Campus Control Hub'
            ))

        if not User.query.filter_by(username='student').first():
            db.session.add(User(
                username='student',
                password='student123',
                name='Alex Rivera (Research Student)',
                role='student',
                email='alex.rivera@univ.edu',
                assigned_room='AI & Robotics Lab'
            ))

        if not User.query.filter_by(username='faculty').first():
            db.session.add(User(
                username='faculty',
                password='faculty123',
                name='Dr. Sarah Chen (Faculty / Employee)',
                role='student',
                email='s.chen@univ.edu',
                assigned_room='Embedded Systems Lab'
            ))

        # Seed Shared Hardware Gateway Key
        if not DeviceAuth.query.filter_by(api_key='sample_key_123').first():
            db.session.add(DeviceAuth(
                api_key='sample_key_123',
                device_name='ESP32 Gateway Gateway-Hub-1',
                is_active=True
            ))

        if Room.query.count() == 0:
            now = get_utc_now()

            r1 = Room(
                name='AI & Robotics Lab',
                code='LAB-101',
                is_occupied=False,
                last_motion_at=now - timedelta(minutes=20),
                empty_since=now - timedelta(seconds=45)
            )

            r2 = Room(
                name='Embedded Systems Lab',
                code='LAB-204',
                is_occupied=True,
                last_motion_at=now - timedelta(seconds=12),
                empty_since=None
            )

            r3 = Room(
                name='Lecture Hall Alpha',
                code='LH-301',
                is_occupied=False,
                last_motion_at=now - timedelta(hours=1),
                empty_since=now - timedelta(minutes=50)
            )

            db.session.add_all([r1, r2, r3])
            db.session.flush()

            o1 = Object(
                tag_id='RFID-BAG-992',
                name='Timbuk2 Laptop Messenger Bag',
                category='Bags',
                priority='HIGH',
                is_checklist_item=True,
                checklist_checked=False,
                room_id=r1.id,
                is_present=True,
                owner_name='Alex Rivera (PhD Candidate)',
                owner_contact='alex.rivera@univ.edu'
            )
            o2 = Object(
                tag_id='BLE-KEY-404',
                name='Toyota Car Key Fob & House Keys',
                category='Keys',
                priority='HIGH',
                is_checklist_item=True,
                checklist_checked=False,
                room_id=r1.id,
                is_present=True,
                owner_name='Dr. Sarah Chen',
                owner_contact='+1-555-019-2834'
            )
            o3 = Object(
                tag_id='RFID-WLT-551',
                name='Leather Wallet & University ID Card',
                category='Wallets & IDs',
                priority='HIGH',
                is_checklist_item=True,
                checklist_checked=True,
                room_id=r1.id,
                is_present=False,
                owner_name='Alex Rivera',
                owner_contact='alex.rivera@univ.edu'
            )
            o4 = Object(
                tag_id='RFID-CHG-102',
                name='Apple 96W USB-C Fast Charger',
                category='Electronics & Chargers',
                priority='MEDIUM',
                is_checklist_item=True,
                checklist_checked=False,
                room_id=r2.id,
                is_present=True,
                owner_name='Marcus Brody',
                owner_contact='m.brody@univ.edu'
            )
            o5 = Object(
                tag_id='BLE-NBK-330',
                name='Spiral Research Lab Notebook',
                category='Documents',
                priority='LOW',
                is_checklist_item=False,
                checklist_checked=False,
                room_id=r2.id,
                is_present=True,
                owner_name='Elena Rostova',
                owner_contact='e.rostova@univ.edu'
            )

            d1 = Device(
                name='Ceiling 4K Laser Projector',
                device_type='Projector',
                room_id=r1.id,
                power_state=True,
                power_watts=350.0,
                is_critical=True
            )
            d2 = Device(
                name='Daikin Inverter AC 2.0 Ton',
                device_type='Air Conditioner',
                room_id=r1.id,
                power_state=True,
                power_watts=1850.0,
                is_critical=True
            )
            d3 = Device(
                name='Fluorescent Ceiling Array',
                device_type='Lighting',
                room_id=r1.id,
                power_state=False,
                power_watts=220.0
            )
            d4 = Device(
                name='Benchtop DC Power Supply #4',
                device_type='Lab Instrument',
                room_id=r2.id,
                power_state=True,
                power_watts=450.0,
                is_critical=True
            )
            d5 = Device(
                name='Soldering Extraction Fan',
                device_type='Ventilation',
                room_id=r2.id,
                power_state=True,
                power_watts=120.0
            )
            d6 = Device(
                name='Auditorium Sound System Amplifier',
                device_type='Audio System',
                room_id=r3.id,
                power_state=False,
                power_watts=600.0
            )

            h1 = IncidentHistory(
                item_name='Toyota Car Key Fob',
                category='Keys',
                priority='HIGH',
                room_name='AI & Robotics Lab',
                incident_type='FORGOTTEN_OBJECT',
                created_at=now - timedelta(days=1, hours=3),
                resolved_at=now - timedelta(days=1, hours=2),
                duration_minutes=42
            )
            h2 = IncidentHistory(
                item_name='Ceiling 4K Laser Projector',
                category='Projector',
                priority='HIGH',
                room_name='AI & Robotics Lab',
                incident_type='DEVICE_LEFT_ON',
                created_at=now - timedelta(days=2),
                resolved_at=now - timedelta(days=2, minutes=-15),
                duration_minutes=15
            )
            h3 = IncidentHistory(
                item_name='Student ID Card & Wallet',
                category='Wallets & IDs',
                priority='HIGH',
                room_name='Lecture Hall Alpha',
                incident_type='FORGOTTEN_OBJECT',
                created_at=now - timedelta(days=3),
                resolved_at=now - timedelta(days=3, minutes=-25),
                duration_minutes=25
            )

            db.session.add_all([o1, o2, o3, o4, o5, d1, d2, d3, d4, d5, d6, h1, h2, h3])
            db.session.commit()

            evaluate_room_security(r1, force_trigger=True)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='127.0.0.1', port=5000)
