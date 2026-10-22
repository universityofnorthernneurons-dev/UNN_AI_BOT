import os
import json
import base64
import requests
import threading
import io
import asyncio
import traceback
from PIL import Image
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import google.generativeai as genai

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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

REPO = "universityofnorthernneurons-dev/UNN_AI_BOT"

def load_json(file_path):
    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        content = base64.b64decode(res.json()['content']).decode('utf-8')
        return json.loads(content), res.json()['sha']
    return {}, None

def save_json(file_path, data, sha):
    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')).decode('utf-8')
    requests.put(url, headers=headers, json={"message": "Update via Bot", "content": content, "sha": sha})

def add_user(user_id):
    users_data, sha = load_json("users.json")
    if "users" not in users_data:
        users_data["users"] = []
    if user_id not in users_data["users"]:
        users_data["users"].append(user_id)
        save_json("users.json", users_data, sha)

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: return True
    settings, _ = load_json("settings.json")
    channels = settings.get("channels", [])
    if not channels: return True
    for channel in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel["id"], user_id=update.effective_user.id)
            if member.status in ['left', 'kicked']: return False
        except Exception: return False
    return True

async def send_join_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings, _ = load_json("settings.json")
    channels = settings.get("channels", [])
    keyboard = []
    for ch in channels:
        keyboard.append([InlineKeyboardButton(f"عضویت در {ch['name']}", url=ch['link'])])
    keyboard.append([InlineKeyboardButton("✅ تایید عضویت", callback_data="check_join")])
    await update.message.reply_text("⚠️ برای استفاده از ربات، ابتدا باید در کانال‌های زیر عضو شوید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await check_membership(update, context):
        await query.edit_message_text("🎉 عضویت شما تایید شد! حالا می‌توانید از ربات استفاده کنید. لطفاً دستور /start را بزنید.")
    else:
        await query.edit_message_text("❌ شما هنوز در تمام کانال‌ها عضو نشده‌اید. لطفاً ابتدا عضو شوید.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user.id)
    if not await check_membership(update, context):
        await send_join_message(update, context)
        return
    context.user_data.clear()
    settings, _ = load_json("settings.json")
    start_text = settings.get("start_text", "سلام! به ربات خوش آمدید.")
    keyboard = [
        [InlineKeyboardButton("پایه دهم", callback_data="grade_10")],
        [InlineKeyboardButton("پایه یازدهم", callback_data="grade_11")],
        [InlineKeyboardButton("پایه دوازدهم", callback_data="grade_12")]
    ]
    await update.message.reply_text(start_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "check_join":
        await check_join_callback(update, context)
        return
    if data.startswith("grade_"):
        keyboard = [[InlineKeyboardButton("ریاضی", callback_data="field_math")], [InlineKeyboardButton("تجربی", callback_data="field_exp")]]
        await query.edit_message_text(text="پایه انتخاب شد. رشته تحصیلی را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("field_"):
        keyboard = [[InlineKeyboardButton("ریاضی ۱", callback_data="subj_math1")], [InlineKeyboardButton("فیزیک ۱", callback_data="subj_phys1")]]
        await query.edit_message_text(text="رشته انتخاب شد. درس را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("subj_"):
        await query.edit_message_text(text="⏳ در حال بررسی دیتابیس...")
        videos, _ = load_json("videos.json")
        video_id = videos.get(data)
        if video_id:
            await query.edit_message_text(text="⏳ در حال ارسال فیلم...")
            await context.bot.send_video(chat_id=query.message.chat_id, video=video_id, caption="فیلم آموزشی شما")
        else:
            await query.edit_message_text(text="⚠️ فیلمی برای این درس ثبت نشده است.")

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership(update, context):
        await send_join_message(update, context)
        return
    if update.effective_user.id == ADMIN_ID and context.user_data.get('admin_state'):
        return
    settings, _ = load_json("settings.json")
    ai_prompt = settings.get("ai_prompt", "You are a helpful assistant.")
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=ai_prompt)
        if 'chat_history' not in context.user_data:
            context.user_data['chat_history'] = model.start_chat(history=[])
            
        response = await asyncio.wait_for(
            asyncio.to_thread(context.user_data['chat_history'].send_message, update.message.text),
            timeout=60.0
        )
        await update.message.reply_text(response.text)
    except asyncio.TimeoutError:
        await update.message.reply_text("⚠️ پاسخگویی گوگل بیش از حد طول کشید. لطفاً دوباره تلاش کنید.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطای متنی:\n`{str(e)}`", parse_mode='Markdown')

# --- تابع جدید پردازش عکس با روش سبک (REST API) ---
async def process_image_with_gemini(image_bytes, prompt):
    # تبدیل عکس به Base64
    img_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # آدرس API گوگل
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": img_b64
                    }
                }
            ]
        }]
    }
    
    headers = {'Content-Type': 'application/json'}
    
    # ارسال درخواست در یک ترد جداگانه تا ربات هنگ نکنه
    response = await asyncio.to_thread(requests.post, url, headers=headers, json=payload, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        try:
            return result['candidates'][0]['content']['parts'][0]['text']
        except KeyError:
            return "⚠️ گوگل پاسخی برنگرداند (احتمالاً فیلتر امنیتی عکس را رد کرده است)."
    else:
        return f"⚠️ خطای API گوگل (کد {response.status_code}):\n{response.text}"

async def ai_image_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership(update, context):
        await send_join_message(update, context)
        return
        
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
    await update.message.reply_text("👗 در حال آنالیز عکس و کشیدن الگو (لطفاً چند لحظه صبر کنید)...")
    
    settings, _ = load_json("settings.json")
    ai_prompt = settings.get("ai_prompt", "You are a Master Tailor. Analyze this clothing and provide pattern drafting instructions in Persian.")
    
    try:
        # ۱. دریافت عکس
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # ۲. تغییر سایز و تبدیل فرمت (برای سبک شدن)
        image = Image.open(io.BytesIO(photo_bytes))
        image.thumbnail((800, 800), Image.Resampling.LANCZOS) # سایز رو کوچیکتر کردیم
        img_byte_arr = io.BytesIO()
        image.convert('RGB').save(img_byte_arr, format='JPEG', quality=85) # کیفیت رو کمی کم کردیم
        img_bytes = img_byte_arr.getvalue()

        # ۳. ارسال به گوگل با متد جدید
        response_text = await process_image_with_gemini(img_bytes, ai_prompt)
        
        await update.message.reply_text(response_text)
        
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text(f"⚠️ خطای سیستمی:\n\n`{str(e)}`", parse_mode='Markdown')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎬 مدیریت فیلم‌ها", callback_data="admin_videos")],
        [InlineKeyboardButton("📢 مدیریت کانال‌ها", callback_data="admin_channels")],
        [InlineKeyboardButton("⚙️ تنظیمات متن و هوش مصنوعی", callback_data="admin_settings")]
    ]
    await update.message.reply_text("👨‍💻 **پنل مدیریت پیشرفته**\nلطفاً یک گزینه را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "admin_stats":
        users_data, _ = load_json("users.json")
        count = len(users_data.get("users", []))
        await query.edit_message_text(f"📊 در حال حاضر **{count}** نفر از ربات شما استفاده می‌کنند.", parse_mode='Markdown')
    elif data == "admin_broadcast":
        context.user_data['admin_state'] = 'waiting_for_broadcast'
        await query.edit_message_text("📢 لطفاً **متن پیام همگانی** خود را بفرستید تا برای همه کاربران ارسال شود. (برای لغو /cancel را بزنید)")
    elif data == "admin_videos":
        videos, _ = load_json("videos.json")
        text = "🎬 **لیست فیلم‌های فعلی:**\n\n"
        if not videos: text += "هیچ فیلمی ثبت نشده است.\n"
        else:
            for code in videos.keys(): text += f"🔹 کد درس: `{code}`\n"
        keyboard = [[InlineKeyboardButton("➕ افزودن فیلم جدید", callback_data="admin_add_video")], [InlineKeyboardButton("🗑️ حذف یک فیلم", callback_data="admin_del_video_menu")], [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "admin_add_video":
        context.user_data['admin_state'] = 'waiting_for_video'
        await query.edit_message_text("🎬 لطفاً حالا **فیلم** مورد نظر را ارسال کنید. (برای لغو /cancel را بزنید)")
    elif data == "admin_del_video_menu":
        videos, _ = load_json("videos.json")
        keyboard = [[InlineKeyboardButton(f"❌ حذف {code}", callback_data=f"del_vid_{code}")] for code in videos.keys()]
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_videos")])
        await query.edit_message_text("کدام فیلم حذف شود؟", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("del_vid_"):
        code = data.replace("del_vid_", "")
        videos, sha = load_json("videos.json")
        if code in videos:
            del videos[code]
            save_json("videos.json", videos, sha)
            await query.edit_message_text(f"✅ فیلم با کد `{code}` حذف شد.")
    elif data == "admin_channels":
        settings, _ = load_json("settings.json")
        channels = settings.get("channels", [])
        text = "📢 **کانال‌های تبلیغاتی:**\n\n"
        if not channels: text += "هیچ کانالی تنظیم نشده است.\n"
        for ch in channels: text += f"🔹 {ch['name']} - {ch['id']}\n"
        keyboard = [[InlineKeyboardButton("➕ افزودن کانال", callback_data="admin_add_channel")], [InlineKeyboardButton("🗑️ حذف یک کانال", callback_data="admin_del_channel_menu")], [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "admin_add_channel":
        context.user_data['admin_state'] = 'waiting_for_channel_info'
        await query.edit_message_text("📢 اطلاعات کانال را دقیقاً با این فرمت بفرستید (با علامت | جدا کنید):\n\n`@id | لینک | نام`\n\nمثال:\n`@my_chan | https://t.me/my_chan | کانال من`\n\n(برای لغو /cancel را بزنید)", parse_mode='Markdown')
    elif data == "admin_del_channel_menu":
        settings, _ = load_json("settings.json")
        channels = settings.get("channels", [])
        keyboard = [[InlineKeyboardButton(f"❌ حذف {ch['name']}", callback_data=f"del_ch_{i}")] for i, ch in enumerate(channels)]
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_channels")])
        await query.edit_message_text("کدام کانال حذف شود؟", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("del_ch_"):
        index = int(data.replace("del_ch_", ""))
        settings, sha = load_json("settings.json")
        if 0 <= index < len(settings["channels"]):
            del settings["channels"][index]
            save_json("settings.json", settings, sha)
            await query.edit_message_text("✅ کانال حذف شد.")
    elif data == "admin_settings":
        keyboard = [[InlineKeyboardButton("📝 تغییر متن استارت", callback_data="set_start_text")], [InlineKeyboardButton("🧠 تغییر شخصیت هوش مصنوعی", callback_data="set_ai_prompt")], [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]
        await query.edit_message_text("⚙️ کدام تنظیم را می‌خواهید تغییر دهید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "set_start_text":
        context.user_data['admin_state'] = 'waiting_for_start_text'
        await query.edit_message_text("📝 لطفاً **متن جدید استارت** را بفرستید. (برای لغو /cancel را بزنید)")
    elif data == "set_ai_prompt":
        context.user_data['admin_state'] = 'waiting_for_ai_prompt'
        await query.edit_message_text("🧠 لطفاً **دستورالعمل جدید هوش مصنوعی** را به انگلیسی بفرستید. (برای لغو /cancel را بزنید)")
    elif data == "admin_back":
        context.user_data['admin_state'] = None
        await admin_panel(update, context)

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    state = context.user_data.get('admin_state')
    if state == 'waiting_for_broadcast':
        users_data, _ = load_json("users.json")
        users = users_data.get("users", [])
        await update.message.reply_text(f"⏳ در حال ارسال به {len(users)} کاربر...")
        success = 0
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=update.message.text)
                success += 1
            except Exception: pass
        context.user_data['admin_state'] = None
        await update.message.reply_text(f"✅ پیام به {success} کاربر ارسال شد.")
    elif state == 'waiting_for_video':
        video = update.message.video
        if not video:
            await update.message.reply_text("لطفاً فقط فایل ویدیو ارسال کنید.")
            return
        context.user_data['temp_video_id'] = video.file_id
        context.user_data['admin_state'] = 'waiting_for_code'
        await update.message.reply_text("✅ فیلم دریافت شد. حالا کد درس را بفرستید (مثلاً: `subj_math1`):")
    elif state == 'waiting_for_code':
        code = update.message.text.strip()
        video_id = context.user_data.get('temp_video_id')
        videos, sha = load_json("videos.json")
        videos[code] = video_id
        save_json("videos.json", videos, sha)
        context.user_data['admin_state'] = None
        await update.message.reply_text(f"🎉 فیلم با موفقیت به کد `{code}` متصل شد!")
    elif state == 'waiting_for_channel_info':
        try:
            parts = [p.strip() for p in update.message.text.split('|')]
            if len(parts) != 3: raise ValueError
            settings, sha = load_json("settings.json")
            if "channels" not in settings: settings["channels"] = []
            settings["channels"].append({"id": parts[0], "link": parts[1], "name": parts[2]})
            save_json("settings.json", settings, sha)
            context.user_data['admin_state'] = None
            await update.message.reply_text("✅ کانال اضافه شد.")
        except Exception:
            await update.message.reply_text("❌ فرمت اشتباه است. مثال: `@id | link | name`")
    elif state == 'waiting_for_start_text':
        settings, sha = load_json("settings.json")
        settings["start_text"] = update.message.text
        save_json("settings.json", settings, sha)
        context.user_data['admin_state'] = None
        await update.message.reply_text("✅ متن استارت تغییر کرد.")
    elif state == 'waiting_for_ai_prompt':
        settings, sha = load_json("settings.json")
        settings["ai_prompt"] = update.message.text
        save_json("settings.json", settings, sha)
        context.user_data['admin_state'] = None
        await update.message.reply_text("✅ شخصیت هوش مصنوعی تغییر کرد.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_state'] = None
    await update.message.reply_text("✅ عملیات لغو شد.")

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("cancel", cancel))
    
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_|^del_|^set_"))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.add_handler(MessageHandler(filters.User(ADMIN_ID) & (filters.VIDEO | filters.TEXT), handle_admin_input))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))
    application.add_handler(MessageHandler(filters.PHOTO, ai_image_chat))
    
    print("Ultimate Bot is running...")
    application.run_polling()
