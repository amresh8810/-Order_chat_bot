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

# Store temporary data
user_data = {}

class Order:
    def __init__(self):
        self.name = None
        self.address = None
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
        params = {
            "order_id": order_id,
            "date": date,
            "name": order_obj.name,
            "address": order_obj.address,
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
    markup.add('🍴 View Menu', '🛒 Order Food', '❓ Help / AI Chat', '📞 Contact Owner')
    return markup

def get_category_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    categories = ['Indian', 'Italian', 'Chinese', 'Fast Food', 'Japanese']
    btns = [types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}") for cat in categories]
    markup.add(*btns)
    return markup

# ==========================================
# HANDLERS
# ==========================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        f"नमस्ते {message.from_user.first_name}! 🍴\n\n"
        "मैं आपका *Premium Restaurant Guide* हूँ।\n"
        "यहाँ से आप शानदार खाना देख सकते हैं और आर्डर कर सकते हैं।"
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
        bot.answer_callback_query(call.id, f"Showing {category} Restaurants")
        for res in matches:
            detail = (
                f"🍴 *{res['Restaurant_Name']}*\n"
                f"⭐ Rating: {res['Rating']} | 🍜 Cuisine: {res['Cuisine']}\n"
                f"💰 Avg Cost: ₹{res['Avg_Cost']}\n"
                f"📍 City: {res['City']}\n"
                f"📞 Contact: {res['Contact']}"
            )
            # Send Photo with Details
            img_url = res.get('Image_URL', 'https://via.placeholder.com/300')
            bot.send_photo(call.message.chat.id, img_url, caption=detail, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "No restaurants found in this category.")

@bot.message_handler(func=lambda message: message.text == '🛒 Order Food')
def start_order(message):
    chat_id = message.chat.id
    user_data[chat_id] = Order()
    msg = bot.send_message(chat_id, "🛒 *Order Booking Start!*\n\nअपना नाम लिखें:")
    bot.register_next_step_handler(msg, process_name_step)

def process_name_step(message):
    chat_id = message.chat.id
    user_data[chat_id].name = message.text
    msg = bot.send_message(chat_id, "अब अपना *Delivery Address* लिखें:")
    bot.register_next_step_handler(msg, process_address_step)

def process_address_step(message):
    chat_id = message.chat.id
    user_data[chat_id].address = message.text
    msg = bot.send_message(chat_id, "आपका *Mobile Number* क्या है?")
    bot.register_next_step_handler(msg, process_phone_step)

def process_phone_step(message):
    chat_id = message.chat.id
    user_data[chat_id].phone = message.text
    msg = bot.send_message(chat_id, "आप क्या खाना चाहते हैं? (Food/Restaurant Name):")
    bot.register_next_step_handler(msg, process_product_step)

def process_product_step(message):
    chat_id = message.chat.id
    user_data[chat_id].product = message.text
    order_id = int(datetime.datetime.now().timestamp()) % 10000
    date_str = datetime.datetime.now().strftime("%d-%m-%Y")
    log_to_google_sheet(order_id, date_str, user_data[chat_id])
    
    conf = (f"✅ *Order Confirmed!*\n\n🆔 ID: {order_id}\n👤 Name: {user_data[chat_id].name}\n Items: {user_data[chat_id].product}\n\nधन्यवाद! 🙏")
    bot.send_message(chat_id, conf, parse_mode="Markdown")
    del user_data[chat_id]

@bot.message_handler(func=lambda message: message.text == ' Contact Owner')
def contact_owner(message):
    bot.reply_to(message, "📞 *Contact Amresh Kumar*\n📱 Phone: +91 9123456780", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == '❓ Help / AI Chat')
def help_ai(message):
    bot.reply_to(message, "🤖 *AI Assistant:* आप मुझसे खाने की सलाह मांग सकते हैं।", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    text = message.text.strip()
    if text in ['🍴 View Menu', '🛒 Order Food', '📞 Contact Owner', '❓ Help / AI Chat']: return
    
    # Simple search fallback
    data = load_data()
    for row in data:
        if text.lower() in row['Restaurant_Name'].lower():
            bot.send_photo(message.chat.id, row['Image_URL'], caption=f"🍴 *{row['Restaurant_Name']}*\n⭐ {row['Rating']}", parse_mode="Markdown")
            return

    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, get_ai_response(text))

if __name__ == "__main__":
    print("Premium Restaurant Bot Starting...")
    bot.infinity_polling()
