import os
import json
import base64
import requests
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# نام کاربری و مخزن گیت‌هاب شما
REPO = "universityofnorthernneurons-dev/UNN_AI_BOT"
FILE_PATH = "videos.json"

# --- توابع اتصال به گیت‌هاب به عنوان دیتابیس ---
def get_videos():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        content = base64.b64decode(res.json()['content']).decode('utf-8')
        return json.loads(content), res.json()['sha']
    return {}, None

def update_videos(videos, sha):
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content = base64.b64encode(json.dumps(videos, ensure_ascii=False, indent=2).encode('utf-8')).decode('utf-8')
    data = {"message": "Update videos via Bot", "content": content, "sha": sha}
    requests.put(url, headers=headers, json=data)

# --- بخش کاربران عادی ---
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
        await query.edit_message_text(text="⏳ در حال بررسی دیتابیس...")
        
        # دریافت فیلم از گیت‌هاب
        videos, _ = get_videos()
        video_id = videos.get(data)
        
        if video_id:
            await query.edit_message_text(text="⏳ در حال ارسال فیلم...")
            await context.bot.send_video(chat_id=query.message.chat_id, video=video_id, caption="فیلم آموزشی شما")
        else:
            await query.edit_message_text(text="⚠️ فیلمی برای این درس ثبت نشده است. (با پنل ادمین اضافه کنید)")

# --- بخش پنل ادمین (فقط برای شما) ---
async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    context.user_data['admin_state'] = 'waiting_for_video'
    await update.message.reply_text("👨‍💻 **پنل ادمین**\nلطفاً حالا **فیلم** مورد نظر را برای من ارسال کنید (یا فوروارد کنید).")

async def handle_admin_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or context.user_data.get('admin_state') != 'waiting_for_video':
        return
    
    video = update.message.video
    if not video:
        await update.message.reply_text("لطفاً فقط فایل ویدیو ارسال کنید.")
        return
        
    context.user_data['temp_video_id'] = video.file_id
    context.user_data['admin_state'] = 'waiting_for_code'
    await update.message.reply_text("✅ فیلم دریافت شد.\nحالا کد درس را بفرستید (مثلاً: `subj_math1` یا `subj_phys1`):")

async def handle_admin_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or context.user_data.get('admin_state') != 'waiting_for_code':
        return
    
    code = update.message.text.strip()
    video_id = context.user_data.get('temp_video_id')
    
    await update.message.reply_text("⏳ در حال ذخیره در دیتابیس گیت‌هاب...")
    
    videos, sha = get_videos()
    videos[code] = video_id
    update_videos(videos, sha)
    
    context.user_data['admin_state'] = None
    await update.message.reply_text(f"🎉 فیلم با موفقیت به کد `{code}` متصل شد!\nحالا کاربران با زدن این دکمه، فیلم را دریافت می‌کنند.")

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # دستورات ادمین
    application.add_handler(CommandHandler("admin", admin_add))
    application.add_handler(MessageHandler(filters.VIDEO & filters.User(ADMIN_ID), handle_admin_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID), handle_admin_code))
    
    print("Bot is running...")
    application.run_polling()
