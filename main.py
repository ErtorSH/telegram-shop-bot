from telebot import TeleBot
import config
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
import sqlite3
import re
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_healthcheck():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), PingHandler)
    server.serve_forever()




bot = TeleBot(config.TOKEN)


DB_NAME = "shop.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    postal_code TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT,
                    photo_id TEXT,
                    stock INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    receipt_photo_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
    finally:
        conn.close()


def add_product(name, price, description="", stock=0):
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO products (name, price, description, stock) VALUES (?, ?, ?, ?)",
                (name, price, description, stock)
            )
            return cur.lastrowid
    finally:
        conn.close()


def delete_product(product_id):
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.execute("DELETE FROM product_photos WHERE product_id = ?", (product_id,))
    finally:
        conn.close()


def set_stock(product_id, stock):
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute("UPDATE products SET stock = ? WHERE id = ?", (stock, product_id))
    finally:
        conn.close()

def get_products():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    finally:
        conn.close()


def add_photo(product_id, file_id):
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute(
                "INSERT INTO product_photos (product_id, file_id) VALUES (?, ?)",
                (product_id, file_id)
            )
    finally:
        conn.close()


def get_photos(product_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT file_id FROM product_photos WHERE product_id = ? ORDER BY id",
            (product_id,)
        ).fetchall()
    finally:
        conn.close()


def get_user(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    try:
        return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    finally:
        conn.close()


def save_user(telegram_id, first_name, last_name, address, postal_code, phone):
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (telegram_id, first_name, last_name, address, postal_code, phone) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (telegram_id, first_name, last_name, address, postal_code, phone)
            )
    finally:
        conn.close()


init_db()

if not get_products():
    add_product("عینک آفتابی Aviator", 2450000, "فریم طلایی، لنز ضد UV", 10)
    add_product("عینک طبی Classic", 1800000, "فریم مشکی مات، سبک", 5)
    add_product("عینک آفتابی Wayfarer", 2100000, "فریم مشکی براق، پلاریزه", 8)


btn1 = "ثبت نام 👤"
btn2 = "لیست محصولات 🕶"
btn3 = "ثبت سفارش🛍"
btn4 = "پیگیری سفارش🛒"
btn5 = "خرید های من🛒"
btn6 = "پنل ادمین📩"
btn7 = "ارتباط با سازنده👨‍💻"

main_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
main_kb.add(
    KeyboardButton(btn1),
    KeyboardButton(btn2),
    KeyboardButton(btn3),
    KeyboardButton(btn4),
    KeyboardButton(btn5),
    KeyboardButton(btn6),
    KeyboardButton(btn7)
)

phone_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
phone_kb.add(KeyboardButton("ارسال شماره📱", request_contact=True))


DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
POSTAL_RE = re.compile(r"^(?!(\d)\1{3})[13-9]{4}[1346-9][013-9]{5}$")

INFO_TEXT = """برای ثبت نام اطلاعات زیر را در یک پیام و با ویرگول جدا کنید:
نام، نام خانوادگی، آدرس دقیق، کد پستی (۱۰ رقم)

مثال:
علی،محمدی،کرج حصار خط چهار،3148616313"""


def parse_info(text):
    parts = [p.strip() for p in re.split(r"[،,]", text) if p.strip()]
    if len(parts) < 4:
        return None, "اطلاعات ناقصه. نام، نام خانوادگی، آدرس و کد پستی رو با ویرگول جدا کن و دوباره بفرست:"

    first, last = parts[0], parts[1]
    postal = parts[-1].translate(DIGITS).replace(" ", "")
    address = "، ".join(parts[2:-1])

    if not POSTAL_RE.match(postal):
        return None, "کد پستی معتبر نیست. باید ۱۰ رقم و درست باشه. اطلاعات رو دوباره بفرست:"

    return (first, last, address, postal), None


@bot.message_handler(commands=['start'])
def welcome(message):
    first = message.from_user.first_name or ""
    last = message.from_user.last_name or ""
    name = f"{first} {last}".strip()
    bot.send_message(message.chat.id,
                     f"سلام {name} عزیز به فروشگاه ما خوش اومدی \n ممنون که مارا انتخاب کردید🌹😊 از گزینه های زیر انتخاب کنید👇",
                     reply_markup=main_kb)


@bot.message_handler(func=lambda m: m.text == btn1)
def register(message):
    if get_user(message.from_user.id):
        bot.send_message(message.chat.id, "شما قبلاً ثبت نام کرده‌اید ✅")
        return

    msg = bot.send_message(message.chat.id, INFO_TEXT)
    bot.register_next_step_handler(msg, get_info)


def get_info(message):
    if message.text and message.text.startswith("/"):
        bot.send_message(message.chat.id, "ثبت نام لغو شد.", reply_markup=main_kb)
        return

    if not message.text:
        msg = bot.send_message(message.chat.id, "لطفاً اطلاعات رو به‌صورت متن بفرست:")
        bot.register_next_step_handler(msg, get_info)
        return

    data, error = parse_info(message.text)
    if error:
        msg = bot.send_message(message.chat.id, error)
        bot.register_next_step_handler(msg, get_info)
        return

    first, last, address, postal = data
    msg = bot.send_message(
        message.chat.id,
        "اطلاعاتت دریافت شد✔\nبرای تکمیل ثبت نام شماره‌ات رو با دکمه‌ی زیر بفرست:",
        reply_markup=phone_kb
    )
    bot.register_next_step_handler(msg, get_phone, first, last, address, postal)


def get_phone(message, first, last, address, postal):
    if message.text and message.text.startswith("/"):
        bot.send_message(message.chat.id, "ثبت نام لغو شد.", reply_markup=main_kb)
        return

    if message.contact is None or message.contact.user_id != message.from_user.id:
        msg = bot.send_message(
            message.chat.id,
            "لطفاً با دکمه‌ی «ارسال شماره» شماره‌ی خودت رو بفرست:",
            reply_markup=phone_kb
        )
        bot.register_next_step_handler(msg, get_phone, first, last, address, postal)
        return

    save_user(message.from_user.id, first, last, address, postal, message.contact.phone_number)
    bot.send_message(message.chat.id, "ثبت نام شما انجام شد✔", reply_markup=main_kb)


def product_view(index):
    products = get_products()
    index = index % len(products)
    p = products[index]

    text = (f"🕶 {p['name']}\n\n"
            f"{p['description']}\n\n"
            f"💰 قیمت: {p['price']:,} تومان\n"
            f"📦 موجودی: {p['stock']} عدد\n\n"
            f"({index + 1} از {len(products)})")

    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("◀ بعدی", callback_data=f"prod_{index + 1}"),
        InlineKeyboardButton(f"{index + 1}/{len(products)}", callback_data="noop"),
        InlineKeyboardButton("قبلی ▶", callback_data=f"prod_{index - 1}"),
    )
    kb.add(InlineKeyboardButton("📷 مشاهده تصاویر", callback_data=f"photos_{p['id']}"))
    return text, kb


@bot.message_handler(func=lambda m: m.text == btn2)
def show_products(message):
    if not get_products():
        bot.send_message(message.chat.id, "فعلاً محصولی ثبت نشده.")
        return
    text, kb = product_view(0)
    bot.send_message(message.chat.id, text, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("prod_"))
def change_product(call):
    index = int(call.data.split("_")[1])
    text, kb = product_view(index)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception:
        pass
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "noop")
def noop(call):
    bot.answer_callback_query(call.id)


@bot.message_handler(commands=['id'])
def my_id(message):
    bot.reply_to(message, f"آیدی تو: {message.from_user.id}")


@bot.message_handler(content_types=['photo'])
def save_product_photo(message):
    if message.from_user.id != config.ADMIN_ID:
        return

    caption = (message.caption or "").strip()
    if not caption.isdigit():
        bot.reply_to(message, "شماره‌ی محصول رو تو کپشن عکس بنویس. مثلاً: 1")
        return

    product_id = int(caption)
    if product_id not in [p["id"] for p in get_products()]:
        bot.reply_to(message, "محصولی با این شماره وجود نداره.")
        return

    add_photo(product_id, message.photo[-1].file_id)
    bot.reply_to(message, f"عکس برای محصول {product_id} ذخیره شد ✅")


@bot.callback_query_handler(func=lambda c: c.data.startswith("photos_"))
def send_photos(call):
    product_id = int(call.data.split("_")[1])
    photos = get_photos(product_id)

    if not photos:
        bot.answer_callback_query(call.id, "برای این محصول هنوز تصویری ثبت نشده.", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    if len(photos) == 1:
        bot.send_photo(chat_id, photos[0]["file_id"])
    else:
        media = [InputMediaPhoto(p["file_id"]) for p in photos[:10]]
        bot.send_media_group(chat_id, media)

def is_admin(user_id):
    return user_id == config.ADMIN_ID


def admin_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ افزودن محصول", callback_data="adm_add"),
        InlineKeyboardButton("📦 تغییر موجودی", callback_data="adm_stock"),
        InlineKeyboardButton("🗑 حذف محصول", callback_data="adm_del"),
    )
    return kb


def product_buttons(prefix):
    kb = InlineKeyboardMarkup(row_width=1)
    for p in get_products():
        kb.add(InlineKeyboardButton(f"{p['id']} - {p['name']}", callback_data=f"{prefix}_{p['id']}"))
    return kb


ADD_TEXT = """اطلاعات محصول رو در یک پیام و با ویرگول جدا کن:
نام، قیمت (تومان)، موجودی، توضیحات

مثال:
عینک آفتابی Aviator،2450000،10،فریم طلایی، لنز ضد UV

(قیمت و موجودی رو بدون کاما بنویس)"""


@bot.message_handler(func=lambda m: m.text == btn6)
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "این بخش مخصوص ادمینه.")
        return
    bot.send_message(message.chat.id, "پنل مدیریت 👨‍💼\nیکی رو انتخاب کن:", reply_markup=admin_menu())


@bot.message_handler(func=lambda m: m.text == btn7)
def creator(message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("ارتباط",url="https://t.me/Amir_Ertor")
    )
    bot.send_message(message.chat.id,"برای ارتباط با سازنده روی دکمه زیر کلیک کنید:",reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "adm_add")
def adm_add(call):
    bot.answer_callback_query(call.id)
    if not is_admin(call.from_user.id):
        return
    msg = bot.send_message(call.message.chat.id, ADD_TEXT)
    bot.register_next_step_handler(msg, adm_add_get)


def adm_add_get(message):
    if not message.text or message.text.startswith("/"):
        bot.send_message(message.chat.id, "افزودن محصول لغو شد.")
        return

    parts = [p.strip() for p in re.split(r"[،,]", message.text) if p.strip()]
    if len(parts) < 3:
        msg = bot.send_message(message.chat.id, "اطلاعات ناقصه. نام، قیمت و موجودی لازمه. دوباره بفرست:")
        bot.register_next_step_handler(msg, adm_add_get)
        return

    name = parts[0]
    price = parts[1].translate(DIGITS)
    stock = parts[2].translate(DIGITS)
    if not (price.isdigit() and stock.isdigit()):
        msg = bot.send_message(message.chat.id, "قیمت و موجودی باید فقط عدد باشن (بدون کاما). دوباره بفرست:")
        bot.register_next_step_handler(msg, adm_add_get)
        return

    description = "، ".join(parts[3:])
    product_id = add_product(name, int(price), description, int(stock))
    bot.send_message(
        message.chat.id,
        f"محصول ثبت شد ✅\nشماره‌ی محصول: {product_id}\n"
        f"برای افزودن عکس، عکس‌ها رو یکی‌یکی با کپشن {product_id} بفرست."
    )


@bot.callback_query_handler(func=lambda c: c.data in ("adm_stock", "adm_del"))
def adm_choose(call):
    bot.answer_callback_query(call.id)
    if not is_admin(call.from_user.id):
        return
    if not get_products():
        bot.send_message(call.message.chat.id, "محصولی ثبت نشده.")
        return
    prefix = "admstock" if call.data == "adm_stock" else "admdel"
    bot.send_message(call.message.chat.id, "کدوم محصول؟", reply_markup=product_buttons(prefix))


@bot.callback_query_handler(func=lambda c: c.data.startswith("admstock_"))
def adm_stock_pick(call):
    bot.answer_callback_query(call.id)
    if not is_admin(call.from_user.id):
        return
    product_id = int(call.data.split("_")[1])
    msg = bot.send_message(call.message.chat.id, "موجودی جدید رو بنویس (فقط عدد):")
    bot.register_next_step_handler(msg, adm_stock_set, product_id)


def adm_stock_set(message, product_id):
    if message.text and message.text.startswith("/"):
        bot.send_message(message.chat.id, "لغو شد.")
        return

    text = (message.text or "").translate(DIGITS).strip()
    if not text.isdigit():
        msg = bot.send_message(message.chat.id, "فقط عدد بفرست:")
        bot.register_next_step_handler(msg, adm_stock_set, product_id)
        return

    set_stock(product_id, int(text))
    bot.send_message(message.chat.id, "موجودی بروز شد ✅")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admdel_"))
def adm_del_ask(call):
    bot.answer_callback_query(call.id)
    if not is_admin(call.from_user.id):
        return
    product_id = int(call.data.split("_")[1])
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("بله، حذف کن", callback_data=f"admdelyes_{product_id}"),
        InlineKeyboardButton("انصراف", callback_data="adm_cancel"),
    )
    bot.edit_message_text("مطمئنی حذف بشه؟", call.message.chat.id, call.message.message_id, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("admdelyes_"))
def adm_del_do(call):
    bot.answer_callback_query(call.id)
    if not is_admin(call.from_user.id):
        return
    delete_product(int(call.data.split("_")[1]))
    bot.edit_message_text("محصول حذف شد ✅", call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data == "adm_cancel")
def adm_cancel(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("لغو شد.", call.message.chat.id, call.message.message_id)

bot.infinity_polling()