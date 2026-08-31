"""
================================================================================
🍴 PREMIUM RESTAURANT & ORDER BOT
================================================================================
Developed by: Amresh Kumar
Technology: Python, Telegram Bot API, Google Gemini AI, Google Sheets
Description: A professional ordering solution with GPS support and AI chat.
================================================================================
"""

import sys
import telebot
import requests
import csv
import os
import random
import datetime
from telebot import types
import base64
from gtts import gTTS
import io
from urllib.parse import quote
import qrcode
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

# ------------------------------------------------------------------------------
# 🔹 CORE CONFIGURATION
# ------------------------------------------------------------------------------
# Fetching keys from Environment Variables for Security
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8819535449:AAHhm2S9dG1KpFbz_olw4xMr2Mlt3LpPSmM')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', 'AIzaSyCNL15MhyDUqVA9cQMO3S1U7IV_ZLTHc38')
SHEET_URL = os.environ.get('GOOGLE_SHEET_URL', 'https://script.google.com/macros/s/AKfycbwdRqnwnDwhSXnGOc7fXgrB96Iiq6JumRfrxwZ2GCuRoqWp6V7OHBe3zpm6iUBU9RZLHg/exec')
UPI_ID = os.environ.get('UPI_ID', '8797114376@ibl')  # Replace with your actual UPI ID (e.g., phone@paytm)
UPI_NAME = os.environ.get('UPI_NAME', 'Amresh Kumar')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 6886477028))  # Replace with your Telegram ID

bot = telebot.TeleBot(API_TOKEN)
DATA_FILE = 'data.csv'
ORDERS_FILE = 'orders.csv'

# Temporary storage for order processing
user_data = {}
user_carts = {} # Storage for shopping cart: {chat_id: {item_id: {name,price,qty}}}
order_user_map = {} # Maps order_id -> chat_id for live status push notifications

# Order status progression pipeline
ORDER_STATUSES = [
    ("⏳", "Order Placed",        "Your order has been received and is waiting for confirmation."),
    ("✅", "Accepted & Preparing","Great news! Your order is accepted and being prepared fresh for you! 👨‍🍳"),
    ("🍳", "Cooking in Progress", "Our chef is cooking your delicious meal right now! 🔥"),
    ("🛵", "Out for Delivery",    "Your order is on the way! Our delivery partner is heading to you! 🚀"),
    ("🎉", "Delivered",           "Your order has been delivered! Enjoy your meal! 😋 Rate us below."),
    ("❌", "Order Rejected",      "Sorry, we could not process your order. Please contact us for support."),
]

STATUS_LABELS = {s[1]: (s[0], s[2]) for s in ORDER_STATUSES}



class Order:
    """Class to structure order data during the collection process."""
    def __init__(self):
        self.order_id = int(datetime.datetime.now().timestamp()) % 10000
        self.name = None
        self.address = None
        self.location_link = None
        self.phone = None
        self.product = None
        self.payment_method = None
        self.total_amount = 0
        self.is_manual = False

def generate_dynamic_upi_qr(amount, order_id=None):
    """Generates a dynamic UPI QR code in memory containing payee, exact amount, and order note."""
    note = f"Order #{order_id}" if order_id else "Food Order"
    upi_payload = f"upi://pay?pa={UPI_ID}&pn={quote(UPI_NAME)}&am={float(amount):.2f}&cu=INR&tn={quote(note)}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(upi_payload)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#0F2027", back_color="white")
    
    buf = io.BytesIO()
    buf.name = f"upi_order_{order_id}.png"
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf, upi_payload


def get_tracking_status_message(order_id, status):
    """Builds a visual order tracking message with progress indicator."""
    pipeline = ["Order Placed", "Accepted & Preparing", "Cooking in Progress", "Out for Delivery", "Delivered"]
    
    emoji, detail = STATUS_LABELS.get(status, ("🔄", "Processing your order..."))
    
    # Build progress bar
    progress_lines = []
    found = status in pipeline
    rejected = status == "Order Rejected"
    
    if rejected:
        return (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *ORDER #{order_id} — TRACKING*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ *Order Rejected*\n\n"
            f"_{detail}_\n\n"
            "📞 Please contact us for more info."
        )
    
    for i, step in enumerate(pipeline):
        step_emoji, _ = STATUS_LABELS.get(step, ("◻️", ""))
        if step == status:
            progress_lines.append(f"👉 {step_emoji} *{step}* ← You are here")
        elif pipeline.index(step) < pipeline.index(status) if status in pipeline else False:
            progress_lines.append(f"   ✅ ~~{step}~~")
        else:
            progress_lines.append(f"   ◻️ {step}")

    progress_text = "\n".join(progress_lines)
    
    msg = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *ORDER #{order_id} — LIVE TRACKING*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{progress_text}\n\n"
        "─────────────────────\n"
        f"{emoji} *{status}*\n"
        f"_{detail}_\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    return msg

def get_admin_order_action_keyboard(order_id):
    """Inline keyboard for admin to update order status with one tap."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("✅ Accept & Prepare", callback_data=f"ostatus_{order_id}_Accepted & Preparing"),
        types.InlineKeyboardButton("❌ Reject Order",     callback_data=f"ostatus_{order_id}_Order Rejected"),
    )
    markup.row(
        types.InlineKeyboardButton("🍳 Cooking Now",       callback_data=f"ostatus_{order_id}_Cooking in Progress"),
        types.InlineKeyboardButton("🛵 Out for Delivery",  callback_data=f"ostatus_{order_id}_Out for Delivery"),
    )
    markup.row(
        types.InlineKeyboardButton("🎉 Mark Delivered",    callback_data=f"ostatus_{order_id}_Delivered"),
    )
    return markup


# ------------------------------------------------------------------------------
# 🔹 DATA & CLOUD INTEGRATION
# ------------------------------------------------------------------------------


def load_data():
    """Loads restaurant data from local CSV file. Returns empty list if error."""
    data = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row: 
                        cleaned_row = {}
                        for k, v in row.items():
                            if k:
                                key = k.strip()
                                val = v.strip() if v else ""
                                cleaned_row[key] = val
                        data.append(cleaned_row)
            return data
        except Exception as e:
            print(f"Error reading CSV: {e}")
    return []

def log_to_google_sheet(order_id, date, order_obj):
    """Synchronizes order details with Google Sheets for real-time tracking."""
    try:
        final_address = order_obj.location_link if order_obj.location_link else order_obj.address
        params = {
            "order_id": order_id,
            "date": date,
            "name": order_obj.name,
            "address": final_address,
            "phone": order_obj.phone,
            "product": order_obj.product,
            "price": order_obj.total_amount
        }
        requests.get(SHEET_URL, params=params, timeout=5)
    except Exception as e:
        print(f"Cloud Sync Error: {e}")

def log_rating_to_google_sheet(order_id, rating):
    """Logs customer rating to Google Sheets."""
    try:
        params = {
            "order_id": order_id,
            "rating": rating,
            "type": "feedback"
        }
        requests.get(SHEET_URL, params=params, timeout=5)
    except:
        pass

def log_order_to_local(order_id, user_id, name, product, price):
    """Logs the order locally to a CSV file for status tracking."""
    file_exists = os.path.exists(ORDERS_FILE) and os.path.getsize(ORDERS_FILE) > 0
    try:
        with open(ORDERS_FILE, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['Order_ID', 'User_ID', 'Name', 'Product', 'Price', 'Status'])
            # Order_ID, User_ID, Name, Product, Price, Status
            writer.writerow([order_id, user_id, name, product, price, 'Order Placed'])
    except Exception as e:
        print(f"Local Log Error: {e}")

def get_order_row(order_id):
    """Returns the full CSV row for an order as a dict."""
    if not os.path.exists(ORDERS_FILE):
        return None
    try:
        with open(ORDERS_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('Order_ID') == str(order_id):
                    return row
    except Exception as e:
        print(f"Read Order Error: {e}")
    return None

def get_order_status(order_id):
    """Retrieves the status of an order from the local CSV."""
    row = get_order_row(order_id)
    return row.get('Status') if row else None

def update_order_status(order_id, new_status):
    """Updates the status of an order in the local CSV."""
    if not os.path.exists(ORDERS_FILE):
        return False
    rows = []
    updated = False
    try:
        with open(ORDERS_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            header = next(reader, None)
            if header:
                rows.append(header)
            for row in reader:
                if row and row[0] == str(order_id):
                    row[5] = new_status   # Status is column index 5
                    updated = True
                rows.append(row)

        if updated:
            with open(ORDERS_FILE, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerows(rows)
            return True
    except Exception as e:
        print(f"Update Status Error: {e}")
    return False



# ------------------------------------------------------------------------------
# 🔹 AI ASSISTANT (GEMINI AI)
# ------------------------------------------------------------------------------

def get_ai_response(user_text):
    """Generates intelligent responses using Google Gemini 1.5 Flash."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GOOGLE_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"You are a professional assistant for Amresh Kumar's Restaurant. The owner is Amresh Kumar. Contact: +91 8797114376. Instagram: @amresh_kumar.__. WhatsApp: +91 8797114376. Answer politely in English. User says: {user_text}"}]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Our AI assistant is temporarily unavailable. Please try again later."

def get_voice_response(audio_data):
    """Processes voice input using Gemini 1.5 Flash."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    # Encode audio to base64
    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
    
    payload = {
        "contents": [{
            "parts": [
                {"text": "Listen to this audio from a customer. You are a helpful assistant for Amresh's Restaurant. Reply briefly and politely in English (or Hindi if spoken)."},
                {
                    "inline_data": {
                        "mime_type": "audio/ogg",
                        "data": audio_b64
                    }
                }
            ]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Voice AI Error: {e}")
        return "Sorry, I couldn't understand that audio."

# ------------------------------------------------------------------------------
# 🔹 DYNAMIC KEYBOARDS
# ------------------------------------------------------------------------------

def get_main_keyboard(user_id=None):
    """Returns the primary navigation menu."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🍴 View Menu', '🛒 Order Food')
    markup.add('🛒 My Cart', '📱 Social Media Hub')
    markup.add('🎲 Surprise Me', '❓ Help / AI Chat')
    markup.add('➕ More Options')
    return markup

def get_more_keyboard(is_admin=False):
    """Returns an extended menu for additional features."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('📦 Track Order', '📞 Contact Owner')
    if is_admin:
        markup.add('🛠️ Admin Panel')
    markup.add('🔙 Main Menu')
    return markup

def get_social_keyboard():
    """Returns interactive links for social media engagement."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_wa = types.InlineKeyboardButton("💬 WhatsApp", url="https://wa.me/918797114376")
    btn_ig = types.InlineKeyboardButton("📸 Instagram", url="https://www.instagram.com/amresh_kumar.__?igsh=MW95aWs1cDZ1aXpjdg==")
    btn_li = types.InlineKeyboardButton("🔗 LinkedIn", url="https://www.linkedin.com/in/amresh-kumar-8451162a6/")
    btn_map = types.InlineKeyboardButton("📍 Our Location", url="https://www.google.com/maps/search/?api=1&query=Vinayaka+Missions+Kirupananda+Variyar+Medical+College")
    markup.add(btn_wa, btn_ig, btn_li, btn_map)
    return markup

def get_location_keyboard():
    """Offers GPS location sharing or manual address entry."""
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
    btn_location = types.KeyboardButton('📍 Share My Current Location', request_location=True)
    btn_skip = types.KeyboardButton('Type Manually')
    markup.add(btn_location, btn_skip)
    return markup

def get_rating_keyboard(order_id):
    """Returns a star-based rating keyboard."""
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(f"{i} ⭐", callback_data=f"rate_{order_id}_{i}") for i in range(1, 6)]
    markup.add(*btns)
    return markup

def get_payment_keyboard():
    """Returns payment method options."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    markup.add('💵 Cash on Delivery', '📲 Pay Online (UPI)')
    return markup

def get_admin_keyboard():
    """Returns admin control panel."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('📦 Active Orders', '📢 Broadcast Message', '📄 Download Data', '🔙 Main Menu')
    return markup

def get_category_keyboard():
    """Displays restaurant categories via inline buttons."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    categories = ['Indian', 'Italian', 'Chinese', 'Fast Food', 'Japanese']
    btns = [types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}") for cat in categories]
    markup.add(*btns)
    return markup

def get_item_keyboard(item_id):
    """Keyboard for each menu item to add to cart."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Add to Cart", callback_data=f"add_{item_id}"),
        types.InlineKeyboardButton("🛒 View Cart", callback_data="open_cart")
    )
    return markup

def get_cart_items(chat_id):
    """Retrieves or normalizes the shopping cart dictionary for a user."""
    cart = user_carts.get(chat_id, {})
    if isinstance(cart, list):
        new_cart = {}
        for it in cart:
            i_id = str(it.get('id', it.get('name', 'item')))
            if i_id not in new_cart:
                new_cart[i_id] = {'id': i_id, 'name': it.get('name', 'Item'), 'price': int(it.get('price', 0)), 'qty': 1}
            else:
                new_cart[i_id]['qty'] += 1
        user_carts[chat_id] = new_cart
        cart = new_cart
    return cart

def format_cart_message(chat_id):
    """Formats a clean Markdown summary of the shopping cart."""
    cart = get_cart_items(chat_id)
    if not cart:
        return (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🛒 *YOUR SHOPPING CART IS EMPTY*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your cart currently has no items. 🍽️\n"
            "Explore our menu to add delicious dishes!"
        )
    
    summary = "━━━━━━━━━━━━━━━━━━━━━\n"
    summary += "🛒 *YOUR SHOPPING CART*\n"
    summary += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    total_price = 0
    total_qty = 0
    for i, (item_id, item) in enumerate(cart.items(), 1):
        price = int(item.get('price', 0))
        qty = int(item.get('qty', 1))
        item_total = price * qty
        total_price += item_total
        total_qty += qty
        summary += f"*{i}. {item.get('name')}*\n"
        summary += f"   ₹{price} × {qty} = *₹{item_total}*\n\n"
    
    summary += "─────────────────────\n"
    summary += f"📦 *Total Items:* {total_qty} pcs\n"
    summary += f"💰 *Grand Total:* *₹{total_price}*\n"
    summary += "━━━━━━━━━━━━━━━━━━━━━\n"
    summary += "⚡ *Use the buttons below to change quantity or checkout:*"
    return summary

def get_interactive_cart_keyboard(chat_id):
    """Generates an interactive inline keyboard with (+ / - / Remove / Checkout) for the cart."""
    cart = get_cart_items(chat_id)
    markup = types.InlineKeyboardMarkup(row_width=4)
    
    if not cart:
        markup.add(types.InlineKeyboardButton("🍴 Browse Menu", callback_data="view_menu_cats"))
        return markup
        
    total_price = 0
    for item_id, item in cart.items():
        qty = int(item.get('qty', 1))
        name = item.get('name', 'Item')
        short_name = (name[:10] + '..') if len(name) > 10 else name
        total_price += int(item.get('price', 0)) * qty
        
        # Row with [-] [Qty] [+] [🗑️ Item]
        btn_dec = types.InlineKeyboardButton("➖", callback_data=f"cdec_{item_id}")
        btn_qty = types.InlineKeyboardButton(f"{qty}x", callback_data=f"cnoop_{item_id}")
        btn_inc = types.InlineKeyboardButton("➕", callback_data=f"cinc_{item_id}")
        btn_del = types.InlineKeyboardButton(f"🗑️ {short_name}", callback_data=f"cdel_{item_id}")
        markup.row(btn_dec, btn_qty, btn_inc, btn_del)
        
    # Actions
    markup.row(types.InlineKeyboardButton(f"🛍️ Proceed to Checkout • ₹{total_price}", callback_data="checkout"))
    markup.row(
        types.InlineKeyboardButton("🍴 Add More Items", callback_data="view_menu_cats"),
        types.InlineKeyboardButton("🗑️ Clear Entire Cart", callback_data="clear_cart")
    )
    return markup

# ------------------------------------------------------------------------------
# 🔹 ORDER & CART FLOW LOGIC
# ------------------------------------------------------------------------------

@bot.message_handler(func=lambda message: message.text in ['🛒 My Cart', '/cart'])
def show_cart(message):
    chat_id = message.chat.id
    bot.send_message(
        chat_id, 
        format_cart_message(chat_id), 
        parse_mode="Markdown", 
        reply_markup=get_interactive_cart_keyboard(chat_id)
    )

@bot.callback_query_handler(func=lambda call: call.data == 'open_cart')
def handle_open_cart(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id,
        format_cart_message(chat_id),
        parse_mode="Markdown",
        reply_markup=get_interactive_cart_keyboard(chat_id)
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_'))
def handle_add_to_cart(call):
    item_id = str(call.data.split('add_')[1])
    data = load_data()
    item = next((row for row in data if str(row.get('Restaurant_ID')) == item_id), None)
    
    if item:
        chat_id = call.message.chat.id
        cart = get_cart_items(chat_id)
        if item_id in cart:
            cart[item_id]['qty'] += 1
        else:
            cart[item_id] = {
                'id': item_id,
                'name': item.get('Restaurant_Name'),
                'price': int(item.get('Avg_Cost', 0)),
                'qty': 1
            }
        user_carts[chat_id] = cart
        total_items = sum(it.get('qty', 1) for it in cart.values())
        bot.answer_callback_query(call.id, f"✅ Added {item.get('Restaurant_Name')}! (Cart: {total_items} items)")
    else:
        bot.answer_callback_query(call.id, "⚠️ Item not found.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cinc_'))
def handle_cart_increment(call):
    chat_id = call.message.chat.id
    item_id = str(call.data.split('cinc_')[1])
    cart = get_cart_items(chat_id)
    if item_id in cart:
        cart[item_id]['qty'] += 1
        user_carts[chat_id] = cart
        bot.answer_callback_query(call.id, f"➕ {cart[item_id]['name']} (Qty: {cart[item_id]['qty']})")
        try:
            bot.edit_message_text(
                format_cart_message(chat_id),
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_interactive_cart_keyboard(chat_id)
            )
        except Exception:
            pass
    else:
        bot.answer_callback_query(call.id, "Item not in cart.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cdec_'))
def handle_cart_decrement(call):
    chat_id = call.message.chat.id
    item_id = str(call.data.split('cdec_')[1])
    cart = get_cart_items(chat_id)
    if item_id in cart:
        if cart[item_id]['qty'] > 1:
            cart[item_id]['qty'] -= 1
            bot.answer_callback_query(call.id, f"➖ {cart[item_id]['name']} (Qty: {cart[item_id]['qty']})")
        else:
            del cart[item_id]
            bot.answer_callback_query(call.id, "🗑️ Item removed from cart.")
        user_carts[chat_id] = cart
        try:
            bot.edit_message_text(
                format_cart_message(chat_id),
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_interactive_cart_keyboard(chat_id)
            )
        except Exception:
            pass
    else:
        bot.answer_callback_query(call.id, "Item not in cart.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cdel_'))
def handle_cart_delete(call):
    chat_id = call.message.chat.id
    item_id = str(call.data.split('cdel_')[1])
    cart = get_cart_items(chat_id)
    if item_id in cart:
        name = cart[item_id]['name']
        del cart[item_id]
        user_carts[chat_id] = cart
        bot.answer_callback_query(call.id, f"🗑️ Removed {name} from cart.")
        try:
            bot.edit_message_text(
                format_cart_message(chat_id),
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_interactive_cart_keyboard(chat_id)
            )
        except Exception:
            pass
    else:
        bot.answer_callback_query(call.id, "Item not in cart.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cnoop_'))
def handle_cart_noop(call):
    item_id = str(call.data.split('cnoop_')[1])
    cart = get_cart_items(call.message.chat.id)
    qty = cart.get(item_id, {}).get('qty', 1)
    bot.answer_callback_query(call.id, f"Current Quantity: {qty}")

@bot.callback_query_handler(func=lambda call: call.data == 'view_menu_cats')
def handle_view_menu_cats(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "🍱 *Choose a Category:*", parse_mode="Markdown", reply_markup=get_category_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == 'clear_cart')
def handle_clear_cart(call):
    chat_id = call.message.chat.id
    user_carts[chat_id] = {}
    bot.answer_callback_query(call.id, "🗑️ Cart cleared.")
    try:
        bot.edit_message_text(
            format_cart_message(chat_id),
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_interactive_cart_keyboard(chat_id)
        )
    except Exception:
        bot.send_message(chat_id, "🛒 Your cart has been cleared.", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == 'checkout')
def handle_checkout_callback(call):
    bot.answer_callback_query(call.id)
    start_order(call.message)

@bot.message_handler(func=lambda message: message.text == '🛒 Order Food' or message.text == '/order')
def start_manual_order(message):
    chat_id = message.chat.id
    cart = get_cart_items(chat_id)
    if cart:
        # If user already has items in cart, proceed with cart checkout
        start_order(message)
    else:
        # Prompt user to browse menu or manual order
        user_data[chat_id] = Order()
        user_data[chat_id].is_manual = True
        msg = bot.send_message(
            chat_id, 
            "🛒 *Place an Order*\n\nYour cart is empty, but you can type your order manually!\n\nPlease enter your *Full Name*:", 
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_name_step)

def start_order(message):
    chat_id = message.chat.id
    cart = get_cart_items(chat_id)
    
    if not cart:
        bot.send_message(chat_id, "⚠️ Your cart is empty! Add items from the menu first.", reply_markup=get_main_keyboard())
        return

    user_data[chat_id] = Order()
    user_data[chat_id].is_manual = False
    
    # Prepare cart summary
    item_summaries = []
    total = 0
    for item in cart.values():
        qty = int(item.get('qty', 1))
        price = int(item.get('price', 0))
        item_summaries.append(f"{item.get('name')} x{qty}")
        total += price * qty
        
    user_data[chat_id].product = ", ".join(item_summaries)
    user_data[chat_id].total_amount = total

    msg = bot.send_message(
        chat_id, 
        f"🛒 *Cart Checkout*\n\n📦 *Items:* {user_data[chat_id].product}\n💰 *Total:* ₹{total}\n\n👤 Please enter your *Full Name*:", 
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, process_name_step)

def process_name_step(message):
    chat_id = message.chat.id
    user_data[chat_id].name = message.text
    msg = bot.send_message(chat_id, f"Hello {message.text}! Provide your delivery address by clicking below or typing manually:", 
                          reply_markup=get_location_keyboard(), parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_address_logic)

def process_address_logic(message):
    chat_id = message.chat.id
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        user_data[chat_id].location_link = f"https://www.google.com/maps?q={lat},{lon}"
        user_data[chat_id].address = "Location Shared via GPS"
        msg = bot.send_message(chat_id, "📍 Location received! Now, provide your *Mobile Number*:", 
                              reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_phone_step)
    elif message.text == 'Type Manually':
        msg = bot.send_message(chat_id, "Please type your full delivery address:", 
                              reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, process_manual_address_step)
    else:
        user_data[chat_id].address = message.text
        msg = bot.send_message(chat_id, "Now, provide your *Mobile Number*:", 
                              reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_phone_step)

def process_manual_address_step(message):
    chat_id = message.chat.id
    user_data[chat_id].address = message.text
    msg = bot.send_message(chat_id, "Great! What is your *Mobile Number*?")
    bot.register_next_step_handler(msg, process_phone_step)

def process_phone_step(message):
    chat_id = message.chat.id
    user_data[chat_id].phone = message.text
    
    if user_data[chat_id].is_manual:
        msg = bot.send_message(chat_id, "What would you like to order? (Food Name):")
        bot.register_next_step_handler(msg, process_product_step)
    else:
        # Items are already in cart
        msg = bot.send_message(chat_id, f"📦 Order Summary: *{user_data[chat_id].product}*\n💰 Total: *₹{user_data[chat_id].total_amount}*\n\n💳 *Select Payment Method:*", 
                               parse_mode="Markdown", reply_markup=get_payment_keyboard())
        bot.register_next_step_handler(msg, process_payment_logic)

def process_product_step(message):
    chat_id = message.chat.id
    user_data[chat_id].product = message.text
    msg = bot.send_message(chat_id, "Please enter the *Total Price* (e.g. 500):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_price_step)

def process_price_step(message):
    chat_id = message.chat.id
    try:
        price = int(message.text)
    except:
        price = 0
    
    user_data[chat_id].total_amount = price
    msg = bot.send_message(chat_id, f"📦 Manual Order: *{user_data[chat_id].product}*\n💰 Total: *₹{price}*\n\n💳 *Select Payment Method:*", 
                           parse_mode="Markdown", reply_markup=get_payment_keyboard())
    bot.register_next_step_handler(msg, process_payment_logic)

def process_payment_logic(message):
    chat_id = message.chat.id
    choice = message.text

    if 'UPI' in choice or 'Pay Online' in choice:
        user_data[chat_id].payment_method = 'Online'
        amount = user_data[chat_id].total_amount
        order_id = getattr(user_data[chat_id], 'order_id', int(datetime.datetime.now().timestamp()) % 10000)
        user_data[chat_id].order_id = order_id
        
        try:
            qr_buf, upi_url = generate_dynamic_upi_qr(amount, order_id)
            caption = (
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "📲 *DYNAMIC UPI PAYMENT QR*\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 *Order ID:* `#{order_id}`\n"
                f"💰 *Amount to Pay:* `₹{amount}`\n"
                f"👤 *Payee:* `{UPI_NAME}`\n"
                f"🔑 *UPI ID:* `{UPI_ID}`\n"
                "─────────────────────\n"
                "⚡ *Quick & Direct Payment:*\n"
                "1️⃣ Scan with *GPay / PhonePe / Paytm / BHIM*\n"
                "2️⃣ The exact amount *₹{amount}* & Order ID are pre-filled!\n"
                "3️⃣ After paying, tap *Confirm Payment* below.\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            )
            bot.send_photo(chat_id, qr_buf, caption=caption, parse_mode="Markdown")
        except Exception as e:
            print(f"Dynamic QR Error: {e}")
            bot.send_message(
                chat_id, 
                f"📲 *Pay Online (UPI)*\n\nUPI ID: `{UPI_ID}`\nAmount: *₹{amount}*\nOrder Note: `Order #{order_id}`",
                parse_mode="Markdown"
            )
        
        # Confirmation keyboard
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('✅ Confirm Payment', '💵 Switch to Cash on Delivery')
        msg = bot.send_message(chat_id, "👇 *Tap below after completing payment:*", parse_mode="Markdown", reply_markup=markup)
        bot.register_next_step_handler(msg, handle_payment_confirmation)
        
    else:
        user_data[chat_id].payment_method = 'COD'
        finalize_order(message)

def handle_payment_confirmation(message):
    chat_id = message.chat.id
    text = message.text or ""
    if 'Cash on Delivery' in text or 'COD' in text:
        user_data[chat_id].payment_method = 'COD'
    finalize_order(message)

def finalize_order(message):
    chat_id = message.chat.id
    
    order_id = getattr(user_data[chat_id], 'order_id', None) or (int(datetime.datetime.now().timestamp()) % 10000)
    date_str, time_str = datetime.datetime.now().strftime("%d-%m-%Y"), datetime.datetime.now().strftime("%I:%M %p")
    
    pay_status = "Paid Online" if user_data[chat_id].payment_method == 'Online' else "Cash on Delivery"

    log_to_google_sheet(order_id, date_str, user_data[chat_id])
    log_order_to_local(order_id, chat_id, user_data[chat_id].name, user_data[chat_id].product, user_data[chat_id].total_amount)

    # Register order -> user mapping for real-time push alerts
    order_user_map[str(order_id)] = chat_id

    loc_val = f"[Click for Maps]({user_data[chat_id].location_link})" if user_data[chat_id].location_link else user_data[chat_id].address

    invoice_msg = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📜 *OFFICIAL INVOICE* 🧾\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *Date:* {date_str} | 🕒 {time_str}\n"
        f"🆔 *Order ID:* `#{order_id}`\n"
        "─────────────────────\n"
        "👤 *CUSTOMER DETAILS*\n"
        f"Name: {user_data[chat_id].name}\n"
        f"Phone: {user_data[chat_id].phone}\n"
        f"Address: {loc_val}\n"
        "─────────────────────\n"
        "📦 *ORDER SUMMARY*\n"
        f"Item(s): *{user_data[chat_id].product}*\n"
        f"Total: *₹{user_data[chat_id].total_amount}*\n"
        f"Payment: {pay_status}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🙏 *Thank you for ordering!*\n"
        "📍 Track your order status with: `/status " + str(order_id) + "`\n"
        "You will receive automatic updates as your order progresses! 🚀"
    )

    # ── Send invoice to customer ──
    try:
        bot.send_message(
            chat_id,
            invoice_msg,
            parse_mode="Markdown",
            reply_markup=get_rating_keyboard(order_id),
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Error sending invoice: {e}")

    # ── Send new order alert to Admin with 1-tap action buttons ──
    try:
        admin_alert = (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔔 *NEW ORDER RECEIVED!* 🛒\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 *Order ID:* `#{order_id}`\n"
            f"📅 *Date:* {date_str} | 🕒 {time_str}\n"
            "─────────────────────\n"
            f"👤 *Name:* {user_data[chat_id].name}\n"
            f"📱 *Phone:* {user_data[chat_id].phone}\n"
            f"📍 *Address:* {loc_val}\n"
            "─────────────────────\n"
            f"📦 *Items:* {user_data[chat_id].product}\n"
            f"💰 *Total:* ₹{user_data[chat_id].total_amount}\n"
            f"💳 *Payment:* {pay_status}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 *Tap a button to update order status:*"
        )
        bot.send_message(
            ADMIN_ID,
            admin_alert,
            parse_mode="Markdown",
            reply_markup=get_admin_order_action_keyboard(order_id),
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Admin alert error: {e}")

    if chat_id in user_data:
        del user_data[chat_id]
    if chat_id in user_carts:
        del user_carts[chat_id]



# ------------------------------------------------------------------------------
# 🔹 PRIMARY MESSAGE HANDLERS
# ------------------------------------------------------------------------------

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # Send "Typing" action to show bot is active
    bot.send_chat_action(message.chat.id, 'upload_photo')

    # 1. Send a Group of Mouth-Watering Images (Album)
    # Using high-quality public URLs for Pizza, Burger, Indian Food
    media = [
        types.InputMediaPhoto('https://images.unsplash.com/photo-1513104890138-7c749659a591', caption="🍕 Cheesy Italian Pizza"),
        types.InputMediaPhoto('https://images.unsplash.com/photo-1568901346375-23c9450c58cd', caption="🍔 Juicy Premium Burgers"),
        types.InputMediaPhoto('https://images.unsplash.com/photo-1585937421612-70a008356fbe', caption="🍛 Authentic Indian Spices")
    ]
    try:
        bot.send_media_group(message.chat.id, media)
    except Exception as e:
        # Fallback if album fails (e.g. bad internet/urls), just continue to text
        print(f"Album Error: {e}")

    # 2. Attractive Welcome Message
    user_name = message.from_user.first_name
    welcome_text = (
        f"✨ *Welcome to Amresh's Food Paradise!* ✨\n\n"
        f"👋 *Namaste {user_name}!* 🙏\n"
        "Are you ready for a flavor explosion? 🌋😋\n\n"
        "🍕 *Cheesy Pizzas* | 🍔 *Juicy Burgers* | 🥗 *Fresh Meals*\n\n"
        "We don't just serve food, we serve **Happiness**! ❤️\n"
        "✅ *Fast Delivery* ⚡\n"
        "✅ *Top Hygiene* 🌟\n"
        "✅ *Best Prices* 💰\n\n"
        "👇 *Tap a button below to Order Now!*"
    )
    
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and ('view menu' in message.text.lower() or 'menu' in message.text.lower()))
def show_categories(message):
    print(f"DEBUG: User {message.chat.id} requested Menu")
    bot.send_message(message.chat.id, "🍱 *Choose a Category:*", parse_mode="Markdown", reply_markup=get_category_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_category(call):
    print(f"DEBUG: Category Clicked: {call.data}")
    try:
        category = call.data.split('cat_')[1] # safer split
        data = load_data()
        matches = [row for row in data if row.get('Category') == category]
        if matches:
            print(f"DEBUG: Found {len(matches)} items for {category}")
            bot.answer_callback_query(call.id, f"Showing {category}")
            for res in matches:
                try:
                    detail = f"🍴 *{res.get('Restaurant_Name', 'Unknown')}*\n⭐ Rating: {res.get('Rating', 'N/A')}\n💰 Cost: ₹{res.get('Avg_Cost', 'N/A')}\n📞 {res.get('Contact', 'N/A')}"
                    img_url = res.get('Image_URL', 'https://via.placeholder.com/300')
                    bot.send_photo(call.message.chat.id, img_url, caption=detail, parse_mode="Markdown", 
                                  reply_markup=get_item_keyboard(res.get('Restaurant_ID')))
                except Exception as e:
                    print(f"Error sending menu item: {e}")
                    # Fallback to text message if photo fails
                    bot.send_message(call.message.chat.id, detail.replace('*', ''), parse_mode=None, 
                                     reply_markup=get_item_keyboard(res.get('Restaurant_ID'))) 
        else:
            bot.answer_callback_query(call.id, "No data available.")
    except Exception as e:
        print(f"Category Handler Error: {e}")
        bot.answer_callback_query(call.id, "Error loading menu.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('rate_'))
def handle_rating(call):
    _, order_id, score = call.data.split('_')
    log_rating_to_google_sheet(order_id, score)
    bot.answer_callback_query(call.id, f"Thank you for the {score} ⭐ rating!")
    bot.edit_message_text(f"✅ *Rating Submitted:* {score} ⭐\nThank you for choosing us!", 
                         call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    # Show main menu again
    bot.send_message(call.message.chat.id, "What would you like to do next?", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['social'])
@bot.message_handler(func=lambda message: message.text and any(keyword in message.text.lower() for keyword in ['social', 'media hub', 'hub', '📱']))
def social_hub(message):
    print(f"DEBUG: Social Hub triggered by {message.chat.id}")
    social_text = (
        "🌟 *Connect with Us!*\n\n"
        "📸 *Instagram:* @amresh_kumar.__\n"
        "💬 *WhatsApp:* +91 8797114376\n\n"
        "Use the buttons below to follow us or chat directly!"
    )
    bot.reply_to(message, social_text, parse_mode="Markdown", reply_markup=get_social_keyboard())

@bot.message_handler(func=lambda message: message.text == '❓ Help / AI Chat')
def help_ai(message):
    bot.reply_to(message, "🤖 *AI Assistant:* How can I help you today? Ask about recipes or restaurant suggestions.", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == '📞 Contact Owner')
def contact_owner(message):
    bot.reply_to(message, "📞 *Contact Amresh Kumar*\n📱 Phone: +91 8797114376\n📸 Instagram: @amresh_kumar.__", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == '🎲 Surprise Me')
def surprise_me(message):
    data = load_data()
    if data:
        choice = random.choice(data)
        caption = (
            f"✨ *Recommended for You!* ✨\n\n"
            f"🍴 *{choice.get('Restaurant_Name')}*\n"
            f"⭐ Rating: {choice.get('Rating', 'N/A')} | 💰 Cost: ₹{choice.get('Avg_Cost', 'N/A')}\n"
            f"🍛 Cuisine: {choice.get('Cuisine', 'N/A')}\n"
            f"📍 City: {choice.get('City', 'N/A')}\n\n"
            f"👇 Click 'Order Food' to book now!"
        )
        img_url = choice.get('Image_URL', 'https://via.placeholder.com/300')
        try:
           bot.send_photo(message.chat.id, img_url, caption=caption, parse_mode="Markdown")
        except:
           bot.send_message(message.chat.id, caption, parse_mode="Markdown")
    else:
        bot.reply_to(message, "⚠️ No restaurants available right now.")

@bot.message_handler(commands=['status'])
@bot.message_handler(func=lambda message: message.text == '📦 Track Order')
def check_order_status(message):
    try:
        args = message.text.split() if message.text.startswith('/') else []
        if len(args) < 2:
            msg = bot.reply_to(
                message,
                "📦 *Live Order Tracking*\n\nEnter your *Order ID* to track your order:\n_(e.g. type: `1234`)_",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, _process_status_query)
            return

        order_id = args[1].strip('#')
        status = get_order_status(order_id)

        if status:
            bot.reply_to(message, get_tracking_status_message(order_id, status), parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ *Order `#{order_id}` not found.*\n\nPlease check your Order ID and try again.", parse_mode="Markdown")
    except Exception as e:
        print(f"Status check error: {e}")
        bot.reply_to(message, "⚠️ Error checking status. Please try again.")

def _process_status_query(message):
    """Handles free-text order ID input for tracking."""
    try:
        order_id = message.text.strip().strip('#')
        status = get_order_status(order_id)
        if status:
            bot.reply_to(message, get_tracking_status_message(order_id, status), parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ *Order `#{order_id}` not found.*\n\nDouble-check your Order ID from your invoice.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "⚠️ Invalid Order ID. Please enter a valid number.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('ostatus_'))
def handle_admin_order_status_update(call):
    """Admin taps a status button -> updates CSV -> pushes real-time notification to customer."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "🚫 Access Denied.")
        return

    try:
        # Format: ostatus_<order_id>_<New Status>
        parts = call.data.split('_', 2)
        order_id = parts[1]
        new_status = parts[2]

        # Update in CSV
        update_order_status(order_id, new_status)

        emoji, detail = STATUS_LABELS.get(new_status, ("🔄", "Status updated."))

        # ── Notify admin (update the admin message) ──
        bot.answer_callback_query(call.id, f"{emoji} Order #{order_id} → {new_status}")
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=get_admin_order_action_keyboard(order_id)
            )
            bot.send_message(
                call.message.chat.id,
                f"✅ *Order #{order_id}* status updated to:\n{emoji} *{new_status}*",
                parse_mode="Markdown"
            )
        except Exception:
            pass

        # ── Push real-time notification to CUSTOMER ──
        customer_chat_id = order_user_map.get(str(order_id))
        if customer_chat_id:
            try:
                notification = get_tracking_status_message(order_id, new_status)
                bot.send_message(
                    customer_chat_id,
                    notification,
                    parse_mode="Markdown"
                )
                # If delivered, send rating prompt again
                if new_status == "Delivered":
                    bot.send_message(
                        customer_chat_id,
                        "🌟 *How was your experience?* Please rate your order below:",
                        parse_mode="Markdown",
                        reply_markup=get_rating_keyboard(order_id)
                    )
            except Exception as e:
                print(f"Customer push error: {e}")
        else:
            print(f"Warning: No customer chat_id found for order #{order_id} (bot restarted?)")

    except Exception as e:
        print(f"Status update callback error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Error updating status.")



@bot.message_handler(commands=['admin'])
def admin_panel(message):
    # Only allow the admin to access this panel
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 *Access Denied:* You are not the admin.")
        return
    
    bot.reply_to(message, "🛠️ *Admin Panel Loaded*\nSelect an option below:", parse_mode="Markdown", reply_markup=get_admin_keyboard())

@bot.message_handler(func=lambda message: message.text == '📦 Active Orders')
def admin_show_orders(message):
    if message.from_user.id != ADMIN_ID: return
    
    if not os.path.exists(ORDERS_FILE):
        bot.reply_to(message, "📂 No order history found.")
        return
        
    try:
        active_orders = []
        with open(ORDERS_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader, None) # Skip Header
            for row in reader:
                if row and 'Pending' in row[4]: # Filter Pending orders
                    active_orders.append(row)
        
        if not active_orders:
            bot.reply_to(message, "✅ No pending orders.")
        else:
            response = "📦 *Pending Orders:*\n\n"
            for order in active_orders[-5:]: # Show last 5
                # Assuming index 4 is Price (after shift) or 5 if Status is shifted
                # The row format is: [Order_ID, User_ID, Name, Product, Price, Status]
                response += f"🆔 *#{order[0]}* - {order[2]}\n🔹 Item: {order[3]}\n💰 Price: ₹{order[4]}\n🔸 Status: {order[5]}\n\n"
            response += "Use `/updatestatus <ID> <Status>` to update."
            bot.reply_to(message, response, parse_mode="Markdown")
            
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error reading orders: {e}")

@bot.message_handler(func=lambda message: message.text == '📄 Download Data')
def admin_download(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        if os.path.exists(ORDERS_FILE):
            with open(ORDERS_FILE, 'rb') as file:
                bot.send_document(message.chat.id, file, caption="📂 Here is your Order History.")
        else:
            bot.reply_to(message, "⚠️ No data file found.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error: {e}")

@bot.message_handler(func=lambda message: message.text == '📢 Broadcast Message')
def admin_broadcast_step1(message):
    if message.from_user.id != ADMIN_ID: return
    msg = bot.send_message(message.chat.id, "📣 Enter the message to broadcast to all users:")
    bot.register_next_step_handler(msg, admin_broadcast_step2)

def admin_broadcast_step2(message):
    text = message.text
    # In a real bot, you would load user_ids from a database/file
    # For now, we'll just echo it back as a demo since we aren't storing all user IDs persistently yet.
    bot.reply_to(message, f"✅ *Broadcast Sent (Demo)*\n\nMessage: {text}\n\n(Note: To send to real users, we need to save every User ID in a file first.)", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == '🔙 Main Menu')
def back_to_main(message):
    bot.reply_to(message, "🔙 Returning to Main Menu...", reply_markup=get_main_keyboard())


@bot.message_handler(func=lambda message: message.text == '➕ More Options')
def show_more_options(message):
    is_admin = (message.from_user.id == ADMIN_ID)
    bot.reply_to(message, "➕ *More Options:*", parse_mode="Markdown", reply_markup=get_more_keyboard(is_admin))

@bot.message_handler(func=lambda message: message.text == '📦 Track Order')
def track_order_entry(message):
    bot.reply_to(message, "📦 To check your order status, please use: `/status <Order_ID>`\nExample: `/status 1234`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == '🛠️ Admin Panel')
def admin_panel_shortcut(message):
    admin_panel(message)

@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    try:
        # Show "Recording Audio" action
        bot.send_chat_action(message.chat.id, 'record_audio')
        
        # Download the voice file
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Get AI Response (Text)
        ai_reply_text = get_voice_response(downloaded_file)
        
        # Reply with Text first (for reference)
        bot.reply_to(message, f"🤖 *AI Reply:* {ai_reply_text}", parse_mode="Markdown")
        
        # Convert AI Reply to Voice (TTS)
        tts = gTTS(text=ai_reply_text, lang='en')
        voice_buffer = io.BytesIO()
        tts.write_to_fp(voice_buffer)
        voice_buffer.seek(0)
        
        # Send Voice Reply
        bot.send_voice(message.chat.id, voice_buffer, caption="🎤 Audio Reply")
        
    except Exception as e:
        print(f"Voice Handle Error: {e}")
        bot.reply_to(message, "⚠️ Sorry, I couldn't process your voice message.")

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    text = message.text.strip() if message.text else ""
    if text:
        print(f"DEBUG: Message received from {message.from_user.first_name}: {text}")

    # Core Buttons Check
    core_buttons = ['view menu', 'order food', 'social media', 'surprise me', 'help / ai chat', 'contact owner', 'hub', 'my cart']
    if any(btn in text.lower() for btn in core_buttons):
        print(f"DEBUG: Core button '{text}' caught and skipped in handle_all")
        return
        
    data = load_data()
    for row in data:
        if text.lower() in row.get('Restaurant_Name', '').lower():
            bot.send_photo(message.chat.id, row.get('Image_URL'), caption=f"🍴 *{row.get('Restaurant_Name')}*", parse_mode="Markdown")
            return
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, get_ai_response(text))

if __name__ == "__main__":
    print("-----------------------------------------------------------------")
    print("[SUCCESS] BOT STARTED SUCCESSFULLY! (Press Ctrl+C to stop)")
    print("Checking Logs... All systems normal.")
    print("-----------------------------------------------------------------")
    # Set Bot Commands for the "Menu" button in Telegram UI
    try:
        bot.set_my_commands([
            types.BotCommand("start", "Launch the bot"),
            types.BotCommand("order", "Order food"),
            types.BotCommand("menu", "View our menu"),
            types.BotCommand("status", "Check order status"),
            types.BotCommand("social", "Social media links"),
            types.BotCommand("help", "AI assistance"),
            types.BotCommand("admin", "Admin panel (Admin only)")
        ])
        print("[OK] Commands set successfully.")
    except Exception as e:
        print(f"[WARN] Failed to set commands: {e}")

    try:
        bot.remove_webhook()
        bot.infinity_polling()
    except Exception as e:
        print(f"ERROR: BOT CRASHED: {e}")
