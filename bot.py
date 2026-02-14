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
import datetime
from telebot import types

# ------------------------------------------------------------------------------
# 🔹 CORE CONFIGURATION
# ------------------------------------------------------------------------------
# Fetching keys from Environment Variables for Security
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8587931543:AAFJJ7OHr6yaPvJ3zgfB9fhsq9KeVrWScgQ')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', 'AIzaSyDsjiyAM5B9lJtplEUpCkhElbvfeQtBOQA')
SHEET_URL = os.environ.get('GOOGLE_SHEET_URL', 'https://script.google.com/macros/s/AKfycbwdRqnwnDwhSXnGOc7fXgrB96Iiq6JumRfrxwZ2GCuRoqWp6V7OHBe3zpm6iUBU9RZLHg/exec')

bot = telebot.TeleBot(API_TOKEN)
DATA_FILE = 'data.csv'

# Temporary storage for order processing
user_data = {}

class Order:
    """Class to structure order data during the collection process."""
    def __init__(self):
        self.name = None
        self.address = None
        self.location_link = None
        self.phone = None
        self.product = None

# ------------------------------------------------------------------------------
# 🔹 DATA & CLOUD INTEGRATION
# ------------------------------------------------------------------------------

def load_data():
    """Loads restaurant data from local CSV file."""
    data = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data.append(row)
            return data
        except Exception as e:
            print(f"Error reading CSV: {e}")
    return None

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
            "product": order_obj.product
        }
        requests.get(SHEET_URL, params=params, timeout=5)
    except Exception as e:
        print(f"Cloud Sync Error: {e}")

# ------------------------------------------------------------------------------
# 🔹 AI ASSISTANT (GEMINI AI)
# ------------------------------------------------------------------------------

def get_ai_response(user_text):
    """Generates intelligent responses using Google Gemini 1.5 Flash."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GOOGLE_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"You are a professional assistant for a Restaurant. Answer politely in English. User says: {user_text}"}]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Our AI assistant is temporarily unavailable. Please try again later."

# ------------------------------------------------------------------------------
# 🔹 DYNAMIC KEYBOARDS
# ------------------------------------------------------------------------------

def get_main_keyboard():
    """Returns the primary navigation menu."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🍴 View Menu', '🛒 Order Food', '📱 Social Media Hub', '❓ Help / AI Chat', '📞 Contact Owner')
    return markup

def get_social_keyboard():
    """Returns interactive links for social media engagement."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_wa = types.InlineKeyboardButton("💬 Chat on WhatsApp", url="https://wa.me/918797114376")
    btn_ig = types.InlineKeyboardButton("📸 Follow on Instagram", url="https://www.instagram.com/amresh_kumar.__?igsh=MW95aWs1cDZ1aXpjdg==")
    btn_map = types.InlineKeyboardButton("📍 Our Restaurant Location", url="https://www.google.com/maps/place/Vinayaka+Missions+Kirupananda+Variyar+Medical+College+%26+Hospital/@11.5833319,78.0471145,8480m/data=!3m1!1e3!4m6!3m5!1s0x3babefd87754637d:0x567844ffa0271836!8m2!3d11.5855951!4d78.0638786!16s%2Fg%2F11qm0bk4sb?entry=ttu&g_ep=EgoyMDI2MDIxMS4wIKXMDSoASAFQAw%3D%3D")
    markup.add(btn_wa, btn_ig, btn_map)
    return markup

def get_location_keyboard():
    """Offers GPS location sharing or manual address entry."""
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
    btn_location = types.KeyboardButton('📍 Share My Current Location', request_location=True)
    btn_skip = types.KeyboardButton('Type Manually')
    markup.add(btn_location, btn_skip)
    return markup

def get_category_keyboard():
    """Displays restaurant categories via inline buttons."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    categories = ['Indian', 'Italian', 'Chinese', 'Fast Food', 'Japanese']
    btns = [types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}") for cat in categories]
    markup.add(*btns)
    return markup

# ------------------------------------------------------------------------------
# 🔹 ORDER FLOW LOGIC
# ------------------------------------------------------------------------------

@bot.message_handler(func=lambda message: message.text == '🛒 Order Food' or message.text == '/order')
def start_order(message):
    chat_id = message.chat.id
    user_data[chat_id] = Order()
    msg = bot.send_message(chat_id, "🛒 *Food Order Booking Started*\n\nPlease enter your full name:", parse_mode="Markdown")
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
    msg = bot.send_message(chat_id, "What would you like to order? (Food Name):")
    bot.register_next_step_handler(msg, process_product_step)

def process_product_step(message):
    chat_id = message.chat.id
    user_data[chat_id].product = message.text
    order_id = int(datetime.datetime.now().timestamp()) % 10000
    date_str, time_str = datetime.datetime.now().strftime("%d-%m-%Y"), datetime.datetime.now().strftime("%I:%M %p")
    
    log_to_google_sheet(order_id, date_str, user_data[chat_id])
    
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
        "Status: ✅ Confirmed (COD)\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🙏 *Thank you for ordering!*\n"
        "We will contact you shortly."
    )
    bot.send_message(chat_id, invoice_msg, parse_mode="Markdown", reply_markup=get_main_keyboard(), disable_web_page_preview=True)
    del user_data[chat_id]

# ------------------------------------------------------------------------------
# 🔹 PRIMARY MESSAGE HANDLERS
# ------------------------------------------------------------------------------

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        f"Hi {message.from_user.first_name}! 🍴\n\n"
        "Welcome to the *Premium Restaurant Guide*.\n"
        "Explore our menu, chat with AI, or place an order below!"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text == '🍴 View Menu')
def show_categories(message):
    bot.send_message(message.chat.id, "🍱 *Choose a Category:*", parse_mode="Markdown", reply_markup=get_category_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_category(call):
    category = call.data.split('_')[1]
    data = load_data()
    matches = [row for row in data if row['Category'] == category]
    if matches:
        bot.answer_callback_query(call.id, f"Showing {category}")
        for res in matches:
            detail = f"🍴 *{res['Restaurant_Name']}*\n⭐ Rating: {res['Rating']}\n💰 Cost: ₹{res['Avg_Cost']}\n📞 {res['Contact']}"
            img_url = res.get('Image_URL', 'https://via.placeholder.com/300')
            bot.send_photo(call.message.chat.id, img_url, caption=detail, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "No data available.")

@bot.message_handler(func=lambda message: message.text == '📱 Social Media Hub')
def social_hub(message):
    social_text = "🌟 *Connect with Us!*\n\nUse the buttons below to follow us or chat on WhatsApp:"
    bot.reply_to(message, social_text, parse_mode="Markdown", reply_markup=get_social_keyboard())

@bot.message_handler(func=lambda message: message.text == '❓ Help / AI Chat')
def help_ai(message):
    bot.reply_to(message, "🤖 *AI Assistant:* How can I help you today? Ask about recipes or restaurant suggestions.", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == '📞 Contact Owner')
def contact_owner(message):
    bot.reply_to(message, "📞 *Contact Amresh Kumar*\n📱 Phone: +91 8797114376", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    text = message.text.strip()
    if text in ['🍴 View Menu', '🛒 Order Food', '📱 Social Media Hub', '❓ Help / AI Chat', '📞 Contact Owner']: return
    data = load_data()
    for row in data:
        if text.lower() in row['Restaurant_Name'].lower():
            bot.send_photo(message.chat.id, row['Image_URL'], caption=f"🍴 *{row['Restaurant_Name']}*", parse_mode="Markdown")
            return
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, get_ai_response(text))

if __name__ == "__main__":
    print("Premium Restaurant Bot Launching...")
    bot.infinity_polling()
