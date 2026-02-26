
"""
🚗 Kiki Transfer Bot — полная версия
Bangkok ↔ Pattaya Transfer Service
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, date, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, ReplyKeyboardRemove
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ──────────────────────────────────────────
#  НАСТРОЙКИ
# ──────────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
_admin_ids = os.environ.get("ADMIN_IDS", os.environ.get("ADMIN_ID", "123456789"))
ADMIN_IDS = [int(x.strip()) for x in _admin_ids.split(",")]

ADMIN_NAMES = {
    # Добавь сюда имена админов: ID: "Имя"
    # Например: 197940339: "Артём"
}

MANAGER_USERNAME = os.environ.get("MANAGER_USERNAME", "")
# ──────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ──────────────────────────────────────────
#  БАЗА ДАННЫХ
# ──────────────────────────────────────────
DB_PATH = "kiki.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            first_seen TEXT,
            last_seen TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            direction TEXT,
            car_type TEXT,
            car_price INTEGER,
            passengers INTEGER,
            children INTEGER,
            bags_large INTEGER,
            bags_carry INTEGER,
            flight TEXT,
            travel_date TEXT,
            travel_time TEXT,
            destination TEXT,
            name_on_board TEXT,
            status TEXT DEFAULT 'pending',
            booked_by INTEGER,
            driver_photo TEXT,
            driver_name TEXT,
            driver_phone TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            order_id INTEGER,
            text TEXT,
            direction TEXT DEFAULT 'client_to_admin',
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

def db():
    return sqlite3.connect(DB_PATH)

def track_user(user_id, username, full_name):
    now = datetime.now().isoformat()
    with db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO users (user_id, username, full_name, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_seen=?, username=?, full_name=?
        """, (user_id, username, full_name, now, now, now, username, full_name))
        conn.commit()

def track_event(user_id, event):
    now = datetime.now().isoformat()
    with db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO stats (user_id, event, created_at) VALUES (?, ?, ?)",
                  (user_id, event, now))
        conn.commit()

def save_order(data):
    now = datetime.now().isoformat()
    with db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO orders
            (user_id, username, full_name, phone, direction, car_type, car_price,
             passengers, children, bags_large, bags_carry, flight, travel_date,
             travel_time, destination, name_on_board, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (
            data['user_id'], data['username'], data['full_name'], data['phone'],
            data['direction'], data['car_type'], data['car_price'],
            data['passengers'], data.get('children', 0),
            data.get('bags_large', 0), data.get('bags_carry', 0),
            data.get('flight', '—'), data['travel_date'], data['travel_time'],
            data['destination'], data.get('name_on_board', '—'),
            now, now
        ))
        order_id = c.lastrowid
        conn.commit()
    return order_id

def save_message(user_id, username, full_name, order_id, text, direction='client_to_admin'):
    now = datetime.now().isoformat()
    with db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO messages (user_id, username, full_name, order_id, text, direction, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, full_name, order_id, text, direction, now))
        conn.commit()

def get_order(order_id):
    with db() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        return c.fetchone()

def update_order_status(order_id, status, admin_id=None):
    now = datetime.now().isoformat()
    with db() as conn:
        c = conn.cursor()
        c.execute("UPDATE orders SET status=?, booked_by=?, updated_at=? WHERE id=?",
                  (status, admin_id, now, order_id))
        conn.commit()

def update_order_driver(order_id, driver_name, driver_phone):
    now = datetime.now().isoformat()
    with db() as conn:
        c = conn.cursor()
        c.execute("UPDATE orders SET driver_name=?, driver_phone=?, updated_at=? WHERE id=?",
                  (driver_name, driver_phone, now, order_id))
        conn.commit()

def get_stats():
    with db() as conn:
        c = conn.cursor()
        today = date.today().isoformat()
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        month_ago = date.today().replace(day=1).isoformat()

        c.execute("SELECT COUNT(DISTINCT user_id) FROM stats WHERE event='start' AND created_at LIKE ?", (f"{today}%",))
        starts_today = c.fetchone()[0]

        c.execute("SELECT COUNT(DISTINCT user_id) FROM stats WHERE event='start' AND created_at >= ?", (week_ago,))
        starts_week = c.fetchone()[0]

        c.execute("SELECT COUNT(DISTINCT user_id) FROM stats WHERE event='start' AND created_at >= ?", (month_ago,))
        starts_month = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (f"{today}%",))
        orders_today = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE created_at >= ?", (week_ago,))
        orders_week = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE created_at >= ?", (month_ago,))
        orders_month = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE status IN ('booked','driver_sent','done')")
        orders_confirmed = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
        orders_pending = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE status='rejected'")
        orders_rejected = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE status='done'")
        orders_done = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE direction LIKE '%Бангкок%Паттайя%'")
        bkk_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE direction LIKE '%Паттайя%Бангкок%'")
        ptt_count = c.fetchone()[0]

        c.execute("SELECT COUNT(DISTINCT user_id) FROM users")
        total_users = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders")
        total_orders = c.fetchone()[0]

        # Статистика за последние 7 дней по дням
        daily_stats = []
        for i in range(6, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            c.execute("SELECT COUNT(DISTINCT user_id) FROM stats WHERE event='start' AND created_at LIKE ?", (f"{d}%",))
            day_starts = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (f"{d}%",))
            day_orders = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM orders WHERE status='done' AND updated_at LIKE ?", (f"{d}%",))
            day_done = c.fetchone()[0]
            daily_stats.append({'date': d, 'starts': day_starts, 'orders': day_orders, 'done': day_done})

    return {
        'starts_today': starts_today, 'starts_week': starts_week, 'starts_month': starts_month,
        'orders_today': orders_today, 'orders_week': orders_week, 'orders_month': orders_month,
        'orders_confirmed': orders_confirmed, 'orders_pending': orders_pending,
        'orders_rejected': orders_rejected, 'orders_done': orders_done,
        'bkk_count': bkk_count, 'ptt_count': ptt_count,
        'total_users': total_users, 'total_orders': total_orders,
        'daily_stats': daily_stats
    }

def get_active_orders():
    with db() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE status IN ('pending','booked','driver_sent') ORDER BY created_at DESC LIMIT 20")
        return c.fetchall()

def get_completed_orders():
    with db() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE status IN ('done','rejected') ORDER BY updated_at DESC LIMIT 20")
        return c.fetchall()

def get_user_orders(user_id):
    with db() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (user_id,))
        return c.fetchall()

# ──────────────────────────────────────────
#  АВТОМОБИЛИ
# ──────────────────────────────────────────
CARS = {
    "sedan":   {"name": "Седан",    "emoji": "🚗", "seats": 2,  "price": 1200},
    "wagon":   {"name": "Универсал","emoji": "🚙", "seats": 4,  "price": 1600},
    "minibus": {"name": "Минибас",  "emoji": "🚐", "seats": 10, "price": 1900},
}


# ──────────────────────────────────────────
#  FSM
# ──────────────────────────────────────────
class BKK(StatesGroup):
    car        = State()
    passengers = State()
    children   = State()
    bags_large = State()
    bags_carry = State()
    flight     = State()
    date       = State()
    time       = State()
    hotel      = State()
    phone      = State()
    board_name = State()
    confirm    = State()

class PTT(StatesGroup):
    car        = State()
    passengers = State()
    children   = State()
    bags_large = State()
    bags_carry = State()
    date       = State()
    time       = State()
    pickup     = State()
    room       = State()
    phone      = State()
    confirm    = State()

class DriverInfo(StatesGroup):
    photo       = State()
    driver_name = State()
    driver_phone = State()

class ClientMessage(StatesGroup):
    waiting = State()

class AdminReply(StatesGroup):
    waiting = State()


# ──────────────────────────────────────────
#  КЛАВИАТУРЫ
# ──────────────────────────────────────────
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="ℹ️ О нас",   callback_data="about"),
            InlineKeyboardButton(text="💰 Цены",    callback_data="prices"),
        ],
        [
            InlineKeyboardButton(text="✈️ Бангкок → Паттайя", callback_data="dir_bkk"),
        ],
        [
            InlineKeyboardButton(text="🏖 Паттайя → Бангкок", callback_data="dir_ptt"),
        ],
        [
            InlineKeyboardButton(text="💬 Написать менеджеру", callback_data="contact_manager"),
        ],
    ])

def kb_back_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
    ])

def kb_cars(prefix="car"):
    rows = []
    for key, car in CARS.items():
        rows.append([InlineKeyboardButton(
            text=f"{car['emoji']} {car['name']} — до {car['seats']} мест — {car['price']} ฿",
            callback_data=f"{prefix}_{key}"
        )])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_passengers(max_seats, prefix="pax"):
    nums = list(range(1, min(max_seats, 10) + 1))
    rows = []
    if len(nums) <= 5:
        rows.append([InlineKeyboardButton(text=str(n), callback_data=f"{prefix}_{n}") for n in nums])
    else:
        rows.append([InlineKeyboardButton(text=str(n), callback_data=f"{prefix}_{n}") for n in nums[:5]])
        rows.append([InlineKeyboardButton(text=str(n), callback_data=f"{prefix}_{n}") for n in nums[5:]])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_car")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_children():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Нет, только взрослые", callback_data="children_0"),
        ],
        [
            InlineKeyboardButton(text="1 ребёнок", callback_data="children_1"),
            InlineKeyboardButton(text="2 детей",   callback_data="children_2"),
            InlineKeyboardButton(text="3 детей",   callback_data="children_3"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_pax")],
    ])

def kb_bags_large(max_n):
    btns = [InlineKeyboardButton(text=str(i), callback_data=f"blarge_{i}") for i in range(0, min(max_n+1, 11))]
    rows = [btns[:6]]
    if len(btns) > 6:
        rows.append(btns[6:])
    rows = [r for r in rows if r]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_children")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_bags_carry(max_n):
    btns = [InlineKeyboardButton(text=str(i), callback_data=f"bcarry_{i}") for i in range(0, min(max_n+1, 11))]
    rows = [btns[:6]]
    if len(btns) > 6:
        rows.append(btns[6:])
    rows = [r for r in rows if r]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_bags_large")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_confirm():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить заявку", callback_data="send_order"),
            InlineKeyboardButton(text="✏️ Изменить",         callback_data="back_main"),
        ],
    ])

def kb_admin_order(order_id, direction):
    rows = [
        [
            InlineKeyboardButton(text="✅ Подтвердить",  callback_data=f"adm_book_{order_id}"),
            InlineKeyboardButton(text="❌ Отказать",     callback_data=f"adm_reject_{order_id}"),
        ],
        [InlineKeyboardButton(text="💬 Написать клиенту", callback_data=f"adm_msg_{order_id}")],
    ]
    if "Паттайя" in direction and "Бангкок" in direction:
        rows.insert(1, [InlineKeyboardButton(
            text="🚗 Отправить данные водителя", callback_data=f"adm_driver_{order_id}"
        )])
    rows.append([InlineKeyboardButton(text="✔️ Завершить заявку", callback_data=f"adm_done_{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_admin_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Активные заявки",   callback_data="admin_active"),
            InlineKeyboardButton(text="✅ Завершённые",        callback_data="admin_done"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика",         callback_data="admin_stats"),
        ],
    ])

def order_summary(data, is_bkk=True):
    car = CARS.get(data.get('car_type', 'sedan'), CARS['sedan'])
    children_txt = f"\n👶 Детей: {data.get('children', 0)}" if data.get('children', 0) else ""
    flight_txt = f"\n✈️ Рейс: {data.get('flight', '—')}" if is_bkk else ""
    if is_bkk:
        board_txt = f"\n🪧 Табличка: {data.get('name_on_board', '—')}"
    else:
        board_txt = f"\n🏢 Здание/Комната: {data.get('name_on_board', '—')}"

    return (
        f"🗺 {data['direction']}\n"
        f"{car['emoji']} {car['name']} — {car['price']} ฿\n"
        f"👥 Взрослых: {data['passengers']}{children_txt}\n"
        f"🧳 Чемоданов: {data.get('bags_large', 0)} | 🎒 Ручная кладь: {data.get('bags_carry', 0)}\n"
        f"{flight_txt}"
        f"\n📅 Дата: {data['travel_date']}"
        f"\n🕐 Время: {data['travel_time']}"
        f"\n📍 Адрес: {data['destination']}"
        f"{board_txt}"
        f"\n📱 Телефон: {data['phone']}"
    )

def order_summary_from_row(o):
    car = CARS.get(o['car_type'], {})
    is_bkk = "Бангкок" in (o['direction'] or '') and (o['direction'] or '').startswith("✈️")
    children_txt = f"\n👶 Детей: {o['children']}" if o['children'] else ""
    flight_txt = f"\n✈️ Рейс: {o['flight']}" if is_bkk and o['flight'] and o['flight'] != '—' else ""
    if is_bkk:
        board_txt = f"\n🪧 Табличка: {o['name_on_board']}"
    else:
        board_txt = f"\n🏢 Здание/Комната: {o['name_on_board']}"

    return (
        f"🗺 {o['direction']}\n"
        f"{car.get('emoji','🚗')} {car.get('name',o['car_type'])} — {o['car_price']} ฿\n"
        f"👥 Взрослых: {o['passengers']}{children_txt}\n"
        f"🧳 Чемоданов: {o['bags_large']} | 🎒 Ручная кладь: {o['bags_carry']}\n"
        f"{flight_txt}"
        f"\n📅 Дата: {o['travel_date']}"
        f"\n🕐 Время: {o['travel_time']}"
        f"\n📍 Адрес: {o['destination']}"
        f"{board_txt}"
        f"\n📱 Телефон: {o['phone']}"
    )


# ──────────────────────────────────────────
#  /start
# ──────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    user = msg.from_user
    track_user(user.id, user.username or "", user.full_name)
    track_event(user.id, "start")

    await msg.answer(
        "🚗 <b>Kiki Transfer</b>\n\n"
        "Комфортный трансфер между аэропортами Бангкока\n"
        "(Суварнабхуми / Дон Мыанг) и Паттайей.\n\n"
        "✅ <b>Бронирование без предоплаты</b>\n"
        "🪧 Встреча с именной табличкой — гарантировано\n"
        "⏰ Мониторим рейс — ждём даже при задержке\n"
        "💵 Оплата водителю при посадке\n"
        "🛣 Платные дороги включены в стоимость\n\n"
        "Выберите действие:",
        reply_markup=kb_main(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🚗 <b>Kiki Transfer</b>\n\nВыберите действие:",
        reply_markup=kb_main(),
        parse_mode="HTML"
    )
    await cb.answer()


# ──────────────────────────────────────────
#  О НАС / ЦЕНЫ
# ──────────────────────────────────────────
@dp.callback_query(F.data == "about")
async def about(cb: CallbackQuery):
    await cb.message.edit_text(
        "ℹ️ <b>О нас — Kiki Transfer</b>\n\n"
        "Мы специализируемся на комфортных трансферах между Бангкоком и Паттайей.\n\n"
        "🏆 <b>Наши преимущества:</b>\n"
        "• Гарантированная встреча с именной табличкой\n"
        "• Мониторим рейс — никаких опозданий\n"
        "• Бронирование без предоплаты\n"
        "• Оплата водителю на месте\n"
        "• Платные дороги включены\n"
        "• Чистые комфортные автомобили\n"
        "• Вежливые и опытные водители\n\n"
        "💰 <b>Цены от 1 200 бат</b>\n\n"
        "🕐 Работаем 24/7",
        reply_markup=kb_back_main(),
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(F.data == "prices")
async def prices(cb: CallbackQuery):
    await cb.message.edit_text(
        "💰 <b>Наши цены</b>\n\n"
        "🚗 <b>Седан</b> — до 2 пассажиров\n"
        "    1 200 ฿\n\n"
        "🚙 <b>Универсал</b> — до 4 пассажиров\n"
        "    1 600 ฿\n\n"
        "🚐 <b>Минибас</b> — до 10 пассажиров\n"
        "    1 900 ฿\n\n"
        "✅ Платные дороги включены\n"
        "✅ Оплата водителю при посадке\n"
        "✅ Бронирование без предоплаты",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✈️ Бангкок → Паттайя", callback_data="dir_bkk"),
            ],
            [
                InlineKeyboardButton(text="🏖 Паттайя → Бангкок", callback_data="dir_ptt"),
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")],
        ]),
        parse_mode="HTML"
    )
    await cb.answer()


# ──────────────────────────────────────────
#  ВЫБОР НАПРАВЛЕНИЯ → АВТОМОБИЛЬ
# ──────────────────────────────────────────
@dp.callback_query(F.data == "dir_bkk")
async def dir_bkk(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(direction="✈️ Бангкок → Паттайя", is_bkk=True)
    track_event(cb.from_user.id, "chose_direction_bkk")
    await cb.message.edit_text(
        "✈️ <b>Бангкок → Паттайя</b>\n\n"
        "Выберите тип автомобиля:",
        reply_markup=kb_cars(),
        parse_mode="HTML"
    )
    await state.set_state(BKK.car)
    await cb.answer()

@dp.callback_query(F.data == "dir_ptt")
async def dir_ptt(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(direction="🏖 Паттайя → Бангкок", is_bkk=False)
    track_event(cb.from_user.id, "chose_direction_ptt")
    await cb.message.edit_text(
        "🏖 <b>Паттайя → Бангкок</b>\n\n"
        "Выберите тип автомобиля:",
        reply_markup=kb_cars(),
        parse_mode="HTML"
    )
    await state.set_state(PTT.car)
    await cb.answer()


# ──────────────────────────────────────────
#  ОБЩИЙ ШАГ: ВЫБОР АВТО → ПАССАЖИРЫ
# ──────────────────────────────────────────
async def handle_car_selection(cb: CallbackQuery, state: FSMContext, car_key: str, next_state):
    car = CARS[car_key]
    await state.update_data(car_type=car_key, car_price=car['price'])
    await cb.message.edit_text(
        f"{car['emoji']} <b>{car['name']}</b> — {car['price']} ฿\n\n"
        f"👥 Укажите количество <b>взрослых пассажиров:</b>",
        reply_markup=kb_passengers(car['seats']),
        parse_mode="HTML"
    )
    await state.set_state(next_state)
    await cb.answer()

@dp.callback_query(BKK.car, F.data.startswith("car_"))
async def bkk_car(cb: CallbackQuery, state: FSMContext):
    await handle_car_selection(cb, state, cb.data.split("_", 1)[1], BKK.passengers)

@dp.callback_query(PTT.car, F.data.startswith("car_"))
async def ptt_car(cb: CallbackQuery, state: FSMContext):
    await handle_car_selection(cb, state, cb.data.split("_", 1)[1], PTT.passengers)

@dp.callback_query(F.data == "back_to_car")
async def back_to_car(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_bkk = data.get("is_bkk", True)
    await cb.message.edit_text(
        "Выберите тип автомобиля:",
        reply_markup=kb_cars(),
        parse_mode="HTML"
    )
    await state.set_state(BKK.car if is_bkk else PTT.car)
    await cb.answer()


# ──────────────────────────────────────────
#  ПАССАЖИРЫ
# ──────────────────────────────────────────
async def handle_pax(cb: CallbackQuery, state: FSMContext, next_state):
    pax = int(cb.data.split("_")[1])
    await state.update_data(passengers=pax)
    await cb.message.edit_text(
        f"👥 Взрослых пассажиров: {pax}\n\n"
        "👶 Есть ли дети?",
        reply_markup=kb_children(),
        parse_mode="HTML"
    )
    await state.set_state(next_state)
    await cb.answer()

@dp.callback_query(BKK.passengers, F.data.startswith("pax_"))
async def bkk_pax(cb: CallbackQuery, state: FSMContext):
    await handle_pax(cb, state, BKK.children)

@dp.callback_query(PTT.passengers, F.data.startswith("pax_"))
async def ptt_pax(cb: CallbackQuery, state: FSMContext):
    await handle_pax(cb, state, PTT.children)

@dp.callback_query(F.data == "back_to_pax")
async def back_to_pax(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    car = CARS.get(data.get('car_type', 'sedan'), CARS['sedan'])
    is_bkk = data.get("is_bkk", True)
    await cb.message.edit_text(
        "👥 Укажите количество взрослых пассажиров:",
        reply_markup=kb_passengers(car['seats']),
        parse_mode="HTML"
    )
    await state.set_state(BKK.passengers if is_bkk else PTT.passengers)
    await cb.answer()


# ──────────────────────────────────────────
#  ДЕТИ
# ──────────────────────────────────────────
async def handle_children(cb: CallbackQuery, state: FSMContext, next_state):
    children = int(cb.data.split("_")[1])
    await state.update_data(children=children)
    data = await state.get_data()
    total = data['passengers'] + children
    await cb.message.edit_text(
        f"👥 Взрослых: {data['passengers']}"
        + (f", 👶 Детей: {children}" if children else "") +
        f"\n\n🧳 Сколько <b>больших чемоданов</b>?",
        reply_markup=kb_bags_large(total),
        parse_mode="HTML"
    )
    await state.set_state(next_state)
    await cb.answer()

@dp.callback_query(BKK.children, F.data.startswith("children_"))
async def bkk_children(cb: CallbackQuery, state: FSMContext):
    await handle_children(cb, state, BKK.bags_large)

@dp.callback_query(PTT.children, F.data.startswith("children_"))
async def ptt_children(cb: CallbackQuery, state: FSMContext):
    await handle_children(cb, state, PTT.bags_large)

@dp.callback_query(F.data == "back_to_children")
async def back_to_children(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_bkk = data.get("is_bkk", True)
    await cb.message.edit_text(
        "👶 Есть ли дети?",
        reply_markup=kb_children(),
        parse_mode="HTML"
    )
    await state.set_state(BKK.children if is_bkk else PTT.children)
    await cb.answer()


# ──────────────────────────────────────────
#  БАГАЖ
# ──────────────────────────────────────────
async def handle_bags_large(cb: CallbackQuery, state: FSMContext, next_state):
    n = int(cb.data.split("_")[1])
    await state.update_data(bags_large=n)
    data = await state.get_data()
    total = data['passengers'] + data.get('children', 0)
    await cb.message.edit_text(
        f"🧳 Больших чемоданов: {n}\n\n"
        "🎒 Сколько <b>ручных кладей / рюкзаков</b>?",
        reply_markup=kb_bags_carry(total),
        parse_mode="HTML"
    )
    await state.set_state(next_state)
    await cb.answer()

@dp.callback_query(BKK.bags_large, F.data.startswith("blarge_"))
async def bkk_bags_large(cb: CallbackQuery, state: FSMContext):
    await handle_bags_large(cb, state, BKK.bags_carry)

@dp.callback_query(PTT.bags_large, F.data.startswith("blarge_"))
async def ptt_bags_large(cb: CallbackQuery, state: FSMContext):
    await handle_bags_large(cb, state, PTT.bags_carry)

@dp.callback_query(F.data == "back_to_bags_large")
async def back_to_bags_large(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    total = data.get('passengers', 1) + data.get('children', 0)
    is_bkk = data.get("is_bkk", True)
    await cb.message.edit_text(
        "🧳 Сколько больших чемоданов?",
        reply_markup=kb_bags_large(total),
        parse_mode="HTML"
    )
    await state.set_state(BKK.bags_large if is_bkk else PTT.bags_large)
    await cb.answer()

async def handle_bags_carry(cb: CallbackQuery, state: FSMContext, next_state, prompt: str):
    n = int(cb.data.split("_")[1])
    await state.update_data(bags_carry=n)
    await cb.message.edit_text(prompt, parse_mode="HTML")
    await state.set_state(next_state)
    await cb.answer()

@dp.callback_query(BKK.bags_carry, F.data.startswith("bcarry_"))
async def bkk_bags_carry(cb: CallbackQuery, state: FSMContext):
    await handle_bags_carry(cb, state, BKK.flight,
        "✈️ Введите <b>номер рейса</b>:\n<i>Например: TG207 или FD123</i>")

@dp.callback_query(PTT.bags_carry, F.data.startswith("bcarry_"))
async def ptt_bags_carry(cb: CallbackQuery, state: FSMContext):
    await handle_bags_carry(cb, state, PTT.date,
        "📅 Введите <b>дату поездки</b>:\n<i>Например: 15.03.2026 или 15 марта</i>")


# ──────────────────────────────────────────
#  БКК: РЕЙС → ДАТА → ВРЕМЯ → ОТЕЛЬ → ТЕЛЕФОН → ТАБЛИЧКА
# ──────────────────────────────────────────
@dp.message(BKK.flight)
async def bkk_flight(msg: Message, state: FSMContext):
    await state.update_data(flight=msg.text.strip().upper())
    await msg.answer(
        "📅 Введите <b>дату прилёта</b>:\n"
        "<i>Например: 15.03.2026 или 15 марта</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.date)

@dp.message(BKK.date)
async def bkk_date(msg: Message, state: FSMContext):
    await state.update_data(travel_date=msg.text.strip())
    await msg.answer(
        "🕐 Введите <b>время прилёта</b>:\n<i>Например: 14:30</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.time)

@dp.message(BKK.time)
async def bkk_time(msg: Message, state: FSMContext):
    await state.update_data(travel_time=msg.text.strip())
    await msg.answer(
        "🏨 Введите <b>название отеля или кондо</b> в Паттайе:\n"
        "<i>Можно добавить название или прикрепить ссылку</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.hotel)

@dp.message(BKK.hotel)
async def bkk_hotel(msg: Message, state: FSMContext):
    await state.update_data(destination=msg.text.strip())
    await msg.answer(
        "📱 Введите ваш <b>номер телефона</b>:\n"
        "<i>Российский: +7 999 123 45 67\n"
        "или тайский: +66 89 123 4567</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.phone)

@dp.message(BKK.phone)
async def bkk_phone(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text.strip())
    await msg.answer(
        "🪧 Какое <b>имя написать на табличке</b> для встречи?\n"
        "<i>Например: Ivan Petrov</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.board_name)

@dp.message(BKK.board_name)
async def bkk_board_name(msg: Message, state: FSMContext):
    await state.update_data(name_on_board=msg.text.strip())
    data = await state.get_data()
    await msg.answer(
        f"📋 <b>Проверьте вашу заявку:</b>\n\n"
        f"{order_summary(data, is_bkk=True)}\n\n"
        f"Всё верно?",
        reply_markup=kb_confirm(),
        parse_mode="HTML"
    )
    await state.set_state(BKK.confirm)


# ──────────────────────────────────────────
#  ПТТ: ДАТА → ВРЕМЯ → АДРЕС → ЗДАНИЕ/КОМНАТА → ТЕЛЕФОН
# ──────────────────────────────────────────
@dp.message(PTT.date)
async def ptt_date(msg: Message, state: FSMContext):
    await state.update_data(travel_date=msg.text.strip())
    await msg.answer(
        "🕐 Введите <b>желаемое время подачи</b>:\n<i>Например: 08:00</i>",
        parse_mode="HTML"
    )
    await state.set_state(PTT.time)

@dp.message(PTT.time)
async def ptt_time(msg: Message, state: FSMContext):
    await state.update_data(travel_time=msg.text.strip())
    await msg.answer(
        "📍 Введите <b>название отеля или кондо</b> в Паттайе:\n"
        "<i>Можно добавить название или прикрепить ссылку</i>",
        parse_mode="HTML"
    )
    await state.set_state(PTT.pickup)

@dp.message(PTT.pickup)
async def ptt_pickup(msg: Message, state: FSMContext):
    await state.update_data(destination=msg.text.strip())
    await msg.answer(
        "🏢 Укажите <b>название здания (билдинг) и номер комнаты</b>:\n"
        "<i>Например: Building A, Room 512</i>",
        parse_mode="HTML"
    )
    await state.set_state(PTT.room)

@dp.message(PTT.room)
async def ptt_room(msg: Message, state: FSMContext):
    await state.update_data(name_on_board=msg.text.strip())
    await msg.answer(
        "📱 Введите ваш <b>номер телефона</b>:\n"
        "<i>Российский: +7 999 123 45 67\n"
        "или тайский: +66 89 123 4567</i>",
        parse_mode="HTML"
    )
    await state.set_state(PTT.phone)

@dp.message(PTT.phone)
async def ptt_phone(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text.strip())
    data = await state.get_data()
    await msg.answer(
        f"📋 <b>Проверьте вашу заявку:</b>\n\n"
        f"{order_summary(data, is_bkk=False)}\n\n"
        f"Всё верно?",
        reply_markup=kb_confirm(),
        parse_mode="HTML"
    )
    await state.set_state(PTT.confirm)


# ──────────────────────────────────────────
#  ОТПРАВКА ЗАЯВКИ
# ──────────────────────────────────────────
@dp.callback_query(F.data == "send_order")
async def send_order(cb: CallbackQuery, state: FSMContext):
    data  = await state.get_data()
    user  = cb.from_user
    is_bkk = data.get('is_bkk', True)

    order_data = {
        'user_id':    user.id,
        'username':   user.username or "",
        'full_name':  user.full_name,
        **data
    }
    order_id = save_order(order_data)
    track_event(user.id, "order_created")

    await cb.message.edit_text(
        "✅ <b>Заявка принята!</b>\n\n"
        f"Номер вашей заявки: <b>#{order_id}</b>\n\n"
        "Ожидайте подтверждения. Обычно это занимает несколько минут.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать менеджеру", callback_data="contact_manager")],
            [InlineKeyboardButton(text="🏠 Главное меню",       callback_data="back_main")],
        ]),
        parse_mode="HTML"
    )

    username = f"@{user.username}" if user.username else "нет username"
    admin_text = (
        f"🔔 <b>Новая заявка #{order_id}</b>\n\n"
        f"👤 {user.full_name} ({username})\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"{order_summary(data, is_bkk=is_bkk)}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, admin_text,
                reply_markup=kb_admin_order(order_id, data['direction']),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки заявки admin {admin_id}: {e}")

    await state.clear()
    await cb.answer("Заявка отправлена!")


# ──────────────────────────────────────────
#  ДЕЙСТВИЯ АДМИНИСТРАТОРА
# ──────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_book_"))
async def admin_booked(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    order_id = int(cb.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await cb.answer("Заявка не найдена", show_alert=True)
        return

    admin_name = ADMIN_NAMES.get(cb.from_user.id, cb.from_user.first_name)
    update_order_status(order_id, "booked", cb.from_user.id)

    is_bkk = "Бангкок" in order['direction'] and order['direction'].startswith("✈️")

    car = CARS.get(order['car_type'], {})
    car_info = f"{car.get('emoji','🚗')} {car.get('name', '')} — {order['car_price']} ฿"

    if is_bkk:
        client_text = (
            f"✅ <b>Ваш трансфер #{order_id} забронирован!</b>\n\n"
            f"🗺 {order['direction']}\n"
            f"{car_info}\n"
            f"📅 {order['travel_date']} в {order['travel_time']}\n\n"
            f"🪧 Водитель встретит вас с табличкой <b>{order['name_on_board']}</b> "
            f"в зоне прилёта после получения багажа.\n\n"
            f"⏰ Мы мониторим ваш рейс — ждём даже при задержке.\n"
            f"💵 Оплата водителю при посадке.\n"
            f"🛣 Платные дороги включены.\n\n"
            f"🚭 Просьба не курить и не употреблять алкоголь в машине.\n\n"
            f"Приятной поездки! 🙏"
        )
    else:
        client_text = (
            f"✅ <b>Ваш трансфер #{order_id} забронирован!</b>\n\n"
            f"🗺 {order['direction']}\n"
            f"{car_info}\n"
            f"📅 {order['travel_date']} в {order['travel_time']}\n\n"
            f"🚗 Машина забронирована. Скоро мы пришлём вам фото автомобиля, "
            f"имя и номер телефона водителя.\n\n"
            f"💵 Оплата водителю при посадке.\n"
            f"🛣 Платные дороги включены.\n\n"
            f"🚭 Просьба не курить и не употреблять алкоголь в машине.\n\n"
            f"Ожидайте данные водителя! 🙏"
        )

    try:
        await bot.send_message(order['user_id'], client_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка отправки клиенту: {e}")

    await cb.message.edit_reply_markup(reply_markup=None)

    if not is_bkk:
        await cb.message.reply(
            f"✅ Заявка #{order_id} подтверждена ({admin_name}). Клиент уведомлён.\n\n"
            f"Когда назначите водителя — нажмите кнопку ниже:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🚗 Отправить данные водителя",
                    callback_data=f"adm_driver_{order_id}"
                )],
                [InlineKeyboardButton(
                    text="✔️ Завершить заявку",
                    callback_data=f"adm_done_{order_id}"
                )],
            ])
        )
    else:
        await cb.message.reply(
            f"✅ Заявка #{order_id} подтверждена ({admin_name}). Клиент уведомлён.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✔️ Завершить заявку",
                    callback_data=f"adm_done_{order_id}"
                )],
            ])
        )
    await cb.answer("Клиент получил подтверждение!")


@dp.callback_query(F.data.startswith("adm_reject_"))
async def admin_reject(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    order_id = int(cb.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await cb.answer("Заявка не найдена", show_alert=True)
        return

    admin_name = ADMIN_NAMES.get(cb.from_user.id, cb.from_user.first_name)
    update_order_status(order_id, "rejected", cb.from_user.id)

    try:
        await bot.send_message(
            order['user_id'],
            f"😔 К сожалению, на выбранное время трансфер #{order_id} недоступен.\n\n"
            "Пожалуйста, свяжитесь с менеджером или оформите новый заказ.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать менеджеру", callback_data="contact_manager")],
                [InlineKeyboardButton(text="🔄 Новый заказ", callback_data="back_main")],
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки клиенту: {e}")

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.reply(f"❌ Заявка #{order_id} отклонена ({admin_name}). Клиент уведомлён.")
    await cb.answer()


@dp.callback_query(F.data.startswith("adm_done_"))
async def admin_mark_done(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    order_id = int(cb.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await cb.answer("Заявка не найдена", show_alert=True)
        return

    admin_name = ADMIN_NAMES.get(cb.from_user.id, cb.from_user.first_name)
    update_order_status(order_id, "done", cb.from_user.id)

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.reply(f"✔️ Заявка #{order_id} завершена ({admin_name}).")
    await cb.answer("Заявка завершена!")


# ──────────────────────────────────────────
#  ОТПРАВКА ДАННЫХ ВОДИТЕЛЯ (Паттайя → БКК)
# ──────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_driver_"))
async def send_driver_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    order_id = int(cb.data.split("_")[2])
    await state.update_data(driver_order_id=order_id)
    await cb.message.reply(
        f"📸 Отправьте <b>фото автомобиля</b> для заявки #{order_id}:",
        parse_mode="HTML"
    )
    await state.set_state(DriverInfo.photo)
    await cb.answer()

@dp.message(DriverInfo.photo, F.photo)
async def driver_photo(msg: Message, state: FSMContext):
    await state.update_data(driver_photo_id=msg.photo[-1].file_id)
    await msg.answer("✍️ Введите <b>имя водителя</b>:", parse_mode="HTML")
    await state.set_state(DriverInfo.driver_name)

@dp.message(DriverInfo.photo)
async def driver_photo_text(msg: Message, state: FSMContext):
    await msg.answer("📸 Пожалуйста, отправьте именно <b>фото</b> автомобиля.", parse_mode="HTML")

@dp.message(DriverInfo.driver_name)
async def driver_name_handler(msg: Message, state: FSMContext):
    await state.update_data(driver_name_val=msg.text.strip())
    await msg.answer("📱 Введите <b>номер телефона водителя</b>:", parse_mode="HTML")
    await state.set_state(DriverInfo.driver_phone)

@dp.message(DriverInfo.driver_phone)
async def driver_phone_handler(msg: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('driver_order_id')
    order = get_order(order_id)

    if not order:
        await msg.answer("Заявка не найдена.")
        await state.clear()
        return

    driver_name_val = data['driver_name_val']
    driver_phone_val = msg.text.strip()
    photo_id = data.get('driver_photo_id')

    update_order_driver(order_id, driver_name_val, driver_phone_val)
    update_order_status(order_id, "driver_sent", msg.from_user.id)

    car = CARS.get(order['car_type'], {})
    car_info = f"{car.get('emoji','🚗')} {car.get('name', '')} — {order['car_price']} ฿"

    caption = (
        f"🚗 <b>Данные вашего водителя (заявка #{order_id}):</b>\n\n"
        f"👤 Имя: <b>{driver_name_val}</b>\n"
        f"📱 Телефон: <b>{driver_phone_val}</b>\n\n"
        f"{car_info}\n"
        f"📅 {order['travel_date']} в {order['travel_time']}\n"
        f"📍 {order['destination']}\n\n"
        f"💵 Оплата водителю при посадке.\n"
        f"🛣 Платные дороги включены.\n\n"
        f"🚭 Просьба не курить и не употреблять алкоголь в машине.\n\n"
        f"Хорошей дороги! 🙏"
    )

    try:
        if photo_id:
            await bot.send_photo(order['user_id'], photo_id, caption=caption, parse_mode="HTML")
        else:
            await bot.send_message(order['user_id'], caption, parse_mode="HTML")
        await msg.answer(f"✅ Данные водителя по заявке #{order_id} отправлены клиенту!")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")

    await state.clear()


# ──────────────────────────────────────────
#  НАПИСАТЬ МЕНЕДЖЕРУ (клиент)
# ──────────────────────────────────────────
@dp.callback_query(F.data == "contact_manager")
async def contact_manager(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "💬 <b>Написать менеджеру</b>\n\n"
        "Напишите ваш вопрос и мы ответим в ближайшее время:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(ClientMessage.waiting)
    await cb.answer()

@dp.message(ClientMessage.waiting)
async def client_message_received(msg: Message, state: FSMContext):
    user = msg.from_user
    username = f"@{user.username}" if user.username else "нет username"

    orders_list = get_user_orders(user.id)
    order_ref = f"Заявка #{orders_list[0]['id']}" if orders_list else "Без заявки"
    order_id = orders_list[0]['id'] if orders_list else None

    save_message(user.id, user.username or "", user.full_name, order_id, msg.text, 'client_to_admin')

    admin_text = (
        f"💬 <b>Сообщение от клиента</b>\n\n"
        f"👤 {user.full_name} ({username})\n"
        f"🆔 <code>{user.id}</code>\n"
        f"📋 {order_ref}\n\n"
        f"✉️ {msg.text}"
    )

    sent = False
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, admin_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="↩️ Ответить клиенту",
                        callback_data=f"adm_msg_{user.id}"
                    )]
                ]),
                parse_mode="HTML"
            )
            sent = True
        except Exception as e:
            logger.error(f"Ошибка пересылки сообщения: {e}")

    if sent:
        await msg.answer(
            "✅ Сообщение отправлено менеджеру!\nМы ответим вам в ближайшее время.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать ещё", callback_data="contact_manager")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")],
            ])
        )
    else:
        await msg.answer("❌ Не удалось отправить сообщение. Попробуйте позже.")

    await state.clear()


# ──────────────────────────────────────────
#  ОТВЕТ КЛИЕНТУ ОТ АДМИНИСТРАТОРА
# ──────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_msg_"))
async def admin_msg_client(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    target_id = int(cb.data.split("_")[2])
    await state.update_data(reply_target_id=target_id)
    await cb.message.reply(
        f"✍️ Напишите ответ клиенту (ID: <code>{target_id}</code>).\n"
        "Следующее ваше сообщение будет отправлено ему.\n\n"
        "Отменить: /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminReply.waiting)
    await cb.answer()

@dp.message(AdminReply.waiting)
async def admin_reply_send(msg: Message, state: FSMContext):
    if msg.text and msg.text.strip() == "/cancel":
        await state.clear()
        await msg.answer("Отменено.")
        return

    data = await state.get_data()
    target_id = data.get('reply_target_id')
    if not target_id:
        await state.clear()
        return

    admin_name = ADMIN_NAMES.get(msg.from_user.id, "Менеджер")
    try:
        await bot.send_message(
            target_id,
            f"💬 <b>Ответ от менеджера:</b>\n\n{msg.text}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Ответить", callback_data="contact_manager")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")],
            ])
        )
        save_message(msg.from_user.id, msg.from_user.username or "", msg.from_user.full_name,
                     None, msg.text, 'admin_to_client')
        await msg.answer("✅ Ответ отправлен клиенту!")
    except Exception as e:
        await msg.answer(f"❌ Не удалось отправить: {e}")

    await state.clear()


# ──────────────────────────────────────────
#  КОМАНДЫ ПОЛЬЗОВАТЕЛЯ
# ──────────────────────────────────────────
@dp.message(Command("mystatus"))
async def my_status(msg: Message, state: FSMContext):
    await state.clear()
    orders_list = get_user_orders(msg.from_user.id)
    if not orders_list:
        await msg.answer(
            "У вас пока нет заявок.\n\nОформите трансфер:",
            reply_markup=kb_main()
        )
        return

    status_map = {
        'pending':      '⏳ Ожидает подтверждения',
        'booked':       '✅ Подтверждена',
        'driver_sent':  '🚗 Водитель назначен',
        'done':         '✔️ Выполнена',
        'rejected':     '❌ Отклонена',
    }

    text = "📋 <b>Ваши последние заявки:</b>\n\n"
    for o in orders_list:
        status = status_map.get(o['status'], o['status'])
        car = CARS.get(o['car_type'], {})
        text += (
            f"<b>Заявка #{o['id']}</b>\n"
            f"🗺 {o['direction']}\n"
            f"📅 {o['travel_date']} {o['travel_time']}\n"
            f"{car.get('emoji', '🚗')} {car.get('name', '')} — {o['car_price']} ฿\n"
            f"Статус: {status}\n\n"
        )

    await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать менеджеру", callback_data="contact_manager")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")],
    ]), parse_mode="HTML")


@dp.message(Command("manager"))
async def cmd_manager(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        "💬 <b>Написать менеджеру</b>\n\n"
        "Напишите ваш вопрос и мы ответим в ближайшее время:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(ClientMessage.waiting)


# ──────────────────────────────────────────
#  АДМИН-ПАНЕЛЬ
# ──────────────────────────────────────────
@dp.message(Command("admin"))
async def admin_panel(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔️ У вас нет доступа к этой команде.")
        return
    await state.clear()
    await msg.answer(
        "🔧 <b>Админ-панель Kiki Transfer</b>\n\n"
        f"Добро пожаловать, {msg.from_user.first_name}!",
        reply_markup=kb_admin_panel(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    s = get_stats()

    daily_text = ""
    for d in s['daily_stats']:
        daily_text += f"  {d['date']}: 👁 {d['starts']} | 📋 {d['orders']} | ✔️ {d['done']}\n"

    text = (
        "📊 <b>Статистика Kiki Transfer</b>\n\n"
        "👥 <b>Посещения (открытия /start):</b>\n"
        f"  Сегодня: {s['starts_today']}\n"
        f"  За неделю: {s['starts_week']}\n"
        f"  За месяц: {s['starts_month']}\n"
        f"  Всего пользователей: {s['total_users']}\n\n"
        "📋 <b>Заявки:</b>\n"
        f"  Сегодня: {s['orders_today']}\n"
        f"  За неделю: {s['orders_week']}\n"
        f"  За месяц: {s['orders_month']}\n"
        f"  Всего заявок: {s['total_orders']}\n\n"
        "📌 <b>По статусам:</b>\n"
        f"  ⏳ Ожидают: {s['orders_pending']}\n"
        f"  ✅ Подтверждены/в работе: {s['orders_confirmed']}\n"
        f"  ✔️ Выполнено: {s['orders_done']}\n"
        f"  ❌ Отклонены: {s['orders_rejected']}\n\n"
        "🗺 <b>По направлениям:</b>\n"
        f"  ✈️ БКК → Паттайя: {s['bkk_count']}\n"
        f"  🏖 Паттайя → БКК: {s['ptt_count']}\n\n"
        "📅 <b>По дням (7 дней):</b>\n"
        f"  (👁 открытий | 📋 заявок | ✔️ выполнено)\n"
        f"{daily_text}"
    )
    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(F.data == "admin_active")
async def admin_active(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    orders_list = get_active_orders()
    if not orders_list:
        await cb.answer("Активных заявок нет", show_alert=True)
        return

    status_map = {
        'pending':      '⏳ Ожидает',
        'booked':       '✅ Подтверждена',
        'driver_sent':  '🚗 Водитель назначен',
    }

    text = "📋 <b>Активные заявки:</b>\n\n"
    btns = []
    for o in orders_list:
        car = CARS.get(o['car_type'], {})
        status = status_map.get(o['status'], o['status'])
        booked_by = ADMIN_NAMES.get(o['booked_by'], f"ID {o['booked_by']}") if o['booked_by'] else "—"
        text += (
            f"<b>#{o['id']}</b> | {status}\n"
            f"👤 {o['full_name']} | 📱 {o['phone']}\n"
            f"🗺 {o['direction']}\n"
            f"{car.get('emoji','🚗')} {car.get('name','')} — {o['car_price']} ฿\n"
            f"📅 {o['travel_date']} {o['travel_time']}\n"
            f"📍 {o['destination']}\n"
            f"👮 Принял: {booked_by}\n\n"
        )
        btns.append([InlineKeyboardButton(
            text=f"📝 Заявка #{o['id']}", callback_data=f"adm_view_{o['id']}"
        )])

    btns.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])

    await cb.message.edit_text(
        text[:4000],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("adm_view_"))
async def admin_view_order(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    order_id = int(cb.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await cb.answer("Заявка не найдена", show_alert=True)
        return

    status_map = {
        'pending':      '⏳ Ожидает',
        'booked':       '✅ Подтверждена',
        'driver_sent':  '🚗 Водитель назначен',
        'done':         '✔️ Выполнена',
        'rejected':     '❌ Отклонена',
    }

    booked_by = ADMIN_NAMES.get(order['booked_by'], f"ID {order['booked_by']}") if order['booked_by'] else "—"
    username = f"@{order['username']}" if order['username'] else "нет username"

    text = (
        f"📋 <b>Заявка #{order_id}</b>\n"
        f"Статус: {status_map.get(order['status'], order['status'])}\n"
        f"👮 Принял: {booked_by}\n\n"
        f"👤 {order['full_name']} ({username})\n"
        f"🆔 <code>{order['user_id']}</code>\n\n"
        f"{order_summary_from_row(order)}"
    )

    if order['driver_name']:
        text += f"\n\n🚗 Водитель: {order['driver_name']} | 📱 {order['driver_phone']}"

    await cb.message.edit_text(
        text,
        reply_markup=kb_admin_order(order_id, order['direction']),
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(F.data == "admin_done")
async def admin_done(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    orders_list = get_completed_orders()
    if not orders_list:
        await cb.answer("Завершённых заявок нет", show_alert=True)
        return

    text = "✅ <b>Завершённые заявки:</b>\n\n"
    for o in orders_list:
        car = CARS.get(o['car_type'], {})
        booked_by = ADMIN_NAMES.get(o['booked_by'], f"ID {o['booked_by']}") if o['booked_by'] else "—"
        status_emoji = "✔️" if o['status'] == 'done' else "❌"
        text += (
            f"{status_emoji} <b>#{o['id']}</b>\n"
            f"👤 {o['full_name']}\n"
            f"🗺 {o['direction']}\n"
            f"{car.get('emoji','🚗')} {car.get('name','')} — {o['car_price']} ฿\n"
            f"📅 {o['travel_date']}\n"
            f"👮 Принял: {booked_by}\n\n"
        )

    await cb.message.edit_text(
        text[:4000],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(F.data == "admin_back")
async def admin_back(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.message.edit_text(
        "🔧 <b>Админ-панель Kiki Transfer</b>",
        reply_markup=kb_admin_panel(),
        parse_mode="HTML"
    )
    await cb.answer()


# ──────────────────────────────────────────
#  КОМАНДА /cancel
# ──────────────────────────────────────────
@dp.message(Command("cancel"))
async def cmd_cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        "Действие отменено.\n\n🚗 <b>Kiki Transfer</b>",
        reply_markup=kb_main(),
        parse_mode="HTML"
    )


# ──────────────────────────────────────────
#  КОМАНДЫ БОТА
# ──────────────────────────────────────────
async def set_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start",    description="🚗 Заказать трансфер"),
        BotCommand(command="mystatus", description="📋 Моя заявка / статус"),
        BotCommand(command="manager",  description="💬 Написать менеджеру"),
    ])
    from aiogram.types import BotCommandScopeChat
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands([
                BotCommand(command="start",    description="🚗 Заказать трансфер"),
                BotCommand(command="mystatus", description="📋 Моя заявка / статус"),
                BotCommand(command="manager",  description="💬 Написать менеджеру"),
                BotCommand(command="admin",    description="🔧 Админ-панель"),
            ], scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logger.warning(f"Не удалось установить команды для {admin_id}: {e}")
    await bot.set_my_description(
        "🚗 Kiki Transfer — комфортный трансфер между аэропортами Бангкока "
        "(Суварнабхуми / Дон Мыанг) и Паттайей.\n\n"
        "✅ Бронирование без предоплаты\n"
        "🪧 Встреча с именной табличкой — гарантировано\n"
        "⏰ Мониторим рейс — ждём при задержке\n"
        "💵 Оплата водителю при посадке\n"
        "🛣 Платные дороги включены\n\n"
        "Нажмите СТАРТ для оформления заказа 👇"
    )
    await bot.set_my_short_description(
        "Трансфер Бангкок ↔ Паттайя 24/7 | Без предоплаты | Встреча с табличкой"
    )


# ──────────────────────────────────────────
#  ЗАПУСК
# ──────────────────────────────────────────
async def main():
    init_db()
    logger.info(f"🚀 Kiki Transfer Bot запущен. Admins: {ADMIN_IDS}")
    await set_bot_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
