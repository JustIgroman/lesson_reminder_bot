import os
from datetime import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

# --- Хэндлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт 👋\n\n"
        "Щоб встановити нагадування, напиши:\n"
        "/set 08:30"
    )

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Вкажи час у форматі ГГ:ХХ (наприклад 08:30)")
        return

    try:
        hour, minute = map(int, context.args[0].split(":"))
        reminder_time = time(hour, minute)

        # Используем job_queue через application
        context.application.job_queue.run_daily(
            send_reminder,
            reminder_time,
            chat_id=update.effective_chat.id,
        )

        await update.message.reply_text(
            f"✅ Нагадування встановлено на {hour:02d}:{minute:02d} щодня."
        )

    except:
        await update.message.reply_text("❌ Неправильний формат. Приклад: /set 08:30")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="⏰ Час на урок!"
    )

# --- Создание приложения ---
app = ApplicationBuilder().token(TOKEN).build()

# --- Регистрируем хэндлеры ---
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("set", set_time))

# --- Запуск ---
app.run_polling()
