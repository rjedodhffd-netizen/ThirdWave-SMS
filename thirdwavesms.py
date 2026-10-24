import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CopyTextButton
import requests
import json
import os
import re
import time
import uuid
import random
from datetime import datetime, timedelta
from threading import Thread
import phonenumbers
from phonenumbers import geocoder

# ================== الإعدادات ==================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8744522940:AAG2BnKHqUZZqbJQooy7hY2Hvm2YVNFnRGE")
THIRDWAVE_API_KEY = os.getenv("THIRDWAVE_API_KEY", "tw_zoyS-liK1zcUTVmg_c5oSx9MdBNSCMwke3eG70goCW0")
MAIN_ADMIN_ID = 2017794875
MAIN_ADMIN_USERNAME = "hagouc"
OTP_GROUP_ID = -1003953419808
SUBSCRIPTION_PRICE = 10.0
SUBSCRIPTION_DAYS = 30

USERS_FILE = "users.json"
COUNTRIES_FILE = "countries.json"
SUBSCRIBERS_FILE = "subscribers.json"

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

# ================== إدارة البيانات ==================
def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return default

def save_json(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

USERS = load_json(USERS_FILE, {})
COUNTRIES = load_json(COUNTRIES_FILE, {})
SUBSCRIBERS = load_json(SUBSCRIBERS_FILE, {})

# ================== دوال مساعدة ==================
def is_admin(user_id):
    return user_id == MAIN_ADMIN_ID

def clean_number(num):
    return re.sub(r'\D', '', str(num))

def detect_country(number):
    try:
        s = str(number).strip()
        if not s.startswith('+'): s = '+' + s
        parsed = phonenumbers.parse(s)
        region = phonenumbers.region_code_for_number(parsed)
        if not region: return "Unknown", "🌍"
        name = geocoder.description_for_number(parsed, "en")
        flag = ''.join([chr(0x1F1E6 + ord(c) - ord('A')) for c in region])
        return name or region, flag
    except: return "Unknown", "🌍"

def extract_otp(text):
    if not text: return "----"
    patterns = [r'(?:code|كود|رمز|verification|OTP|otp)[:\s]*(\d{4,8})', r'\b(\d{6})\b', r'\b(\d{5})\b', r'\b(\d{4})\b']
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m: return m.group(1)
    return "----"

def detect_service(text, sender=""):
    t = (str(text) + " " + str(sender)).lower()
    services = {
        "whatsapp": ("WS", "5188683998125106802"), "واتساب": ("WS", "5188683998125106802"),
        "telegram": ("TG", "5471949924658588235"), "تيليجرام": ("TG", "5471949924658588235"),
        "facebook": ("FB", "5323261730283863478"), "فيسبوك": ("FB", "5323261730283863478"),
        "instagram": ("IG", "5319160079465857105"), "انستقرام": ("IG", "5319160079465857105"),
        "google": ("GG", "5359758030198031389"), "جوجل": ("GG", "5359758030198031389"),
        "tiktok": ("TT", "5327982530702359565")
    }
    for key, (label, eid) in services.items():
        if key in t: return label, eid
    return "OTP", "5334998226636390258"

def check_subscription(user_id):
    user_str = str(user_id)
    if user_str not in SUBSCRIBERS: return False, "not_subscribed"
    end_date = datetime.strptime(SUBSCRIBERS[user_str]["end_date"], "%Y-%m-%d %H:%M:%S")
    if end_date < datetime.now(): return False, "expired"
    return True, "active"

# ================== الأزرار ==================
def get_main_keyboard(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📲 احصل على رقم", style="primary"),
        KeyboardButton("📊 إحصائياتي", style="success")
    )
    if is_admin(user_id):
        markup.add(KeyboardButton("⚙️ لوحة الإدارة", style="danger"))
    return markup
  # ================== أوامر المستخدم ==================
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = msg.from_user.id
    USERS.setdefault(str(user_id), {
        "join_date": datetime.now().strftime("%Y-%m-%d"),
        "activations": 0,
        "selected_country": None,
        "selected_numbers": [],
        "username": msg.from_user.username or "",
        "first_name": msg.from_user.first_name or ""
    })
    USERS[str(user_id)]["username"] = msg.from_user.username or ""
    USERS[str(user_id)]["first_name"] = msg.from_user.first_name or ""
    save_json(USERS_FILE, USERS)
    
    bot.send_message(msg.chat.id, f"أهلاً بك يا {msg.from_user.first_name}!\nاختر من الأزرار بالأسفل 👇", reply_markup=get_main_keyboard(user_id))

@bot.message_handler(func=lambda m: m.text == "📲 احصل على رقم")
def get_number(msg):
    user_id = str(msg.from_user.id)
    
    sub_status, sub_msg = check_subscription(user_id)
    if not sub_status:
        if sub_msg == "not_subscribed":
            bot.reply_to(msg, f"❌ **أنت غير مشترك!**\n\nالاشتراك الشهري: **{SUBSCRIPTION_PRICE}$**\nللاستفسار والاشتراك، يرجى التواصل مع الأدمن: @{MAIN_ADMIN_USERNAME}", parse_mode="Markdown")
        elif sub_msg == "expired":
            bot.reply_to(msg, f"⚠️ **انتهى اشتراكك!**\n\nللتجديد، يرجى التواصل مع الأدمن: @{MAIN_ADMIN_USERNAME}", parse_mode="Markdown")
        return
        
    if not COUNTRIES:
        bot.reply_to(msg, "❌ لا توجد دول متاحة حالياً! اطلب من الأدمن إضافة أرقام.")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for cid, info in COUNTRIES.items():
        if info.get("count", 0) > 0:
            flag = info.get("flag", "🌍")
            markup.add(InlineKeyboardButton(f"{flag} {info['name']} (+{info['code']})", callback_data=f"country_{cid}"))
    
    if markup.keyboard:
        bot.send_message(msg.chat.id, "اختر الدولة:", reply_markup=markup)
    else:
        bot.reply_to(msg, "❌ لا توجد أرقام متاحة في أي دولة حالياً!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("country_"))
def select_country(call):
    user_id = str(call.from_user.id)
    
    sub_status, sub_msg = check_subscription(user_id)
    if not sub_status:
        bot.answer_callback_query(call.id, "❌ اشتراكك غير ساري!", show_alert=True)
        return
        
    cid = call.data.replace("country_", "")
    if cid not in COUNTRIES:
        bot.answer_callback_query(call.id, "❌ الدولة غير موجودة")
        return
    
    file = COUNTRIES[cid].get("file")
    if not file or not os.path.exists(file):
        bot.answer_callback_query(call.id, "❌ لا توجد أرقام")
        return
    
    with open(file, 'r') as f:
        nums = [l.strip() for l in f if l.strip()]
    
    if not nums:
        bot.answer_callback_query(call.id, "❌ لا توجد أرقام في هذه الدولة")
        return
    
    picked = random.sample(nums, min(4, len(nums)))
    USERS[user_id]["selected_country"] = cid
    USERS[user_id]["selected_numbers"] = picked
    save_json(USERS_FILE, USERS)
    
    markup = InlineKeyboardMarkup(row_width=1)
    for n in picked:
        markup.add(InlineKeyboardButton(f"📋 +{n}", copy_text=CopyTextButton(text=f"+{n}")))
        
    markup.add(InlineKeyboardButton("🔄 تغيير الأرقام", callback_data=f"change_nums_{cid}", style="danger"))
    
    bot.edit_message_text(
        f"✅ تم اختيار الدولة: {COUNTRIES[cid]['name']}\n\n"
        f"الأرقام المتاحة لك:\n(اضغط لنسخ الرقم)\n\n"
        f"⏳ في انتظار وصول الكود...",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("change_nums_"))
def change_numbers(call):
    user_id = str(call.from_user.id)
    
    sub_status, sub_msg = check_subscription(user_id)
    if not sub_status:
        bot.answer_callback_query(call.id, "❌ اشتراكك غير ساري!", show_alert=True)
        return
        
    cid = call.data.replace("change_nums_", "")
    file = COUNTRIES.get(cid, {}).get("file")
    if not file or not os.path.exists(file):
        return
    
    with open(file, 'r') as f:
        nums = [l.strip() for l in f if l.strip()]
    
    old = USERS[user_id].get("selected_numbers", [])
    avail = [n for n in nums if n not in old]
    if not avail: avail = nums
        
    picked = random.sample(avail, min(4, len(avail)))
    USERS[user_id]["selected_numbers"] = picked
    save_json(USERS_FILE, USERS)
    
    markup = InlineKeyboardMarkup(row_width=1)
    for n in picked:
        markup.add(InlineKeyboardButton(f"📋 +{n}", copy_text=CopyTextButton(text=f"+{n}")))
        
    markup.add(InlineKeyboardButton("🔄 تغيير الأرقام", callback_data=f"change_nums_{cid}", style="danger"))
    
    bot.edit_message_text(
        f"🔄 تم تغيير الأرقام!\n\n"
        f"الأرقام الجديدة:\n(اضغط لنسخ الرقم)\n\n"
        f"⏳ في انتظار وصول الكود...",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "📊 إحصائياتي")
def stats(msg):
    user_id = str(msg.from_user.id)
    u = USERS.get(user_id, {})
    
    sub_txt = "❌ غير مشترك"
    if user_id in SUBSCRIBERS:
        end = SUBSCRIBERS[user_id]["end_date"]
        sub_txt = f"✅ ينتهي في: {end}"
        
    txt = (
        f"👤 إحصائياتك:\n\n"
        f"📅 تاريخ الانضمام: {u.get('join_date', 'N/A')}\n"
        f"📊 عدد الأكواد المستلمة: {u.get('activations', 0)}\n"
        f"💳 الاشتراك: {sub_txt}"
    )
    bot.reply_to(msg, txt)

# ================== دالة مراقبة ThirdWave وإرسال الأكواد ==================
last_seen_key = ""

def send_otp_to_users(number, sms_text, sender):
    otp = extract_otp(sms_text)
    service, eid = detect_service(sms_text, sender)
    country, flag = detect_country(number)
    
    # 1. إرسال للمستخدمين اللي طالبين الرقم
    sent = 0
    for uid, data in USERS.items():
        if not data.get("selected_numbers"):
            continue
        
        match = False
        matched_num = None
        for n in data["selected_numbers"]:
            n_clean = clean_number(n)
            if n_clean == clean_number(number) or clean_number(number).endswith(n_clean):
                match = True
                matched_num = n
                break
        
        if match:
            try:
                msg_text = (
                    f"🌍 {country} {flag}\n"
                    f"📞 الرقم: `+{clean_number(number)}`\n"
                    f"🔑 الكود: `{otp}`\n"
                    f"<tg-emoji emoji-id='{eid}'>{service}</tg-emoji>"
                )
                bot.send_message(int(uid), msg_text, parse_mode="HTML")
                
                USERS[uid]["activations"] = USERS[uid].get("activations", 0) + 1
                if matched_num in USERS[uid]["selected_numbers"]:
                    USERS[uid]["selected_numbers"].remove(matched_num)
                sent += 1
            except Exception as e:
                print(f"Send error to {uid}: {e}")
    
    if sent > 0:
        save_json(USERS_FILE, USERS)
        print(f"✅ تم إرسال الكود لـ {sent} مستخدم: +{number} | OTP: {otp}")
    
    # 2. إرسال للجروب (دائماً) حتى لو مفيش مستخدم طالب الرقم
    if OTP_GROUP_ID:
        try:
            group_msg = (
                f"🔔 **كود جديد وصل**\n\n"
                f"🌍 الدولة: {country} {flag}\n"
                f"📞 الرقم: `+{clean_number(number)}`\n"
                f"🔑 الكود: `{otp}`\n"
                f"📨 الخدمة: {sender}\n\n"
                f"📝 **الرسالة كاملة:**\n{sms_text}"
            )
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(f"📋 نسخ الكود: {otp}", copy_text=CopyTextButton(text=otp)))
            bot.send_message(OTP_GROUP_ID, group_msg, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Group send error: {e}")

def thirdwave_loop():
    global last_seen_key
    api_key = THIRDWAVE_API_KEY
    api_url = "https://thirdwave.im/api/v1/traffic"
    
    while True:
        try:
            r = requests.get(api_url, params={"api_key": api_key, "limit": 50}, timeout=30)
            if r.status_code == 429:
                print("⚠️ Rate limit, waiting 60s...")
                time.sleep(60)
                continue
            
            if r.status_code != 200:
                time.sleep(10)
                continue
            
            data = r.json()
            items = data.get("items", [])
            if not items:
                time.sleep(5)
                continue
            
            items.sort(key=lambda x: x.get("received_at", ""), reverse=True)
            
            for item in items:
                date_str = item.get("received_at", "")
                number = item.get("number", "")
                sms = item.get("sms", "")
                sender = item.get("sender_id", "")
                
                key = f"{date_str}_{number}"
                if key == last_seen_key:
                    break
                
                if not number or not sms:
                    continue
                
                print(f"📨 OTP: {sms[:60]}... | {number}")
                send_otp_to_users(number, sms, sender)
                last_seen_key = key
            
            time.sleep(5)
        except Exception as e:
            print(f"❌ ThirdWave Error: {e}")
            time.sleep(10)
              # ================== لوحة الإدارة ==================
@bot.message_handler(func=lambda m: m.text == "⚙️ لوحة الإدارة" and is_admin(m.from_user.id))
def admin_panel(msg):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🌍 إضافة أرقام", callback_data="admin_add_country"),
        InlineKeyboardButton("👥 قائمة الدول", callback_data="admin_list_countries"),
        InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
        InlineKeyboardButton("📅 إدارة الاشتراكات", callback_data="admin_subs_menu")
    )
    bot.send_message(msg.chat.id, "⚙️ لوحة الإدارة", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callbacks(call):
    if not is_admin(call.from_user.id): return
    
    if call.data == "admin_add_country":
        bot.send_message(call.message.chat.id, "📄 أرسل ملف الأرقام (txt). كل سطر رقم.")
        user_states[call.from_user.id] = {"action": "add_numbers"}
    
    elif call.data == "admin_list_countries":
        txt = "🌍 قائمة الدول:\n"
        for cid, info in COUNTRIES.items():
            txt += f"• {info.get('flag','🌍')} {info['name']} (+{info['code']}) - {info.get('count', 0)} رقم\n"
        bot.send_message(call.message.chat.id, txt or "❌ لا توجد دول مضافة.")
    
    elif call.data == "admin_stats":
        bot.send_message(call.message.chat.id, f"👥 المستخدمين: {len(USERS)}\n🌍 الدول: {len(COUNTRIES)}\n💳 المشتركين: {len(SUBSCRIBERS)}")

    elif call.data == "admin_subs_menu":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("➕ إعطاء اشتراك لمستخدم", callback_data="admin_give_sub"),
            InlineKeyboardButton("❌ إلغاء اشتراك مستخدم", callback_data="admin_cancel_sub"),
            InlineKeyboardButton("📋 قائمة المشتركين", callback_data="admin_list_subs")
        )
        bot.edit_message_text("📅 إدارة الاشتراكات", call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data == "admin_give_sub":
        bot.send_message(call.message.chat.id, "أرسل **ID** أو **Username** (بدون @) للمستخدم اللي عايز تديله اشتراك:")
        user_states[call.from_user.id] = {"action": "give_sub_get_user"}
        
    elif call.data == "admin_cancel_sub":
        bot.send_message(call.message.chat.id, "أرسل **ID** أو **Username** (بدون @) للمستخدم اللي عايز تلغي اشتراكه:")
        user_states[call.from_user.id] = {"action": "cancel_sub_get_user"}

    elif call.data == "admin_list_subs":
        txt = "📋 قائمة المشتركين:\n\n"
        active = 0
        for uid, data in SUBSCRIBERS.items():
            try:
                end_date = datetime.strptime(data.get("end_date"), "%Y-%m-%d %H:%M:%S")
                if end_date > datetime.now():
                    active += 1
                    u = USERS.get(uid, {})
                    uname = u.get("username", "N/A")
                    name = u.get("first_name", "N/A")
                    txt += f"👤 الاسم: {name}\n"
                    txt += f"🆔 ID: `{uid}`\n"
                    txt += f"📎 User: @{uname}\n"
                    txt += f"📅 ينتهي: {data['end_date']}\n"
                    txt += f"-------------------\n"
            except: pass
        if active == 0:
            txt += "لا يوجد مشتركين نشطين حالياً."
        bot.send_message(call.message.chat.id, txt, parse_mode="Markdown")

# ================== استقبال الملفات من الأدمن ==================
@bot.message_handler(content_types=['document'])
def handle_document(msg):
    user_id = msg.from_user.id
    state = user_states.get(user_id, {})
    if state.get("action") != "add_numbers" or not is_admin(user_id):
        return
    
    file_info = bot.get_file(msg.document.file_id)
    if not file_info.file_path.endswith('.txt'):
        bot.reply_to(msg, "❌ يجب إرسال ملف txt")
        return
    
    downloaded = bot.download_file(file_info.file_path)
    filename = f"numbers_{uuid.uuid4().hex[:8]}.txt"
    with open(filename, 'wb') as f:
        f.write(downloaded)
    
    with open(filename, 'r') as f:
        lines = [l.strip() for l in f if l.strip()]
    
    if not lines:
        bot.reply_to(msg, "❌ الملف فارغ!")
        return
    
    first = clean_number(lines[0])
    code = first[:2] if first else "20"
    name, flag = detect_country(first)
    
    cid = f"{name}_{uuid.uuid4().hex[:6]}"
    COUNTRIES[cid] = {
        "name": name,
        "flag": flag,
        "code": code,
        "file": filename,
        "count": len(lines)
    }
    save_json(COUNTRIES_FILE, COUNTRIES)
    del user_states[user_id]
    
    bot.reply_to(msg, f"✅ تم إضافة {len(lines)} رقم لدولة {name} {flag} (+{code})")

# ================== معالجة حالات النصوص (للأدمن) ==================
@bot.message_handler(func=lambda m: m.from_user.id in user_states and m.content_type == 'text')
def handle_states(msg):
    user_id = msg.from_user.id
    state = user_states.get(user_id, {})
    action = state.get("action")
    
    if action == "give_sub_get_user":
        target = msg.text.strip().replace("@", "")
        target_id = None
        if target.isdigit():
            target_id = target
        else:
            for uid, data in USERS.items():
                if data.get("username", "").lower() == target.lower():
                    target_id = uid
                    break
        
        if not target_id:
            bot.reply_to(msg, "❌ لم يتم العثور على المستخدم. تأكد من الـ ID أو الـ Username.")
            del user_states[msg.from_user.id]
            return
        
        end_date = (datetime.now() + timedelta(days=SUBSCRIPTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        SUBSCRIBERS[target_id] = {
            "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end_date,
            "price": SUBSCRIPTION_PRICE
        }
        save_json(SUBSCRIBERS_FILE, SUBSCRIBERS)
        del user_states[msg.from_user.id]
        
        bot.reply_to(msg, f"✅ تم تفعيل الاشتراك للمستخدم `{target_id}` لمدة {SUBSCRIPTION_DAYS} يوم.\n📅 ينتهي في: {end_date}")
        try:
            bot.send_message(int(target_id), f"🎉 تم تفعيل اشتراكك!\n📅 الاشتراك ساري حتى: {end_date}\n💰 السعر: {SUBSCRIPTION_PRICE}$ شهرياً")
        except: pass

    elif action == "cancel_sub_get_user":
        target = msg.text.strip().replace("@", "")
        target_id = None
        if target.isdigit():
            target_id = target
        else:
            for uid, data in USERS.items():
                if data.get("username", "").lower() == target.lower():
                    target_id = uid
                    break
        
        if not target_id or target_id not in SUBSCRIBERS:
            bot.reply_to(msg, "❌ المستخدم غير موجود أو ليس لديه اشتراك.")
            del user_states[msg.from_user.id]
            return
        
        del SUBSCRIBERS[target_id]
        save_json(SUBSCRIBERS_FILE, SUBSCRIBERS)
        del user_states[msg.from_user.id]
        
        bot.reply_to(msg, f"✅ تم إلغاء اشتراك المستخدم `{target_id}`.")
        try:
            bot.send_message(int(target_id), "⚠️ تم إلغاء اشتراكك. للاشتراك مرة أخرى يرجى التواصل مع الأدمن.")
        except: pass

# ================== التشغيل ==================
if __name__ == "__main__":
    print("🚀 بدء البوت...")
    thread = Thread(target=thirdwave_loop, daemon=True)
    thread.start()
    print("✅ ThirdWave Loop started!")
    bot.infinity_polling()
    