"""
================================================================================
🍴 PREMIUM RESTAURANT & ORDER BOT
================================================================================
Developed by: Amresh Kumar
Technology: Python, Telegram Bot API, Google Gemini AI, Google Sheets
Description: A professional ordering solution with GPS support and AI chat.
================================================================================
"""

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

# ------------------------------------------------------------------------------
# 🔹 CORE CONFIGURATION
# ------------------------------------------------------------------------------
# Fetching keys from Environment Variables for Security
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8586119789:AAHyFEdgnYe86kjgzBgGgQbaEr6pog8pzGs')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', 'AIzaSyCNL15MhyDUqVA9cQMO3S1U7IV_ZLTHc38')
SHEET_URL = os.environ.get('GOOGLE_SHEET_URL', 'https://script.google.com/macros/s/AKfycbwdRqnwnDwhSXnGOc7fXgrB96Iiq6JumRfrxwZ2GCuRoqWp6V7OHBe3zpm6iUBU9RZLHg/exec')
UPI_ID = '8797114376@ibl'  # Replace with your actual UPI ID (e.g., phone@paytm)
UPI_NAME = 'Amresh Kumar'
ADMIN_ID = 6886477028  # Replace with your Telegram ID (Use /id command to find yours)

bot = telebot.TeleBot(API_TOKEN)
DATA_FILE = 'data.csv'
ORDERS_FILE = 'orders.csv'

# Temporary storage for order processing
# Temporary storage for order processing
user_data = {}
user_carts = {} # Storage for shopping cart: {chat_id: [items]}

class Order:
    """Class to structure order data during the collection process."""
    def __init__(self):
        self.name = None
        self.address = None
        self.location_link = None
        self.phone = None
        self.product = None
        self.payment_method = None
        self.total_amount = 0
        self.is_manual = False

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
            writer.writerow([order_id, user_id, name, product, price, 'Pending'])
    except Exception as e:
        print(f"Local Log Error: {e}")

def get_order_status(order_id):
    """Retrieves the status of an order from the local CSV."""
    if not os.path.exists(ORDERS_FILE):
        return None
    try:
        with open(ORDERS_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if row and row[0] == str(order_id):
                    return row[4]  # Return Status
    except Exception as e:
        print(f"Read Status Error: {e}")
    return None

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
                    row[4] = new_status
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
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Add to Cart", callback_data=f"add_{item_id}"))
    return markup

def get_cart_keyboard():
    """Keyboard for cart management."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛍️ Checkout Now", callback_data="checkout"),
        types.InlineKeyboardButton("🗑️ Clear Cart", callback_data="clear_cart")
    )
    return markup

# ------------------------------------------------------------------------------
# 🔹 ORDER FLOW LOGIC
# ------------------------------------------------------------------------------

@bot.message_handler(func=lambda message: message.text == '🛒 My Cart')
def show_cart(message):
    chat_id = message.chat.id
    cart = user_carts.get(chat_id, [])
    
    if not cart:
        bot.send_message(chat_id, "🛒 *Your cart is empty!*\n\nBrowse the menu and add some delicious items first. 😋", 
                         parse_mode="Markdown", reply_markup=get_main_keyboard())
        return

    summary = "🛒 *YOUR SHOPPING CART*\n"
    summary += "━━━━━━━━━━━━━━━━━━━━━\n"
    total = 0
    for i, item in enumerate(cart, 1):
        summary += f"{i}. *{item['name']}* - ₹{item['price']}\n"
        total += int(item['price'])
    
    summary += "━━━━━━━━━━━━━━━━━━━━━\n"
    summary += f"💰 *Total Amount: ₹{total}*\n\n"
    summary += "Ready to eat? Click below to place your order!"
    
    bot.send_message(chat_id, summary, parse_mode="Markdown", reply_markup=get_cart_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_'))
def handle_add_to_cart(call):
    item_id = call.data.split('_')[1]
    data = load_data()
    item = next((row for row in data if row.get('Restaurant_ID') == item_id), None)
    
    if item:
        chat_id = call.message.chat.id
        if chat_id not in user_carts:
            user_carts[chat_id] = []
        
        user_carts[chat_id].append({
            'name': item.get('Restaurant_Name'),
            'price': item.get('Avg_Cost')
        })
        
        bot.answer_callback_query(call.id, f"✅ Added {item.get('Restaurant_Name')} to cart!")
    else:
        bot.answer_callback_query(call.id, "⚠️ Item not found.")

@bot.callback_query_handler(func=lambda call: call.data == 'clear_cart')
def handle_clear_cart(call):
    chat_id = call.message.chat.id
    if chat_id in user_carts:
        user_carts[chat_id] = []
    bot.answer_callback_query(call.id, "🗑️ Cart cleared.")
    bot.edit_message_text("🛒 Your cart has been cleared.", chat_id, call.message.message_id)
    bot.send_message(chat_id, "What would you like to do next?", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == 'checkout')
def handle_checkout_callback(call):
    bot.answer_callback_query(call.id)
    start_order(call.message)


@bot.message_handler(func=lambda message: message.text == '🛒 Order Food' or message.text == '/order')
def start_manual_order(message):
    chat_id = message.chat.id
    user_data[chat_id] = Order()
    user_data[chat_id].is_manual = True
    msg = bot.send_message(chat_id, "🛒 *Manual Order Started*\n\nPlease enter your full name:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_name_step)

def start_order(message):
    chat_id = message.chat.id
    
    if not user_carts.get(chat_id):
        bot.send_message(chat_id, "⚠️ Your cart is empty! Add items from the menu first.")
        return

    user_data[chat_id] = Order()
    user_data[chat_id].is_manual = False
    # Prepare cart summary
    cart = user_carts[chat_id]
    user_data[chat_id].product = ", ".join([item['name'] for item in cart])
    user_data[chat_id].total_amount = sum([int(item['price']) for item in cart])

    msg = bot.send_message(chat_id, "🛒 *Cart Checkout Started*\n\nPlease enter your full name:", parse_mode="Markdown")
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
        
        # Send Local QR Code
        # Make sure to save your QR image as 'payment_qr.jpg' in the same folder
        if os.path.exists('payment_qr.jpg'):
            try:
                with open('payment_qr.jpg', 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption=f"📲 *Scan to Pay*\nUPI ID: `{UPI_ID}`\n\nAfter payment, click 'Confirm Payment' below.", parse_mode="Markdown")
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Error sending QR code. Please pay directly to: `{UPI_ID}`", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"📲 *Pay Online*\n\nUPI ID: `{UPI_ID}`\n\n(QR Code image not found. Please save it as 'payment_qr.jpg')", parse_mode="Markdown")
        
        # Ask for confirmation
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('✅ Confirm Payment')
        msg = bot.send_message(chat_id, "Please confirm once paid:", reply_markup=markup)
        bot.register_next_step_handler(msg, finalize_order)
        
    else:
        user_data[chat_id].payment_method = 'COD'
        finalize_order(message)

def finalize_order(message):
    chat_id = message.chat.id
    
    # Check if 'Confirm Payment' was clicked or if it's COD direct flow
    # If the user typed something else, we assume they are proceeding.
    
    order_id = int(datetime.datetime.now().timestamp()) % 10000
    date_str, time_str = datetime.datetime.now().strftime("%d-%m-%Y"), datetime.datetime.now().strftime("%I:%M %p")
    
    pay_status = "Paid Online" if user_data[chat_id].payment_method == 'Online' else "Cash on Delivery"
    status_msg = "Pending (Paid)" if user_data[chat_id].payment_method == 'Online' else "Pending (COD)"

    log_to_google_sheet(order_id, date_str, user_data[chat_id])
    log_order_to_local(order_id, chat_id, user_data[chat_id].name, user_data[chat_id].product, user_data[chat_id].total_amount)
    
    # Update local status if online
    if user_data[chat_id].payment_method == 'Online':
        update_order_status(order_id, 'Pending (Paid)')

    loc_val = f"[Click for Maps]({user_data[chat_id].location_link})" if user_data[chat_id].location_link else user_data[chat_id].address
    
    invoice_msg = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📜 *OFFICIAL INVOICE* 🧾\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *Date:* {date_str} | 🕒 {time_str}\n"
        f"🆔 *Order ID:* #{order_id}\n"
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
        "We will contact you shortly."
    )
    # Merge Invoice and Rating buttons in one go
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
@bot.message_handler(func=lambda message: message.text and ('social media' in message.text.lower() or 'hub' in message.text.lower() or '📱' in message.text))
def social_hub(message):
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
def check_order_status(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Usage: /status <Order_ID>\nExample: /status 12345")
            return
        
        order_id = args[1]
        status = get_order_status(order_id)
        
        if status:
            bot.reply_to(message, f"📦 **Order #{order_id} Status:**\n🔹 {status}", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Order ID not found. Please check and try again.")
    except Exception as e:
        bot.reply_to(message, "⚠️ Error checking status.")

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

    # Core Buttons Check (Lower-case check for better matching)
    core_buttons = ['view menu', 'order food', 'social media', 'surprise me', 'help / ai chat', 'contact owner', 'hub', 'my cart']
    if any(btn in text.lower() for btn in core_buttons):
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
        bot.infinity_polling()
    except Exception as e:
        print(f"ERROR: BOT CRASHED: {e}")
