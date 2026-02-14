import telebot
import requests
import csv
import os
import datetime
from telebot import types

# ==========================================
# CONFIGURATION
# ==========================================
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8587931543:AAFJJ7OHr6yaPvJ3zgfB9fhsq9KeVrWScgQ')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', 'AIzaSyDsjiyAM5B9lJtplEUpCkhElbvfeQtBOQA')
SHEET_URL = os.environ.get('GOOGLE_SHEET_URL', 'https://script.google.com/macros/s/AKfycbwdRqnwnDwhSXnGOc7fXgrB96Iiq6JumRfrxwZ2GCuRoqWp6V7OHBe3zpm6iUBU9RZLHg/exec')

bot = telebot.TeleBot(API_TOKEN)
DATA_FILE = 'data.csv'

# Store temporary order data
user_data = {}

class Order:
    def __init__(self):
        self.name = None
        self.address = None
        self.location_link = None
        self.phone = None
        self.product = None

# Function to load restaurant data
def load_data():
    data = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data.append(row)
            return data
        except Exception as e:
            print(f"File read error: {e}")
    return None

# Function to log order to Google Sheets
def log_to_google_sheet(order_id, date, order_obj):
    try:
        # Use location link if available, otherwise text address
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
    except:
        pass

# Gemini AI Response
def get_ai_response(user_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GOOGLE_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": f"You are a helpful assistant for a Restaurant. Answer in Hinglish. User says: {user_text}"}]}]}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "AI is busy, please try again!"

# ==========================================
# KEYBOARDS
# ==========================================

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🍴 View Menu', '🛒 Order Food', '📱 Social Media Hub', '❓ Help / AI Chat', '📞 Contact Owner')
    return markup

def get_social_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_wa = types.InlineKeyboardButton("💬 Chat on WhatsApp", url="https://wa.me/918797114376")
    btn_ig = types.InlineKeyboardButton("📸 Follow on Instagram", url="https://www.instagram.com/amresh_kumar.__?igsh=MW95aWs1cDZ1aXpjdg==")
    btn_map = types.InlineKeyboardButton("📍 Our Restaurant Location", url="https://www.google.com/maps/place/Vinayaka+Missions+Kirupananda+Variyar+Medical+College+%26+Hospital/@11.5833319,78.0471145,8480m/data=!3m1!1e3!4m6!3m5!1s0x3babefd87754637d:0x567844ffa0271836!8m2!3d11.5855951!4d78.0638786!16s%2Fg%2F11qm0bk4sb?entry=ttu&g_ep=EgoyMDI2MDIxMS4wIKXMDSoASAFQAw%3D%3D")
    markup.add(btn_wa, btn_ig, btn_map)
    return markup

def get_location_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
    btn_location = types.KeyboardButton('📍 Share My Current Location', request_location=True)
    btn_skip = types.KeyboardButton('Type Manually')
    markup.add(btn_location, btn_skip)
    return markup

def get_category_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    categories = ['Indian', 'Italian', 'Chinese', 'Fast Food', 'Japanese']
    btns = [types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}") for cat in categories]
    markup.add(*btns)
    return markup

# ==========================================
# ORDER FLOW HANDLERS
# ==========================================

@bot.message_handler(func=lambda message: message.text == '🛒 Order Food' or message.text == '/order')
def start_order(message):
    chat_id = message.chat.id
    user_data[chat_id] = Order()
    msg = bot.send_message(chat_id, "🛒 *Food Order Booking Start!*\n\nअपना पूरा नाम लिखें:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_name_step)

def process_name_step(message):
    chat_id = message.chat.id
    user_data[chat_id].name = message.text
    msg = bot.send_message(chat_id, f"नमस्ते {message.text}! अपना डिलीवरी पता देने के लिए नीचे बटन दबाएं या टाइप करें:", 
                          reply_markup=get_location_keyboard(), parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_address_logic)

def process_address_logic(message):
    chat_id = message.chat.id
    
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        user_data[chat_id].location_link = f"https://www.google.com/maps?q={lat},{lon}"
        user_data[chat_id].address = "Location Shared via GPS"
        msg = bot.send_message(chat_id, "📍 लोकेशन मिल गई! अब अपना *Mobile Number* दें:", 
                              reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_phone_step)
    elif message.text == 'Type Manually':
        msg = bot.send_message(chat_id, "ठीक है, अपना पूरा पता (Address) टाइप करें:", 
                              reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, process_manual_address_step)
    else:
        # User typed address directly
        user_data[chat_id].address = message.text
        msg = bot.send_message(chat_id, "अब अपना *Mobile Number* दें:", 
                              reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_phone_step)

def process_manual_address_step(message):
    chat_id = message.chat.id
    user_data[chat_id].address = message.text
    msg = bot.send_message(chat_id, "ठीक है! अब अपना *Mobile Number* क्या है?")
    bot.register_next_step_handler(msg, process_phone_step)

def process_phone_step(message):
    chat_id = message.chat.id
    user_data[chat_id].phone = message.text
    msg = bot.send_message(chat_id, "आप क्या खाना चाहते हैं? (Food/Restaurant Name):", reply_markup=get_main_keyboard())
    bot.register_next_step_handler(msg, process_product_step)

def process_product_step(message):
    chat_id = message.chat.id
    user_data[chat_id].product = message.text
    order_id = int(datetime.datetime.now().timestamp()) % 10000
    date_str = datetime.datetime.now().strftime("%d-%m-%Y")
    
    # Log to Google Sheets
    log_to_google_sheet(order_id, date_str, user_data[chat_id])
    
    # Confirmation Text
    location_info = f"\n📍 [Google Maps Location]({user_data[chat_id].location_link})" if user_data[chat_id].location_link else f"\n📍 Address: {user_data[chat_id].address}"
    
    conf = (
        f"✅ *Order Confirmed!*\n\n"
        f"🆔 ID: {order_id}\n"
        f"👤 Name: {user_data[chat_id].name}"
        f"{location_info}\n"
        f"📦 Items: {user_data[chat_id].product}\n\n"
        f"धन्यवाद! हमें आपका आर्डर मिल गया है। 🙏"
    )
    bot.send_message(chat_id, conf, parse_mode="Markdown", reply_markup=get_main_keyboard())
    del user_data[chat_id]

# ==========================================
# GENERAL HANDLERS
# ==========================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        f"नमस्ते {message.from_user.first_name}! 🍴\n\n"
        "मैं आपका *Premium Restaurant Guide* हूँ।\n"
        "अब आप अपना *Live Location* शेयर करके और भी आसानी से आर्डर कर सकते हैं!"
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
            detail = (
                f"🍴 *{res['Restaurant_Name']}*\n"
                f"⭐ Rating: {res['Rating']}\n"
                f"💰 Avg Cost: ₹{res['Avg_Cost']}\n"
                f"📞 Contact: {res['Contact']}"
            )
            img_url = res.get('Image_URL', 'https://via.placeholder.com/300')
            bot.send_photo(call.message.chat.id, img_url, caption=detail, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "No data found.")

@bot.message_handler(func=lambda message: message.text == '📞 Contact Owner')
def contact_owner(message):
    bot.reply_to(message, "📞 *Contact Amresh Kumar*\n📱 Phone: +91 9123456780", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == '❓ Help / AI Chat')
def help_ai(message):
    bot.reply_to(message, "🤖 *AI Assistant:* मुझसे कुछ भी पूछें!", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == '📱 Social Media Hub')
def social_hub(message):
    social_text = (
        "🌟 *Connect with Us!*\n\n"
        "नीचे दिए गए बटनों पर क्लिक करके हमसे जुड़ें:"
    )
    bot.reply_to(message, social_text, parse_mode="Markdown", reply_markup=get_social_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    text = message.text.strip()
    if text in ['🍴 View Menu', '🛒 Order Food', '� Social Media Hub', '❓ Help / AI Chat', '📞 Contact Owner']: return
    
    # Search fallback
    data = load_data()
    for row in data:
        if text.lower() in row['Restaurant_Name'].lower():
            bot.send_photo(message.chat.id, row['Image_URL'], caption=f"🍴 *{row['Restaurant_Name']}*", parse_mode="Markdown")
            return

    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, get_ai_response(text))

if __name__ == "__main__":
    print("Restaurant Bot with GPS Location Starting...")
    bot.infinity_polling()
