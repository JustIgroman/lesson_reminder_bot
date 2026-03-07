import logging
import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Отключаем спам от сетевых запросов и планировщика
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

TOKEN = '8284386701:AAGUq_drKOb8dCgTovXWH4XTc9FzX6-Eu9c'
DB_FILE = 'reminders.csv'
USERS_FILE = 'users.csv'

# --- Функции для работы с CSV (Пользователи) ---

def load_users():
    """Загружает словарь пользователей и их часовых поясов."""
    if not os.path.exists(USERS_FILE):
        return {}
    users = {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) == 2:
                users[int(row[0])] = row[1]
    return users

def save_user(chat_id, tz_name):
    """Сохраняет часовой пояс пользователя."""
    users = load_users()
    users[chat_id] = tz_name
    with open(USERS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for cid, tz in users.items():
            writer.writerow([cid, tz])

# --- Функции для работы с CSV (Напоминания) ---

def init_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['chat_id', 'datetime', 'text'])

def load_reminders():
    init_db()
    reminders = []
    with open(DB_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['chat_id'] = int(row['chat_id'])
            reminders.append(row)
    return reminders

def save_reminder(chat_id, dt_str, text):
    init_db()
    with open(DB_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([chat_id, dt_str, text])

def remove_reminder(chat_id, dt_str, text):
    reminders = load_reminders()
    reminders = [r for r in reminders if not (r['chat_id'] == chat_id and r['datetime'] == dt_str and r['text'] == text)]
    
    with open(DB_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['chat_id', 'datetime', 'text'])
        for r in reminders:
            writer.writerow([r['chat_id'], r['datetime'], r['text']])

# --- Обработчики команд ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Украина 🇺🇦", callback_data="tz_Europe/Kyiv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Привет! Я бот-напоминалка ⏰\n\n"
        "Для начала выбери свою страну, чтобы я правильно настроил время:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на инлайн-кнопки."""
    query = update.callback_query
    await query.answer() 
    
    data = query.data
    chat_id = query.message.chat_id

    if data.startswith("tz_"):
        tz_name = data.split("tz_")[1]
        save_user(chat_id, tz_name)
        
        await query.edit_message_text(
            "✅ Страна и часовой пояс успешно настроены!\n\n"
            "Установка: `/set ЧЧ:ММ [ДД.ММ.ГГГГ] Текст`\n"
            "Мои задачи: `/list`\n\n"
            "Пример: `/set 15:30 Купить хлеб`\n"
            "Пример с датой: `/set 10:00 31.12.2024 Поздравить всех`",
            parse_mode='Markdown'
        )

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    text = job.data
    dt_str = job.name 
    
    await context.bot.send_message(chat_id=chat_id, text=f"⏰ НАПОМИНАНИЕ:\n{text}")
    remove_reminder(chat_id, dt_str, text)

async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args
    
    users = load_users()
    if chat_id not in users:
        await update.message.reply_text("❌ Пожалуйста, сначала выбери свою страну командой /start")
        return
        
    user_tz = ZoneInfo(users[chat_id])
    now = datetime.now(user_tz)

    if len(args) < 2:
        await update.message.reply_text("❌ Ошибка: Укажите время и текст!\nПример: /set 15:30 Позвонить маме")
        return

    time_str = args[0]
    try:
        reminder_time = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        await update.message.reply_text("❌ Ошибка формата времени! Используйте ЧЧ:ММ")
        return

    has_date = False
    text_start_index = 1
    reminder_date = now.date()
    
    # Продвинутый парсинг даты
    if len(args) > 1:
        date_str = args[1]
        # Проверяем, похож ли аргумент на дату (есть точки и цифры)
        if '.' in date_str and any(c.isdigit() for c in date_str):
            try:
                parts = date_str.split('.')
                if len(parts) == 2:  # Формат ДД.ММ
                    parsed_date = datetime.strptime(date_str, "%d.%m")
                    reminder_date = parsed_date.replace(year=now.year).date()
                elif len(parts) == 3 and len(parts[2]) == 2:  # Формат ДД.ММ.ГГ
                    reminder_date = datetime.strptime(date_str, "%d.%m.%y").date()
                elif len(parts) == 3 and len(parts[2]) == 4:  # Формат ДД.ММ.ГГГГ
                    reminder_date = datetime.strptime(date_str, "%d.%m.%Y").date()
                else:
                    raise ValueError
                has_date = True
                text_start_index = 2
            except ValueError:
                await update.message.reply_text("❌ Ошибка формата даты!\nДопустимые форматы: ДД.ММ, ДД.ММ.ГГ или ДД.ММ.ГГГГ")
                return

    if text_start_index >= len(args):
        await update.message.reply_text("❌ Ошибка: Вы забыли написать текст напоминания!")
        return

    reminder_text = " ".join(args[text_start_index:])
    
    # Объединяем дату и время с учетом часового пояса
    target_datetime = datetime.combine(reminder_date, reminder_time).replace(tzinfo=user_tz)

    # Проверка на то, чтобы таймер не был установлен в прошлое
    if target_datetime < now:
        if has_date:
            await update.message.reply_text(f"❌ Ошибка: Указанная дата и время ({target_datetime.strftime('%d.%m.%Y %H:%M')}) уже в прошлом!")
        else:
            await update.message.reply_text(f"❌ Ошибка: Время {time_str} сегодня уже прошло!")
        return

    dt_key = target_datetime.isoformat()
    save_reminder(chat_id, dt_key, reminder_text)

    context.job_queue.run_once(
        send_reminder,
        when=target_datetime,
        chat_id=chat_id,
        data=reminder_text,
        name=dt_key
    )

    logger.info(f"Добавлено: chat_id={chat_id} | время={dt_key} | текст='{reminder_text}'")
    await update.message.reply_text(
        f"✅ Установлено на {target_datetime.strftime('%d.%m.%Y в %H:%M')}\n📝 Текст: {reminder_text}"
    )

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    users = load_users()
    if chat_id not in users:
        await update.message.reply_text("❌ Пожалуйста, сначала выбери свою страну командой /start")
        return
        
    reminders = load_reminders()
    user_reminders = [r for r in reminders if r['chat_id'] == chat_id]
    
    if not user_reminders:
        await update.message.reply_text("📭 У вас нет активных напоминаний.")
        return

    user_reminders.sort(key=lambda x: datetime.fromisoformat(x['datetime']))

    msg = "📋 **Ваши напоминания:**\n\n"
    for i, r in enumerate(user_reminders, 1):
        dt = datetime.fromisoformat(r['datetime'])
        msg += f"*{i}.* `{dt.strftime('%d.%m.%Y %H:%M')}` — {r['text']}\n"
        
    await update.message.reply_text(msg, parse_mode='Markdown')

async def post_init(application: Application):
    reminders = load_reminders()
    count = 0
    
    for r in reminders:
        run_at = datetime.fromisoformat(r['datetime'])
        
        tz = run_at.tzinfo or ZoneInfo("UTC")
        now = datetime.now(tz)
        
        if run_at > now:
            application.job_queue.run_once(
                send_reminder,
                when=run_at,
                chat_id=r['chat_id'],
                data=r['text'],
                name=r['datetime']
            )
            count += 1
        else:
            remove_reminder(r['chat_id'], r['datetime'], r['text'])
            
    logger.info(f"Бот запущен. Восстановлено задач из CSV: {count}")

def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("set", set_timer))
    application.add_handler(CommandHandler("list", list_reminders))
    
    application.run_polling()

if __name__ == '__main__':
    main()
