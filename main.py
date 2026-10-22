import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# بخش وب‌سرور برای اینکه Render ربات رو خاموش نکنه
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# بخش اصلی ربات تلگرام
BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات با موفقیت روشن شد. (فعلاً فقط استارت کار می‌کنه، به زودی بخش انتخاب فیلم اضافه میشه)")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("دستورات:\n/start - شروع\n/help - راهنما")

if __name__ == '__main__':
    # اجرای وب‌سرور در پس‌زمینه
    threading.Thread(target=run_flask).start()
    
    # اجرای ربات تلگرام
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    print("Bot is running...")
    application.run_polling()
