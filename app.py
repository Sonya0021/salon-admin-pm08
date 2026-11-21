import os
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-salon-pm08')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///salon_admin.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Для доступа к админ-панели выполните вход.'

# --- МОДЕЛИ БАЗЫ ДАННЫХ ---
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)  # admin, manager, viewer
    name = db.Column(db.String(50), nullable=False)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    role = db.relationship('Role')

class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    duration_min = db.Column(db.Integer, nullable=False)

class Stylist(db.Model):
    __tablename__ = 'stylists'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    specialization = db.Column(db.String(120), nullable=False)
    experience_years = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    stylist_id = db.Column(db.Integer, db.ForeignKey('stylists.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    visit_date = db.Column(db.DateTime, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(30), default='Новая')
    client = db.relationship('Client')
    stylist = db.relationship('Stylist')
    service = db.relationship('Service')

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    entity = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    user = db.relationship('User')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def log_action(action, entity, entity_id, details):
    if current_user.is_authenticated:
        entry = ActivityLog(user_id=current_user.id, action=action, entity=entity, entity_id=entity_id, details=details)
        db.session.add(entry)
        db.session.commit()

def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role.code not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return decorated
    return wrapper

# --- ОБЩИЙ HTML ШАБЛОН (LAYOUT С SIDEBAR И HEADER) ---
BASE_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} — Админ-панель «Стиль»</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f3f4f6; color: #1f2937; display: flex; min-height: 100vh; }
        .sidebar { width: 250px; background: #2d1e20; color: #fff; display: flex; flex-direction: column; flex-shrink: 0; }
        .sidebar .brand { padding: 20px; font-size: 18px; font-weight: bold; background: #211517; border-bottom: 1px solid #463134; }
        .sidebar a { color: #e5e7eb; text-decoration: none; padding: 12px 20px; display: block; font-size: 14px; border-left: 4px solid transparent; }
        .sidebar a:hover, .sidebar a.active { background: #463134; color: #fff; border-left-color: #eab308; }
        .main { flex: 1; display: flex; flex-direction: column; overflow-x: auto; }
        header { background: #fff; padding: 15px 25px; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center; }
        .role-badge { background: #fef3c7; color: #92400e; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-left: 8px; }
        .content { padding: 25px; max-width: 1200px; width: 100%; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: #fff; padding: 18px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border-top: 4px solid #3d2c2e; }
        .card h4 { margin: 0 0 8px 0; color: #6b7280; font-size: 13px; text-transform: uppercase; }
        .card .val { font-size: 24px; font-weight: bold; color: #111827; }
        .panel { background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; }
        .toolbar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .filters { display: flex; flex-wrap: wrap; gap: 8px; }
        input, select { padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; }
        .btn { padding: 8px 14px; border-radius: 6px; border: none; cursor: pointer; font-size: 13px; text-decoration: none; display: inline-block; font-weight: 600; }
        .btn-primary { background: #3d2c2e; color: #fff; }
        .btn-primary:hover { background: #594043; }
        .btn-warn { background: #d97706; color: #fff; }
        .btn-danger { background: #dc2626; color: #fff; }
        .btn-outline { background: #fff; border: 1px solid #d1d5db; color: #374151; }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th, td { padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }
        th { background: #f9fafb; font-weight: 600; color: #374151; }
        .alert { padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
        .alert-err { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
        .pagination { display: flex; gap: 6px; margin-top: 15px; }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; max-width: 700px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: 600; font-size: 13px; }
        .form-group input, .form-group select { width: 100%; }
        @media (max-width: 768px) {
            body { flex-direction: column; }
            .sidebar { width: 100%; }
            .form-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <aside class="sidebar">
        <div class="brand">✂ Салон «Стиль» Admin</div>
        <a href="/admin/dashboard" class="{{ 'active' if active=='dashboard' else '' }}">📊 Dashboard</a>
        <a href="/admin/appointments" class="{{ 'active' if active=='appointments' else '' }}">📅 Записи на услуги</a>
        <a href="/admin/services" class="{{ 'active' if active=='services' else '' }}">💇 Услуги стилистов</a>
        <a href="/admin/stylists" class="{{ 'active' if active=='stylists' else '' }}">👩‍🎨 Стилисты салона</a>
        <a href="/admin/clients" class="{{ 'active' if active=='clients' else '' }}">👥 Клиенты салона</a>
        {% if current_user.role.code == 'admin' %}
        <a href="/admin/users" class="{{ 'active' if active=='users' else '' }}">🔐 Пользователи и роли</a>
        {% endif %}
        {% if current_user.role.code in ['admin', 'manager'] %}
        <a href="/admin/activity-log" class="{{ 'active' if active=='log' else '' }}">📜 Журнал действий</a>
        {% endif %}
    </aside>
    <div class="main">
        <header>
            <div><strong>{{ title }}</strong></div>
            <div>
                {{ current_user.full_name }}
                <span class="role-badge">{{ current_user.role.code }}</span>
                <a href="/logout" class="btn btn-outline" style="margin-left:10px;">Выйти</a>
            </div>
        </header>
        <div class="content">
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% for cat, msg in messages %}
                <div class="alert {{ 'alert-err' if cat=='error' else '' }}">{{ msg }}</div>
              {% endfor %}
            {% endwith %}
            {{ body | safe }}
        </div>
    </div>
</body>
</html>
"""

def render_page(title, active, body_tpl, **ctx):
    rendered_body = render_template_string(body_tpl, **ctx)
    return render_template_string(BASE_HTML, title=title, active=active, body=rendered_body)

# --- АВТОРИЗАЦИЯ ---
@app.route('/')
def index():
    return redirect('/admin/dashboard' if current_user.is_authenticated else '/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            error = 'Неверный email или пароль'
        elif not user.is_active:
            error = 'Учетная запись заблокирована администратором'
        else:
            login_user(user)
            log_action('LOGIN', 'Auth', user.id, f'Успешный вход пользователя {user.email}')
            return redirect('/admin/dashboard')
    return render_template_string("""
    <!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Вход — Админ-панель</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #2d1e20; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { background: #fff; padding: 30px; border-radius: 10px; width: 380px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
        h2 { margin-top: 0; color: #2d1e20; }
        label { display: block; margin-top: 12px; font-weight: 600; font-size: 14px; }
        input { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
        button { width: 100%; margin-top: 18px; padding: 11px; background: #3d2c2e; color: #fff; border: none; border-radius: 6px; font-size: 15px; cursor: pointer; }
        .err { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 6px; margin-bottom: 10px; font-size: 13px; }
        .hint { margin-top: 15px; font-size: 12px; color: #666; background: #f9fafb; padding: 10px; border-radius: 6px; }
    </style></head><body>
    <div class="box">
        <h2>✂ Вход в админ-панель</h2>
        {% if error %}<div class="err">{{ error }}</div>{% endif %}
        <form method="post">
            <label>Email</label><input type="email" name="email" required placeholder="admin@salon.local">
            <label>Пароль</label><input type="password" name="password" required placeholder="••••••••">
            <button type="submit">Войти</button>
        </form>
        <div class="hint">
            <b>Тестовые аккаунты:</b><br>
            admin@salon.local / Admin123!<br>
            manager@salon.local / Manager123!<br>
            viewer@salon.local / Viewer123!
        </div>
    </div></body></html>
    """, error=error)

@app.route('/logout')
@login_required
def logout():
    log_action('LOGOUT', 'Auth', current_user.id, f'Выход пользователя {current_user.email}')
    logout_user()
    return redirect('/login')

# --- DASHBOARD ---
@app.route('/admin/dashboard')
@login_required
def dashboard():
    total_apps = Appointment.query.count()
    new_apps = Appointment.query.filter_by(status='Новая').count()
    total_sum = db.session.query(func.coalesce(func.sum(Service.price), 0)).join(Appointment).scalar()
    stylists_count = Stylist.query.filter_by(is_active=True).count()
    recent_logs = ActivityLog.query.order_by(ActivityLog.id.desc()).limit(6).all()

    body = """
    <div class="cards">
        <div class="card"><h4>Всего записей</h4><div class="val">{{ total_apps }}</div></div>
        <div class="card" style="border-top-color:#d97706;"><h4>Новые заявки</h4><div class="val">{{ new_apps }}</div></div>
        <div class="card" style="border-top-color:#059669;"><h4>Сумма по чекам (SUM)</h4><div class="val">{{ "%.2f"|format(total_sum) }} ₽</div></div>
        <div class="card" style="border-top-color:#2563eb;"><h4>Активных стилистов</h4><div class="val">{{ stylists_count }}</div></div>
    </div>
    {% if current_user.role.code in ['admin', 'manager'] %}
    <div class="panel">
        <h3 style="margin-top:0;">Быстрые действия</h3>
        <a href="/admin/appointments/create" class="btn btn-primary">+ Новая запись клиента</a>
        <a href="/admin/services/create" class="btn btn-outline">+ Добавить услугу</a>
        <a href="/admin/clients/create" class="btn btn-outline">+ Новый клиент</a>
    </div>
    {% endif %}
    <div class="panel">
        <h3 style="margin-top:0;">Последние действия в системе</h3>
        <table>
            <thead><tr><th>Время</th><th>Пользователь</th><th>Действие</th><th>Сущность</th><th>Описание</th></tr></thead>
            <tbody>
            {% for l in recent_logs %}
                <tr><td>{{ l.created_at.strftime('%d.%m.%Y %H:%M') }}</td><td>{{ l.user.full_name }}</td><td><b>{{ l.action }}</b></td><td>{{ l.entity }}</td><td>{{ l.details }}</td></tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    """
    return render_page('Dashboard', 'dashboard', body, total_apps=total_apps, new_apps=new_apps,
                       total_sum=total_sum, stylists_count=stylists_count, recent_logs=recent_logs)

# --- CRUD 1: ЗАПИСИ НА УСЛУГИ (С ПОИСКОМ, ФИЛЬТРОМ, СОРТИРОВКОЙ И ПАГИНАЦИЕЙ) ---
@app.route('/admin/appointments')
@login_required
def list_appointments():
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '')
    sort = request.args.get('sort', 'desc')
    page = request.args.get('page', 1, type=int)

    query = Appointment.query.join(Client).join(Service).join(Stylist)
    if q:
        query = query.filter(Client.full_name.ilike(f'%{q}%') | Service.name.ilike(f'%{q}%'))
    if status_filter:
        query = query.filter(Appointment.status == status_filter)
    query = query.order_by(Appointment.visit_date.asc() if sort == 'asc' else Appointment.visit_date.desc())
    pagination = query.paginate(page=page, per_page=6, error_out=False)

    body = """
    <div class="panel">
        <div class="toolbar">
            <form class="filters" method="get">
                <input type="text" name="q" value="{{ q }}" placeholder="Поиск по клиенту или услуге...">
                <select name="status">
                    <option value="">Все статусы</option>
                    {% for st in ['Новая', 'Подтверждена', 'Выполнена', 'Отменена'] %}
                    <option value="{{ st }}" {{ 'selected' if status_filter==st else '' }}>{{ st }}</option>
                    {% endfor %}
                </select>
                <select name="sort">
                    <option value="desc" {{ 'selected' if sort=='desc' else '' }}>Сначала новые даты</option>
                    <option value="asc" {{ 'selected' if sort=='asc' else '' }}>Сначала старые даты</option>
                </select>
                <button type="submit" class="btn btn-outline">Найти</button>
            </form>
            {% if current_user.role.code in ['admin', 'manager'] %}
            <a href="/admin/appointments/create" class="btn btn-primary">+ Создать запись</a>
            {% endif %}
        </div>
        <table>
            <thead><tr><th>ID</th><th>Клиент</th><th>Стилист</th><th>Услуга</th><th>Цена</th><th>Дата визита</th><th>Статус</th><th>Действия</th></tr></thead>
            <tbody>
            {% for a in pagination.items %}
                <tr>
                    <td>{{ a.id }}</td><td>{{ a.client.full_name }}</td><td>{{ a.stylist.full_name }}</td>
                    <td>{{ a.service.name }}</td><td>{{ "%.2f"|format(a.service.price) }} ₽</td>
                    <td>{{ a.visit_date.strftime('%d.%m.%Y %H:%M') }}</td><td><b>{{ a.status }}</b></td>
                    <td>
                        {% if current_user.role.code in ['admin', 'manager'] %}
                        <a href="/admin/appointments/{{ a.id }}/edit" class="btn btn-warn">Изм.</a>
                        <form method="post" action="/admin/appointments/{{ a.id }}/delete" style="display:inline;" onsubmit="return confirm('Удалить запись #{{ a.id }}?');">
                            <button class="btn btn-danger">Удал.</button>
                        </form>
                        {% else %}Только просмотр{% endif %}
                    </td>
                </tr>
            {% else %}
                <tr><td colspan="8" style="text-align:center;color:#666;">Записи не найдены</td></tr>
            {% endfor %}
            </tbody>
        </table>
        <div class="pagination">
            {% for p in pagination.iter_pages() %}
              {% if p %}
                <a href="?page={{ p }}&q={{ q }}&status={{ status_filter }}&sort={{ sort }}" class="btn {{ 'btn-primary' if p==pagination.page else 'btn-outline' }}">{{ p }}</a>
              {% endif %}
            {% endfor %}
        </div>
    </div>
    """
    return render_page('Записи на услуги', 'appointments', body, pagination=pagination, q=q, status_filter=status_filter, sort=sort)

@app.route('/admin/appointments/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def create_appointment():
    if request.method == 'POST':
        item = Appointment(
            client_id=int(request.form['client_id']),
            stylist_id=int(request.form['stylist_id']),
            service_id=int(request.form['service_id']),
            visit_date=datetime.strptime(request.form['visit_date'], '%Y-%m-%dT%H:%M'),
            payment_method=request.form['payment_method'],
            status=request.form['status']
        )
        db.session.add(item)
        db.session.commit()
        log_action('CREATE', 'Appointment', item.id, f'Создана запись #{item.id} для клиента ID={item.client_id}')
        flash('Запись успешно создана!')
        return redirect('/admin/appointments')
    body = """
    <div class="panel">
        <form method="post" class="form-grid">
            <div class="form-group"><label>Клиент *</label><select name="client_id">{% for c in clients %}<option value="{{ c.id }}">{{ c.full_name }}</option>{% endfor %}</select></div>
            <div class="form-group"><label>Стилист *</label><select name="stylist_id">{% for s in stylists %}<option value="{{ s.id }}">{{ s.full_name }}</option>{% endfor %}</select></div>
            <div class="form-group"><label>Услуга *</label><select name="service_id">{% for srv in services %}<option value="{{ srv.id }}">{{ srv.name }} ({{ srv.price }} ₽)</option>{% endfor %}</select></div>
            <div class="form-group"><label>Дата и время *</label><input type="datetime-local" name="visit_date" required></div>
            <div class="form-group"><label>Оплата</label><select name="payment_method"><option>Банковская карта / СБП</option><option>Наличные в салоне</option></select></div>
            <div class="form-group"><label>Статус</label><select name="status"><option>Новая</option><option>Подтверждена</option><option>Выполнена</option><option>Отменена</option></select></div>
            <div style="grid-column:span 2;"><button class="btn btn-primary">Сохранить</button> <a href="/admin/appointments" class="btn btn-outline">Отмена</a></div>
        </form>
    </div>
    """
    return render_page('Новая запись', 'appointments', body, clients=Client.query.all(), stylists=Stylist.query.all(), services=Service.query.all())

@app.route('/admin/appointments/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def edit_appointment(id):
    item = db.get_or_404(Appointment, id)
    if request.method == 'POST':
        item.client_id = int(request.form['client_id'])
        item.stylist_id = int(request.form['stylist_id'])
        item.service_id = int(request.form['service_id'])
        item.visit_date = datetime.strptime(request.form['visit_date'], '%Y-%m-%dT%H:%M')
        item.payment_method = request.form['payment_method']
        item.status = request.form['status']
        db.session.commit()
        log_action('UPDATE', 'Appointment', item.id, f'Обновлена запись #{item.id}, статус: {item.status}')
        flash('Изменения сохранены!')
        return redirect('/admin/appointments')
    body = """
    <div class="panel">
        <form method="post" class="form-grid">
            <div class="form-group"><label>Клиент</label><select name="client_id">{% for c in clients %}<option value="{{ c.id }}" {{ 'selected' if c.id==item.client_id else '' }}>{{ c.full_name }}</option>{% endfor %}</select></div>
            <div class="form-group"><label>Стилист</label><select name="stylist_id">{% for s in stylists %}<option value="{{ s.id }}" {{ 'selected' if s.id==item.stylist_id else '' }}>{{ s.full_name }}</option>{% endfor %}</select></div>
            <div class="form-group"><label>Услуга</label><select name="service_id">{% for srv in services %}<option value="{{ srv.id }}" {{ 'selected' if srv.id==item.service_id else '' }}>{{ srv.name }}</option>{% endfor %}</select></div>
            <div class="form-group"><label>Дата и время</label><input type="datetime-local" name="visit_date" value="{{ item.visit_date.strftime('%Y-%m-%dT%H:%M') }}" required></div>
            <div class="form-group"><label>Оплата</label><select name="payment_method"><option {{ 'selected' if item.payment_method=='Банковская карта / СБП' else '' }}>Банковская карта / СБП</option><option {{ 'selected' if item.payment_method=='Наличные в салоне' else '' }}>Наличные в салоне</option></select></div>
            <div class="form-group"><label>Статус</label><select name="status">{% for st in ['Новая', 'Подтверждена', 'Выполнена', 'Отменена'] %}<option {{ 'selected' if item.status==st else '' }}>{{ st }}</option>{% endfor %}</select></div>
            <div style="grid-column:span 2;"><button class="btn btn-primary">Сохранить</button> <a href="/admin/appointments" class="btn btn-outline">Отмена</a></div>
        </form>
    </div>
    """
    return render_page(f'Редактирование записи #{id}', 'appointments', body, item=item, clients=Client.query.all(), stylists=Stylist.query.all(), services=Service.query.all())

@app.route('/admin/appointments/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def delete_appointment(id):
    item = db.get_or_404(Appointment, id)
    db.session.delete(item)
    db.session.commit()
    log_action('DELETE', 'Appointment', id, f'Удалена запись #{id}')
    flash(f'Запись #{id} удалена.')
    return redirect('/admin/appointments')

# --- CRUD 2: УСЛУГИ СТИЛИСТОВ ---
@app.route('/admin/services')
@login_required
def list_services():
    q = request.args.get('q', '').strip()
    query = Service.query
    if q:
        query = query.filter(Service.name.ilike(f'%{q}%') | Service.category.ilike(f'%{q}%'))
    body = """
    <div class="panel">
        <div class="toolbar">
            <form class="filters"><input type="text" name="q" value="{{ q }}" placeholder="Поиск услуги..."><button class="btn btn-outline">Найти</button></form>
            {% if current_user.role.code in ['admin', 'manager'] %}<a href="/admin/services/create" class="btn btn-primary">+ Добавить услугу</a>{% endif %}
        </div>
        <table>
            <thead><tr><th>ID</th><th>Название услуги</th><th>Категория</th><th>Цена</th><th>Длительность</th><th>Действия</th></tr></thead>
            <tbody>
            {% for s in items %}
                <tr><td>{{ s.id }}</td><td>{{ s.name }}</td><td>{{ s.category }}</td><td>{{ "%.2f"|format(s.price) }} ₽</td><td>{{ s.duration_min }} мин.</td>
                <td>{% if current_user.role.code in ['admin', 'manager'] %}
                    <a href="/admin/services/{{ s.id }}/edit" class="btn btn-warn">Изм.</a>
                    <form method="post" action="/admin/services/{{ s.id }}/delete" style="display:inline;" onsubmit="return confirm('Удалить услугу?');"><button class="btn btn-danger">Удал.</button></form>
                {% else %}Просмотр{% endif %}</td></tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    """
    return render_page('Услуги стилистов', 'services', body, items=query.all(), q=q)

@app.route('/admin/services/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def create_service():
    if request.method == 'POST':
        price = float(request.form['price'])
        if price < 0 or len(request.form['name'].strip()) < 3:
            flash('Ошибка валидации: название от 3 символов, цена >= 0', 'error')
            return redirect('/admin/services/create')
        s = Service(name=request.form['name'].strip(), category=request.form['category'], price=price, duration_min=int(request.form['duration_min']))
        db.session.add(s)
        db.session.commit()
        log_action('CREATE', 'Service', s.id, f'Создана услуга "{s.name}"')
        flash('Услуга добавлена!')
        return redirect('/admin/services')
    body = """<div class="panel"><form method="post" class="form-grid">
        <div class="form-group"><label>Название *</label><input name="name" required minlength="3"></div>
        <div class="form-group"><label>Категория *</label><select name="category"><option>Стрижки</option><option>Окрашивание</option><option>Укладки</option><option>Уход</option></select></div>
        <div class="form-group"><label>Цена (₽) *</label><input type="number" step="0.01" min="0" name="price" required></div>
        <div class="form-group"><label>Длительность (мин) *</label><input type="number" min="10" name="duration_min" value="60" required></div>
        <div style="grid-column:span 2;"><button class="btn btn-primary">Сохранить</button> <a href="/admin/services" class="btn btn-outline">Отмена</a></div>
    </form></div>"""
    return render_page('Новая услуга', 'services', body)

@app.route('/admin/services/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def edit_service(id):
    s = db.get_or_404(Service, id)
    if request.method == 'POST':
        s.name = request.form['name'].strip()
        s.category = request.form['category']
        s.price = float(request.form['price'])
        s.duration_min = int(request.form['duration_min'])
        db.session.commit()
        log_action('UPDATE', 'Service', s.id, f'Изменена услуга "{s.name}" ({s.price} ₽)')
        flash('Услуга обновлена!')
        return redirect('/admin/services')
    body = """<div class="panel"><form method="post" class="form-grid">
        <div class="form-group"><label>Название</label><input name="name" value="{{ s.name }}" required></div>
        <div class="form-group"><label>Категория</label><input name="category" value="{{ s.category }}" required></div>
        <div class="form-group"><label>Цена (₽)</label><input type="number" step="0.01" min="0" name="price" value="{{ s.price }}" required></div>
        <div class="form-group"><label>Длительность (мин)</label><input type="number" name="duration_min" value="{{ s.duration_min }}" required></div>
        <div style="grid-column:span 2;"><button class="btn btn-primary">Сохранить</button> <a href="/admin/services" class="btn btn-outline">Отмена</a></div>
    </form></div>"""
    return render_page('Редактирование услуги', 'services', body, s=s)

@app.route('/admin/services/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def delete_service(id):
    s = db.get_or_404(Service, id)
    db.session.delete(s)
    db.session.commit()
    log_action('DELETE', 'Service', id, f'Удалена услуга #{id}')
    flash('Услуга удалена.')
    return redirect('/admin/services')

# --- CRUD 3: СТИЛИСТЫ САЛОНА ---
@app.route('/admin/stylists')
@login_required
def list_stylists():
    body = """<div class="panel">
        <div class="toolbar"><h3>Стилисты и мастера салона</h3>
        {% if current_user.role.code in ['admin', 'manager'] %}<a href="/admin/stylists/create" class="btn btn-primary">+ Добавить стилиста</a>{% endif %}</div>
        <table><thead><tr><th>ID</th><th>ФИО мастера</th><th>Специализация</th><th>Стаж (лет)</th><th>Статус</th><th>Действия</th></tr></thead><tbody>
        {% for m in items %}<tr><td>{{ m.id }}</td><td>{{ m.full_name }}</td><td>{{ m.specialization }}</td><td>{{ m.experience_years }}</td><td>{{ 'Активен' if m.is_active else 'В отпуске' }}</td>
        <td>{% if current_user.role.code in ['admin', 'manager'] %}
            <form method="post" action="/admin/stylists/{{ m.id }}/delete" style="display:inline;" onsubmit="return confirm('Удалить стилиста?');"><button class="btn btn-danger">Удал.</button></form>
        {% else %}Просмотр{% endif %}</td></tr>{% endfor %}</tbody></table></div>"""
    return render_page('Стилисты салона', 'stylists', body, items=Stylist.query.all())

@app.route('/admin/stylists/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def create_stylist():
    if request.method == 'POST':
        m = Stylist(full_name=request.form['full_name'], specialization=request.form['specialization'], experience_years=int(request.form['experience_years']))
        db.session.add(m)
        db.session.commit()
        log_action('CREATE', 'Stylist', m.id, f'Добавлен стилист {m.full_name}')
        flash('Стилист добавлен!')
        return redirect('/admin/stylists')
    body = """<div class="panel"><form method="post" class="form-grid">
        <div class="form-group"><label>ФИО *</label><input name="full_name" required></div>
        <div class="form-group"><label>Специализация *</label><input name="specialization" required></div>
        <div class="form-group"><label>Стаж (лет) *</label><input type="number" min="0" name="experience_years" value="3" required></div>
        <div style="grid-column:span 2;"><button class="btn btn-primary">Сохранить</button></div>
    </form></div>"""
    return render_page('Новый стилист', 'stylists', body)

@app.route('/admin/stylists/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def delete_stylist(id):
    m = db.get_or_404(Stylist, id)
    db.session.delete(m)
    db.session.commit()
    log_action('DELETE', 'Stylist', id, f'Удален стилист #{id}')
    flash('Стилист удален.')
    return redirect('/admin/stylists')

# --- CRUD 4: КЛИЕНТЫ САЛОНА ---
@app.route('/admin/clients')
@login_required
def list_clients():
    body = """<div class="panel">
        <div class="toolbar"><h3>База клиентов салона</h3>
        {% if current_user.role.code in ['admin', 'manager'] %}<a href="/admin/clients/create" class="btn btn-primary">+ Добавить клиента</a>{% endif %}</div>
        <table><thead><tr><th>ID</th><th>ФИО клиента</th><th>Телефон</th><th>Email</th><th>Действия</th></tr></thead><tbody>
        {% for c in items %}<tr><td>{{ c.id }}</td><td>{{ c.full_name }}</td><td>{{ c.phone }}</td><td>{{ c.email }}</td>
        <td>{% if current_user.role.code in ['admin', 'manager'] %}
            <form method="post" action="/admin/clients/{{ c.id }}/delete" style="display:inline;" onsubmit="return confirm('Удалить клиента?');"><button class="btn btn-danger">Удал.</button></form>
        {% else %}Просмотр{% endif %}</td></tr>{% endfor %}</tbody></table></div>"""
    return render_page('Клиенты салона', 'clients', body, items=Client.query.all())

@app.route('/admin/clients/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def create_client():
    if request.method == 'POST':
        c = Client(full_name=request.form['full_name'], phone=request.form['phone'], email=request.form['email'])
        db.session.add(c)
        db.session.commit()
        log_action('CREATE', 'Client', c.id, f'Добавлен клиент {c.full_name}')
        flash('Клиент добавлен!')
        return redirect('/admin/clients')
    body = """<div class="panel"><form method="post" class="form-grid">
        <div class="form-group"><label>ФИО *</label><input name="full_name" required></div>
        <div class="form-group"><label>Телефон *</label><input name="phone" placeholder="8(999)123-45-67" required></div>
        <div class="form-group"><label>Email *</label><input type="email" name="email" required></div>
        <div style="grid-column:span 2;"><button class="btn btn-primary">Сохранить</button></div>
    </form></div>"""
    return render_page('Новый клиент', 'clients', body)

@app.route('/admin/clients/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def delete_client(id):
    c = db.get_or_404(Client, id)
    db.session.delete(c)
    db.session.commit()
    log_action('DELETE', 'Client', id, f'Удален клиент #{id}')
    flash('Клиент удален.')
    return redirect('/admin/clients')

# --- ПОЛЬЗОВАТЕЛИ И РОЛИ (ТОЛЬКО ADMIN) ---
@app.route('/admin/users')
@login_required
@role_required('admin')
def list_users():
    body = """<div class="panel"><h3>Пользователи админ-панели и разграничение ролей</h3>
        <table><thead><tr><th>ID</th><th>ФИО</th><th>Email</th><th>Роль</th><th>Статус</th><th>Управление</th></tr></thead><tbody>
        {% for u in users %}<tr><td>{{ u.id }}</td><td>{{ u.full_name }}</td><td>{{ u.email }}</td><td><b>{{ u.role.code }}</b> ({{ u.role.name }})</td>
        <td>{{ 'Активен' if u.is_active else 'Заблокирован' }}</td>
        <td>{% if u.id != current_user.id %}
            <form method="post" action="/admin/users/{{ u.id }}/toggle" style="display:inline;"><button class="btn btn-warn">{{ 'Заблокировать' if u.is_active else 'Разблокировать' }}</button></form>
        {% else %}Текущий аккаунт{% endif %}</td></tr>{% endfor %}</tbody></table></div>"""
    return render_page('Пользователи и роли', 'users', body, users=User.query.all())

@app.route('/admin/users/<int:id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def toggle_user(id):
    u = db.get_or_404(User, id)
    u.is_active = not u.is_active
    db.session.commit()
    log_action('UPDATE', 'User', u.id, f'Статус активности {u.email} изменён на {u.is_active}')
    flash(f'Статус пользователя {u.email} обновлен.')
    return redirect('/admin/users')

# --- ЖУРНАЛ ДЕЙСТВИЙ (ACTIVITY LOG) ---
@app.route('/admin/activity-log')
@login_required
@role_required('admin', 'manager')
def activity_log():
    action_filter = request.args.get('action', '')
    query = ActivityLog.query
    if action_filter:
        query = query.filter_by(action=action_filter)
    logs = query.order_by(ActivityLog.id.desc()).all()
    body = """<div class="panel">
        <div class="toolbar"><form class="filters">
            <select name="action">
                <option value="">Все типы действий</option>
                {% for act in ['LOGIN', 'LOGOUT', 'CREATE', 'UPDATE', 'DELETE'] %}<option value="{{ act }}" {{ 'selected' if action_filter==act else '' }}>{{ act }}</option>{% endfor %}
            </select><button class="btn btn-outline">Фильтр</button>
        </form></div>
        <table><thead><tr><th>ID</th><th>Дата и время</th><th>Пользователь</th><th>Действие</th><th>Сущность</th><th>Подробности</th></tr></thead><tbody>
        {% for l in logs %}<tr><td>{{ l.id }}</td><td>{{ l.created_at.strftime('%d.%m.%Y %H:%M:%S') }}</td><td>{{ l.user.full_name }} ({{ l.user.email }})</td><td><b>{{ l.action }}</b></td><td>{{ l.entity }}</td><td>{{ l.details }}</td></tr>{% endfor %}
        </tbody></table></div>"""
    return render_page('Журнал действий (Аудит)', 'log', body, logs=logs, action_filter=action_filter)

if __name__ == '__main__':
    if not os.path.exists('salon_admin.db'):
        from seed import run_seed
        run_seed()
    app.run(debug=True, port=5000)