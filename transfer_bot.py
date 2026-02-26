"""
🚗 Kiki Transfer Bot — Bangkok ↔ Pattaya
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, BotDescription
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ──────────────────────────────────────────
#  НАСТРОЙКИ
# ──────────────────────────────────────────
TOKEN    = "8685757419:AAEnrWRQbKcB0SStwgdN_JsCUoXEdCGIPcI"   # ← вставь свой токен
ADMIN_ID = 123456789          # ← вставь свой Telegram ID (число)
# ──────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

orders: dict = {}
order_counter = 0


# ─── FSM ─────────────────────────────────
class BKK(StatesGroup):
    baggage      = State()
    flight       = State()
    arrival_date = State()
    arrival_time = State()
    hotel        = State()
    phone        = State()
    confirm      = State()

class PTT(StatesGroup):
    baggage      = State()
    pickup       = State()
    pickup_date  = State()
    pickup_time  = State()
    phone        = State()
    confirm      = State()


# ─── Клавиатуры ──────────────────────────
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✈️ Бангкок → Паттайя", callback_data="dir_bkk"),
            InlineKeyboardButton(text="🏖 Паттайя → Бангкок", callback_data="dir_ptt"),
        ]
    ])

def kb_passengers():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1", callback_data="pax_1"),
            InlineKeyboardButton(text="2", callback_data="pax_2"),
            InlineKeyboardButton(text="3", callback_data="pax_3"),
            InlineKeyboardButton(text="4", callback_data="pax_4"),
        ],
        [
            InlineKeyboardButton(text="5", callback_data="pax_5"),
            InlineKeyboardButton(text="6", callback_data="pax_6"),
            InlineKeyboardButton(text="7", callback_data="pax_7"),
            InlineKeyboardButton(text="8", callback_data="pax_8"),
        ],
    ])

def kb_baggage():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎒 Только ручная кладь", callback_data="bag_carry"),
        ],
        [
            InlineKeyboardButton(text="🧳 1 чемодан",  callback_data="bag_1"),
            InlineKeyboardButton(text="🧳🧳 2 чемодана", callback_data="bag_2"),
        ],
        [
            InlineKeyboardButton(text="🧳🧳🧳 3+ чемодана", callback_data="bag_3"),
        ],
    ])

def kb_confirm():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить заявку", callback_data="send_order"),
            InlineKeyboardButton(text="✏️ Изменить",         callback_data="restart"),
        ],
    ])

def kb_admin(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ ЗАБРОНИРОВАНО", callback_data=f"booked_{order_id}"),
            InlineKeyboardButton(text="❌ Отказать",      callback_data=f"reject_{order_id}"),
        ]
    ])

def kb_back_to_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])


# ─── /start ──────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        "🚗 <b>Kiki Transfer</b>\n\n"
        "Комфортный трансфер между аэропортами Бангкока\n"
        "(Суварнабхуми / Дон Мыанг) и Паттайей.\n\n"
        "🕐 Работаем 24/7\n"
        "💵 Оплата водителю при посадке\n"
        "🪧 Встреча с табличкой в зоне прилёта\n\n"
        "Выберите направление:",
        reply_markup=kb_main(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🚗 <b>Kiki Transfer</b>\n\n"
        "Выберите направление:",
        reply_markup=kb_main(),
        parse_mode="HTML"
    )
    await cb.answer()


# ══════════════════════════════════════════
#  БАНГКОК → ПАТТАЙЯ
# ══════════════════════════════════════════

@dp.callback_query(F.data == "dir_bkk")
async def bkk_start(cb: CallbackQuery, state: FSMContext):
    await state.update_data(direction="✈️ Бангкок → Паттайя")
    await cb.message.edit_text(
        "✈️ <b>Бангкок → Паттайя</b>\n\n"
        "👥 Сколько пассажиров?",
        reply_markup=kb_passengers(),
        parse_mode="HTML"
    )
    await state.set_state(BKK.baggage)
    await cb.answer()

@dp.callback_query(BKK.baggage, F.data.startswith("pax_"))
async def bkk_pax(cb: CallbackQuery, state: FSMContext):
    pax = cb.data.split("_")[1]
    await state.update_data(passengers=pax)
    await cb.message.edit_text(
        f"👥 Пассажиров: {pax}\n\n"
        "🧳 Багаж:",
        reply_markup=kb_baggage(),
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(BKK.baggage, F.data.startswith("bag_"))
async def bkk_bag(cb: CallbackQuery, state: FSMContext):
    bag_map = {
        "bag_carry": "Только ручная кладь",
        "bag_1":     "1 чемодан",
        "bag_2":     "2 чемодана",
        "bag_3":     "3+ чемодана",
    }
    bag = bag_map.get(cb.data, cb.data)
    await state.update_data(baggage=bag)
    await cb.message.edit_text(
        "✈️ Введите <b>номер рейса</b>:\n"
        "<i>Например: TG207 или FD123</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.flight)
    await cb.answer()

@dp.message(BKK.flight)
async def bkk_flight(msg: Message, state: FSMContext):
    await state.update_data(flight=msg.text.strip().upper())
    await msg.answer(
        "📅 Введите <b>дату прилёта</b>:\n"
        "<i>Например: 15.03.2026</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.arrival_date)

@dp.message(BKK.arrival_date)
async def bkk_arrival_date(msg: Message, state: FSMContext):
    await state.update_data(arrival_date=msg.text.strip())
    await msg.answer(
        "🕐 Введите <b>время прилёта</b>:\n"
        "<i>Например: 14:30</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.arrival_time)

@dp.message(BKK.arrival_time)
async def bkk_arrival_time(msg: Message, state: FSMContext):
    await state.update_data(arrival_time=msg.text.strip())
    await msg.answer(
        "🏨 Введите <b>название отеля или кондо</b> в Паттайе:\n"
        "<i>Можно добавить адрес или район</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.hotel)

@dp.message(BKK.hotel)
async def bkk_hotel(msg: Message, state: FSMContext):
    await state.update_data(hotel=msg.text.strip())
    await msg.answer(
        "📱 Введите ваш <b>номер телефона</b> для связи с водителем:\n"
        "<i>Например: +66 89 123 4567</i>",
        parse_mode="HTML"
    )
    await state.set_state(BKK.phone)

@dp.message(BKK.phone)
async def bkk_phone(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text.strip())
    data = await state.get_data()
    summary = (
        f"📋 <b>Проверьте вашу заявку:</b>\n\n"
        f"🗺 {data['direction']}\n"
        f"👥 Пассажиров: {data['passengers']}\n"
        f"🧳 Багаж: {data['baggage']}\n"
        f"✈️ Рейс: {data['flight']}\n"
        f"📅 Дата прилёта: {data['arrival_date']}\n"
        f"🕐 Время прилёта: {data['arrival_time']}\n"
        f"🏨 Отель/Кондо: {data['hotel']}\n"
        f"📱 Телефон: {data['phone']}\n\n"
        f"Всё верно?"
    )
    await msg.answer(summary, reply_markup=kb_confirm(), parse_mode="HTML")
    await state.set_state(BKK.confirm)


# ══════════════════════════════════════════
#  ПАТТАЙЯ → БАНГКОК
# ══════════════════════════════════════════

@dp.callback_query(F.data == "dir_ptt")
async def ptt_start(cb: CallbackQuery, state: FSMContext):
    await state.update_data(direction="🏖 Паттайя → Бангкок")
    await cb.message.edit_text(
        "🏖 <b>Паттайя → Бангкок</b>\n\n"
        "👥 Сколько пассажиров?",
        reply_markup=kb_passengers(),
        parse_mode="HTML"
    )
    await state.set_state(PTT.baggage)
    await cb.answer()

@dp.callback_query(PTT.baggage, F.data.startswith("pax_"))
async def ptt_pax(cb: CallbackQuery, state: FSMContext):
    pax = cb.data.split("_")[1]
    await state.update_data(passengers=pax)
    await cb.message.edit_text(
        f"👥 Пассажиров: {pax}\n\n"
        "🧳 Багаж:",
        reply_markup=kb_baggage(),
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(PTT.baggage, F.data.startswith("bag_"))
async def ptt_bag(cb: CallbackQuery, state: FSMContext):
    bag_map = {
        "bag_carry": "Только ручная кладь",
        "bag_1":     "1 чемодан",
        "bag_2":     "2 чемодана",
        "bag_3":     "3+ чемодана",
    }
    bag = bag_map.get(cb.data, cb.data)
    await state.update_data(baggage=bag)
    await cb.message.edit_text(
        "📍 Введите <b>адрес подачи</b> (отель или кондо в Паттайе):\n"
        "<i>Можно добавить район</i>",
        parse_mode="HTML"
    )
    await state.set_state(PTT.pickup)
    await cb.answer()

@dp.message(PTT.pickup)
async def ptt_pickup(msg: Message, state: FSMContext):
    await state.update_data(hotel=msg.text.strip())
    await msg.answer(
        "📅 Введите <b>дату поездки</b>:\n"
        "<i>Например: 15.03.2026</i>",
        parse_mode="HTML"
    )
    await state.set_state(PTT.pickup_date)

@dp.message(PTT.pickup_date)
async def ptt_pickup_date(msg: Message, state: FSMContext):
    await state.update_data(arrival_date=msg.text.strip())
    await msg.answer(
        "🕐 Введите <b>желаемое время подачи машины</b>:\n"
        "<i>Например: 08:00</i>",
        parse_mode="HTML"
    )
    await state.set_state(PTT.pickup_time)

@dp.message(PTT.pickup_time)
async def ptt_pickup_time(msg: Message, state: FSMContext):
    await state.update_data(arrival_time=msg.text.strip())
    await msg.answer(
        "📱 Введите ваш <b>номер телефона</b>:\n"
        "<i>Например: +66 89 123 4567</i>",
        parse_mode="HTML"
    )
    await state.set_state(PTT.phone)

@dp.message(PTT.phone)
async def ptt_phone(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text.strip())
    data = await state.get_data()
    summary = (
        f"📋 <b>Проверьте вашу заявку:</b>\n\n"
        f"🗺 {data['direction']}\n"
        f"👥 Пассажиров: {data['passengers']}\n"
        f"🧳 Багаж: {data['baggage']}\n"
        f"📍 Адрес подачи: {data['hotel']}\n"
        f"📅 Дата: {data['arrival_date']}\n"
        f"🕐 Время подачи: {data['arrival_time']}\n"
        f"📱 Телефон: {data['phone']}\n\n"
        f"Всё верно?"
    )
    await msg.answer(summary, reply_markup=kb_confirm(), parse_mode="HTML")
    await state.set_state(PTT.confirm)


# ══════════════════════════════════════════
#  ОТПРАВКА ЗАЯВКИ
# ══════════════════════════════════════════

@dp.callback_query(F.data == "send_order")
async def send_order(cb: CallbackQuery, state: FSMContext):
    global order_counter
    order_counter += 1
    oid = order_counter

    data  = await state.get_data()
    user  = cb.from_user
    orders[oid] = {"user_id": user.id, "data": data}

    await cb.message.edit_text(
        "✅ <b>Заявка принята!</b>\n\n"
        "Ожидайте подтверждения. Обычно это занимает несколько минут.\n\n"
        "📞 Если срочно — свяжитесь напрямую.",
        parse_mode="HTML"
    )

    username = f"@{user.username}" if user.username else "нет username"

    if data['direction'].startswith("✈️"):
        details = (
            f"✈️ Рейс: <b>{data.get('flight')}</b>\n"
            f"📅 Дата прилёта: {data.get('arrival_date')}\n"
            f"🕐 Время прилёта: {data.get('arrival_time')}\n"
            f"🏨 Отель/Кондо: {data.get('hotel')}"
        )
    else:
        details = (
            f"📍 Адрес подачи: {data.get('hotel')}\n"
            f"📅 Дата: {data.get('arrival_date')}\n"
            f"🕐 Время подачи: {data.get('arrival_time')}"
        )

    admin_text = (
        f"🔔 <b>Новая заявка #{oid}</b>\n\n"
        f"👤 {user.full_name} ({username})\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"🗺 {data['direction']}\n"
        f"👥 Пассажиров: {data['passengers']}\n"
        f"🧳 Багаж: {data['baggage']}\n"
        f"📱 Телефон: {data.get('phone')}\n\n"
        f"{details}"
    )

    await bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=kb_admin(oid),
        parse_mode="HTML"
    )
    await state.clear()
    await cb.answer("Заявка отправлена!")

@dp.callback_query(F.data == "restart")
async def restart(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🚗 <b>Kiki Transfer</b>\n\nВыберите направление:",
        reply_markup=kb_main(),
        parse_mode="HTML"
    )
    await cb.answer()


# ══════════════════════════════════════════
#  ОТВЕТЫ АДМИНИСТРАТОРА
# ══════════════════════════════════════════

@dp.callback_query(F.data.startswith("booked_"))
async def admin_booked(cb: CallbackQuery):
    oid = int(cb.data.split("_")[1])
    if oid not in orders:
        await cb.answer("Заявка не найдена", show_alert=True)
        return

    user_id = orders[oid]["user_id"]
    data    = orders[oid]["data"]

    if data['direction'].startswith("✈️"):
        meet_info = (
            f"🪧 Водитель встретит вас с табличкой <b>Kiki Transfer</b>\n"
            f"в зоне прилёта после получения багажа."
        )
    else:
        meet_info = (
            f"🚗 Водитель подъедет к указанному адресу\n"
            f"в назначенное время."
        )

    await bot.send_message(
        user_id,
        f"✅ <b>Ваш трансфер забронирован!</b>\n\n"
        f"🗺 {data['direction']}\n"
        f"📅 Дата: {data.get('arrival_date')}\n"
        f"🕐 Время: {data.get('arrival_time')}\n\n"
        f"{meet_info}\n\n"
        f"💵 Оплата водителю при посадке\n\n"
        f"Приятной поездки! 🙏",
        reply_markup=kb_back_to_menu(),
        parse_mode="HTML"
    )

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.reply(f"✅ Заявка #{oid} подтверждена, клиент уведомлён.")
    del orders[oid]
    await cb.answer("Клиент получил подтверждение!")


@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(cb: CallbackQuery):
    oid = int(cb.data.split("_")[1])
    if oid not in orders:
        await cb.answer("Заявка не найдена", show_alert=True)
        return

    user_id = orders[oid]["user_id"]

    await bot.send_message(
        user_id,
        "😔 К сожалению, на выбранное время трансфер недоступен.\n\n"
        "Пожалуйста, свяжитесь с нами напрямую или оформите новый заказ.",
        reply_markup=kb_back_to_menu(),
        parse_mode="HTML"
    )

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.reply(f"❌ Заявка #{oid} отклонена, клиент уведомлён.")
    del orders[oid]
    await cb.answer()


# ─── Установка команд бота ───────────────
async def set_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="🚗 Заказать трансфер"),
    ])
    await bot.set_my_description(
        "🚗 Kiki Transfer — комфортный трансфер между аэропортами Бангкока "
        "(Суварнабхуми / Дон Мыанг) и Паттайей.\n\n"
        "✅ Работаем 24/7\n"
        "✅ Встреча с табличкой\n"
        "✅ Оплата водителю при посадке\n\n"
        "Нажмите СТАРТ для оформления заказа 👇"
    )
    await bot.set_my_short_description(
        "Трансфер Бангкок ↔ Паттайя 24/7 | Встреча с табличкой | Оплата водителю"
    )


# ─── Запуск ──────────────────────────────
async def main():
    await set_bot_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
