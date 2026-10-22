import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# --- بخش تستی (بعداً اینجا فیلم‌های واقعی رو می‌ذاریم) ---
TEST_MEDIA = "https://telegram.org/img/t_logo.png" 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("پایه دهم", callback_data="grade_10")],
        [InlineKeyboardButton("پایه یازدهم", callback_data="grade_11")],
        [InlineKeyboardButton("پایه دوازدهم", callback_data="grade_12")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("سلام! لطفاً **پایه تحصیلی** خود را انتخاب کنید:", reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("grade_"):
        context.user_data['grade'] = data
        keyboard = [
            [InlineKeyboardButton("رشته ریاضی", callback_data="field_math")],
            [InlineKeyboardButton("رشته تجربی", callback_data="field_exp")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="پایه انتخاب شد. حالا **رشته تحصیلی** را انتخاب کنید:", reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith("field_"):
        context.user_data['field'] = data
        keyboard = [
            [InlineKeyboardButton("ریاضی ۱", callback_data="subj_math1")],
            [InlineKeyboardButton("فیزیک ۱", callback_data="subj_phys1")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="رشته انتخاب شد. حالا **درس** را انتخاب کنید:", reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith("subj_"):
        context.user_data['subject'] = data
        keyboard = [
            [InlineKeyboardButton("استاد احمدی", callback_data="teacher_ahmadi")],
            [InlineKeyboardButton("استاد رضایی", callback_data="teacher_rezaei")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="درس انتخاب شد. حالا **معلم** را انتخاب کنید:", reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith("teacher_"):
        context.user_data['teacher'] = data
        keyboard = [
            [InlineKeyboardButton("فصل ۱", callback_data="chap_1")],
            [InlineKeyboardButton("فصل ۲", callback_data="chap_2")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="معلم انتخاب شد. حالا **فصل** را انتخاب کنید:", reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith("chap_"):
        await query.edit_message_text(text="⏳ در حال آماده‌سازی و ارسال فایل تستی...")
        
        try:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=TEST_MEDIA,
                caption=f"🎬 این یک تست است!\n\nپایه: {context.user_data.get('grade')}\nدرس: {context.user_data.get('subject')}\n\nبه زودی فیلم‌های واقعی جایگزین می‌شوند."
            )
        except Exception as e:
            await context.bot.send_message(chat_id=query.message.chat_id, text="خطا در ارسال تست.")

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running...")
    application.run_polling()
