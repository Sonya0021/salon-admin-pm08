from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app import app, db, Role, User, Service, Stylist, Client, Appointment, ActivityLog

def run_seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # 1. Роли
        r_admin = Role(code='admin', name='Администратор')
        r_manager = Role(code='manager', name='Менеджер')
        r_viewer = Role(code='viewer', name='Наблюдатель')
        db.session.add_all([r_admin, r_manager, r_viewer])
        db.session.commit()

        # 2. Пользователи (хэширование через Werkzeug)
        u_admin = User(email='admin@salon.local', full_name='Соколова Елена Викторовна',
                       password_hash=generate_password_hash('Admin123!'), role_id=r_admin.id, is_active=True)
        u_manager = User(email='manager@salon.local', full_name='Морозов Дмитрий Олегович',
                         password_hash=generate_password_hash('Manager123!'), role_id=r_manager.id, is_active=True)
        u_viewer = User(email='viewer@salon.local', full_name='Волкова Анна Сергеевна',
                        password_hash=generate_password_hash('Viewer123!'), role_id=r_viewer.id, is_active=True)
        db.session.add_all([u_admin, u_manager, u_viewer])
        db.session.commit()

        # 3. Услуги (CRUD 1)
        services = [
            Service(name='Женская модельная стрижка', category='Стрижки', price=1800.00, duration_min=60),
            Service(name='Мужская стрижка и укладка', category='Стрижки', price=1200.00, duration_min=45),
            Service(name='Сложное окрашивание AirTouch', category='Окрашивание', price=5500.00, duration_min=180),
            Service(name='Окрашивание в один тон', category='Окрашивание', price=3200.00, duration_min=90),
            Service(name='Вечерняя укладка у топ-стилиста', category='Укладки', price=2500.00, duration_min=60),
            Service(name='Спа-восстановление волос', category='Уход', price=2100.00, duration_min=50),
        ]
        db.session.add_all(services)

        # 4. Стилисты (CRUD 2)
        stylists = [
            Stylist(full_name='Лебедева Кристина Игоревна', specialization='Топ-стилист, колорист', experience_years=8, is_active=True),
            Stylist(full_name='Орлов Максим Андреевич', specialization='Барбер, мужские стрижки', experience_years=5, is_active=True),
            Stylist(full_name='Новикова Дарья Павловна', specialization='Стилист-универсал', experience_years=4, is_active=True),
            Stylist(full_name='Белова Ольга Николаевна', specialization='Мастер по уходу и укладкам', experience_years=6, is_active=True),
        ]
        db.session.add_all(stylists)

        # 5. Клиенты (CRUD 3)
        clients = [
            Client(full_name='Петрухина Мария Викторовна', phone='8(924)834-95-91', email='petruhina@mail.ru'),
            Client(full_name='Иванова Светлана Дмитриевна', phone='8(916)234-56-78', email='ivanova.s@gmail.com'),
            Client(full_name='Козлов Артем Сергеевич', phone='8(903)777-11-22', email='kozlov@yandex.ru'),
            Client(full_name='Смирнова Екатерина Алексеевна', phone='8(926)456-78-90', email='smirnova@mail.ru'),
            Client(full_name='Попова Наталья Владимировна', phone='8(985)111-22-33', email='popova@bk.ru'),
        ]
        db.session.add_all(clients)
        db.session.commit()

        # 6. Записи на услуги — 18 записей для демонстрации пагинации и фильтров (CRUD 4)
        statuses = ['Новая', 'Подтверждена', 'Выполнена', 'Отменена']
        payments = ['Банковская карта / СБП', 'Наличные в салоне']
        base_time = datetime(2026, 6, 1, 10, 0)

        for i in range(18):
            app_item = Appointment(
                client_id=clients[i % len(clients)].id,
                stylist_id=stylists[i % len(stylists)].id,
                service_id=services[i % len(services)].id,
                visit_date=base_time + timedelta(hours=i * 3),
                payment_method=payments[i % 2],
                status=statuses[i % 4]
            )
            db.session.add(app_item)
        db.session.commit()

        # 7. Журнал действий (Activity Log)
        logs = [
            ActivityLog(user_id=u_admin.id, action='LOGIN', entity='Auth', entity_id=u_admin.id, details='Вход администратора в систему'),
            ActivityLog(user_id=u_admin.id, action='CREATE', entity='Service', entity_id=3, details='Добавлена услуга "Сложное окрашивание AirTouch" (5500 ₽)'),
            ActivityLog(user_id=u_manager.id, action='UPDATE', entity='Appointment', entity_id=2, details='Статус записи #2 изменён на "Подтверждена"'),
            ActivityLog(user_id=u_manager.id, action='CREATE', entity='Client', entity_id=5, details='Зарегистрирован клиент Попова Наталья Владимировна'),
            ActivityLog(user_id=u_admin.id, action='UPDATE', entity='User', entity_id=u_viewer.id, details='Назначена роль viewer для Волковой А.С.'),
        ]
        db.session.add_all(logs)
        db.session.commit()
        print('База данных успешно заполнена демонстрационными данными!')

if __name__ == '__main__':
    run_seed()