import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import requests
import json
import os
import re
import time
import uuid
import random
from datetime import datetime, timedelta
from threading import Thread, Event
import phonenumbers
from phonenumbers import geocoder

# ================== الإعدادات ==================
BOT_TOKEN = "8744522940:AAG2BnKHqUZZqbJQooy7hY2Hvm2YVNFnRGE"
MAIN_ADMIN_ID = 2017794875
SETTINGS_FILE = "settings.json"
COUNTRY_FILE = "countries.json"
USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"
REFERRALS_FILE = "referrals.json"
REQUESTS_FILE = "withdrawal_requests.json"
OTP_GROUP_FILE = "otp_group.json"

DEFAULT_SETTINGS = {
    "ThirdWave": {
        "name": "ThirdWave",
        "api_key": "tw_zoyS-liK1zcUTVmg_c5oSx9MdBNSCMwke3eG70goCW0",
        "api_url": "https://thirdwave.im/api/v1/traffic",
        "check_interval": 5,
        "enabled": True
    }
}

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}
bot_info = None

# ================== تحميل وحفظ البيانات ==================
def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

SETTINGS = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
COUNTRIES = load_json(COUNTRY_FILE, {})
USERS = load_json(USERS_FILE, {})
ADMINS = load_json(ADMINS_FILE, [MAIN_ADMIN_ID])
REFERRALS = load_json(REFERRALS_FILE, {})
WITHDRAWALS = load_json(REQUESTS_FILE, [])
OTP_GROUP = load_json(OTP_GROUP_FILE, {"group_id": None})["group_id"]

# ================== دوال مساعدة ==================
def is_admin(user_id):
    return user_id in ADMINS or user_id == MAIN_ADMIN_ID

def clean_number(num):
    return re.sub(r'\D', '', str(num))

def detect_country(number):
    try:
        s = str(number).strip()
        if not s.startswith('+'):
            s = '+' + s
        parsed = phonenumbers.parse(s)
        region = phonenumbers.region_code_for_number(parsed)
        if not region:
            return "Unknown", "🌍"
        name = geocoder.description_for_number(parsed, "en")
        flag = ''.join([chr(0x1F1E6 + ord(c) - ord('A')) for c in region])
        return name or region, flag
    except:
        return "Unknown", "🌍"

def extract_otp(text):
    if not text:
        return "----"
    patterns = [
        r'(?:code|كود|رمز|verification|OTP|otp)[:\s]*(\d{4,8})',
        r'\b(\d{6})\b',
        r'\b(\d{5})\b',
        r'\b(\d{4})\b'
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return "----"

def detect_service(text, sender=""):
    t = (str(text) + " " + str(sender)).lower()
    services = {
        "whatsapp": ("WS", "5188683998125106802"),
        "واتساب": ("WS", "5188683998125106802"),
        "telegram": ("TG", "5471949924658588235"),
        "تيليجرام": ("TG", "5471949924658588235"),
        "facebook": ("FB", "5323261730283863478"),
        "فيسبوك": ("FB", "5323261730283863478"),
        "instagram": ("IG", "5319160079465857105"),
        "انستقرام": ("IG", "5319160079465857105"),
        "google": ("GG", "5359758030198031389"),
        "جوجل": ("GG", "5359758030198031389"),
        "tiktok": ("TT", "5327982530702359565"),
    }
    for key, (label, eid) in services.items():
        if key in t:
            return label, eid
    return "OTP", "5334998226636390258"

def load_data():
    global SETTINGS, COUNTRIES, USERS, ADMINS, REFERRALS, WITHDRAWALS, OTP_GROUP
    SETTINGS = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    COUNTRIES = load_json(COUNTRY_FILE, {})
    USERS = load_json(USERS_FILE, {})
    ADMINS = load_json(ADMINS_FILE, [MAIN_ADMIN_ID])
    REFERRALS = load_json(REFERRALS_FILE, {})
    WITHDRAWALS = load_json(REQUESTS_FILE, [])
    OTP_GROUP = load_json(OTP_GROUP_FILE, {"group_id": None})["group_id"]
    
    # ================== أوامر البوت والأزرار ==================
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = msg.from_user.id
    USERS.setdefault(str(user_id), {
        "join_date": datetime.now().strftime("%Y-%m-%d"),
        "activations": 0,
        "selected_country": None,
        "selected_numbers": [],
        "balance": 0.0,
        "referred_by": None
    })
    save_json(USERS_FILE, USERS)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = KeyboardButton("📲 احصل على رقم", style="primary")
    btn2 = KeyboardButton("📊 إحصائياتي", style="success")
    btn3 = KeyboardButton("💰 رصيدي", style="primary")
    btn4 = KeyboardButton("💸 سحب الرصيد", style="danger")
    markup.row(btn1, btn2)
    markup.row(btn3, btn4)
    
    if is_admin(user_id):
        markup.add(KeyboardButton("⚙️ لوحة الإدارة", style="primary"))
    
    bot.send_message(msg.chat.id, f"أهلاً بك يا {msg.from_user.first_name}!\nاختر من الأزرار بالأسفل 👇", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📲 احصل على رقم")
def get_number(msg):
    user_id = msg.from_user.id
    if not COUNTRIES:
        bot.reply_to(msg, "❌ لا توجد دول متاحة حالياً!")
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
    
    user_id = str(call.from_user.id)
    USERS[user_id]["selected_country"] = cid
    USERS[user_id]["selected_numbers"] = nums[:4]
    save_json(USERS_FILE, USERS)
    
    markup = InlineKeyboardMarkup(row_width=1)
    for n in nums[:4]:
        markup.add(InlineKeyboardButton(f"📋 +{n}", copy_text=telebot.types.CopyTextButton(text=f"+{n}")))
    
    bot.edit_message_text(
        f"✅ تم اختيار الدولة: {COUNTRIES[cid]['name']}\n\n"
        f"الأرقام المتاحة لك:\n(اضغط لنسخ الرقم)\n\n"
        f"⏳ في انتظار وصول الكود...",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "📊 إحصائياتي")
def stats(msg):
    user_id = str(msg.from_user.id)
    u = USERS.get(user_id, {})
    txt = (
        f"👤 إحصائياتك:\n\n"
        f"📅 تاريخ الانضمام: {u.get('join_date', 'N/A')}\n"
        f"📊 عدد الأكواد: {u.get('activations', 0)}\n"
        f"💰 رصيدك: ${u.get('balance', 0.0):.3f}"
    )
    bot.reply_to(msg, txt)

@bot.message_handler(func=lambda m: m.text == "💰 رصيدي")
def balance(msg):
    user_id = str(msg.from_user.id)
    u = USERS.get(user_id, {})
    bot.reply_to(msg, f"💰 رصيدك الحالي: ${u.get('balance', 0.0):.3f}")

@bot.message_handler(func=lambda m: m.text == "💸 سحب الرصيد")
def withdraw(msg):
    user_id = str(msg.from_user.id)
    u = USERS.get(user_id, {})
    bal = u.get('balance', 0.0)
    if bal < 1.0:
        bot.reply_to(msg, "❌ الحد الأدنى للسحب هو $1.0")
        return
    
    req_id = str(uuid.uuid4())[:8]
    WITHDRAWALS.append({
        "id": req_id,
        "user_id": user_id,
        "amount": bal,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "pending"
    })
    save_json(REQUESTS_FILE, WITHDRAWALS)
    
    bot.reply_to(msg, f"✅ تم إرسال طلب السحب!\n💵 المبلغ: ${bal:.3f}\n🆔 الطلب: {req_id}")
    
    for admin in ADMINS:
        try:
            bot.send_message(admin, f"💸 طلب سحب جديد!\n👤 المستخدم: `{user_id}`\n💵 المبلغ: ${bal:.3f}")
        except:
            pass
            # ================== لوحة الإدارة ==================
@bot.message_handler(func=lambda m: m.text == "⚙️ لوحة الإدارة" and is_admin(m.from_user.id))
def admin_panel(msg):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🌍 إضافة أرقام", callback_data="admin_add_country"),
        InlineKeyboardButton("👥 قائمة الدول", callback_data="admin_list_countries"),
        InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
        InlineKeyboardButton("📢 تعيين جروب OTP", callback_data="admin_set_group"),
        InlineKeyboardButton("💸 طلبات السحب", callback_data="admin_withdrawals")
    )
    bot.send_message(msg.chat.id, "⚙️ لوحة الإدارة", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callbacks(call):
    if not is_admin(call.from_user.id):
        return
    
    if call.data == "admin_add_country":
        bot.send_message(call.message.chat.id, "📄 أرسل ملف الأرقام (txt). كل سطر رقم.")
        user_states[call.from_user.id] = {"action": "add_numbers"}
    
    elif call.data == "admin_list_countries":
        txt = "🌍 قائمة الدول:\n"
        for cid, info in COUNTRIES.items():
            txt += f"• {info.get('flag','🌍')} {info['name']} (+{info['code']}) - {info.get('count', 0)} رقم\n"
        bot.send_message(call.message.chat.id, txt or "❌ لا توجد دول مضافة.")
    
    elif call.data == "admin_stats":
        bot.send_message(call.message.chat.id, f"👥 المستخدمين: {len(USERS)}\n🌍 الدول: {len(COUNTRIES)}")
    
    elif call.data == "admin_set_group":
        bot.send_message(call.message.chat.id, "أرسل ID الجروب:")
        user_states[call.from_user.id] = {"action": "set_otp_group"}
    
    elif call.data == "admin_withdrawals":
        txt = "💸 طلبات السحب:\n"
        for w in WITHDRAWALS:
            if w['status'] == 'pending':
                txt += f"🆔 `{w['id']}` | 👤 `{w['user_id']}` | 💵 ${w['amount']:.3f}\n"
        bot.send_message(call.message.chat.id, txt or "✅ لا توجد طلبات معلقة.")

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
    save_json(COUNTRY_FILE, COUNTRIES)
    del user_states[user_id]
    
    bot.reply_to(msg, f"✅ تم إضافة {len(lines)} رقم لدولة {name} {flag} (+{code})")

# ================== دالة مراقبة ThirdWave ==================
last_seen_key = ""

def send_otp_to_users(number, sms_text, sender):
    global last_seen_key
    otp = extract_otp(sms_text)
    service, eid = detect_service(sms_text, sender)
    country, flag = detect_country(number)
    
    sent = 0
    for uid, data in USERS.items():
        if not data.get("selected_numbers"):
            continue
        
        match = False
        for n in data["selected_numbers"]:
            n_clean = clean_number(n)
            if n_clean == clean_number(number) or clean_number(number).endswith(n_clean):
                match = True
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
                USERS[uid]["balance"] = USERS[uid].get("balance", 0.0) + 0.002
                sent += 1
            except Exception as e:
                print(f"Send error to {uid}: {e}")
    
    if sent > 0:
        save_json(USERS_FILE, USERS)
        print(f"✅ تم إرسال الكود لـ {sent} مستخدم: +{number} | OTP: {otp}")
    
    if OTP_GROUP:
        try:
            bot.send_message(OTP_GROUP, f"🔔 كود جديد\n📞 +{number}\n🔑 {otp}\n📨 {sender}")
        except:
            pass

def thirdwave_loop():
    global last_seen_key
    api_key = SETTINGS["ThirdWave"]["api_key"]
    api_url = SETTINGS["ThirdWave"]["api_url"]
    
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
            
            time.sleep(SETTINGS["ThirdWave"].get("check_interval", 5))
        except Exception as e:
            print(f"❌ ThirdWave Error: {e}")
            time.sleep(10)

# ================== معالجة الحالات النصية ==================
@bot.message_handler(func=lambda m: m.from_user.id in user_states and m.content_type == 'text')
def handle_states(msg):
    user_id = msg.from_user.id
    state = user_states.get(user_id, {})
    action = state.get("action")
    
    if action == "set_otp_group":
        try:
            gid = int(msg.text.strip())
            global OTP_GROUP
            OTP_GROUP = gid
            save_json(OTP_GROUP_FILE, {"group_id": gid})
            del user_states[user_id]
            bot.reply_to(msg, f"✅ تم تعيين جروب OTP: `{gid}`")
        except:
            bot.reply_to(msg, "❌ ID غير صحيح")

# ================== التشغيل ==================
if __name__ == "__main__":
    print("🚀 بدء البوت...")
    thread = Thread(target=thirdwave_loop, daemon=True)
    thread.start()
    print("✅ ThirdWave Loop started!")
    bot.infinity_polling()
    