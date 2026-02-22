import os
from datetime import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт 👋\n\n"
        "Щоб встановити нагадування, напиши:\n"
        "/set ГГ:ХХ (наприклад /set 08:30)"
    )

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Вкажи час у форматі ГГ:ХХ (наприклад /set 08:30)"
        )
        return

    try:
        hour, minute = map(int, context.args[0].split(":"))
        reminder_time = time(hour, minute)

        context.application.job_queue.run_daily(
            send_reminder,
            reminder_time,
            chat_id=update.effective_chat.id
        )

        await update.message.reply_text(
            f"✅ Нагадування встановлено на {hour:02d}:{minute:02d} щодня."
        )

    except ValueError:
        await update.message.reply_text(
            "❌ Неправильний формат. Приклад: /set 08:30"
        )

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="⏰ Час на урок!"
    )

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("set", set_time))

if __name__ == "__main__":
    app.run_polling()
