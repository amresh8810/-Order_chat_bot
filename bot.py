import telebot
import requests
import csv
import os
import datetime
from telebot import types

# ==========================================
# CONFIGURATION
# ==========================================
# Get keys from environment variables (Secrets)
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
        response = requests.get(SHEET_URL, params=params)
        if response.status_code == 200:
            print(f"DEBUG: Successfully logged to Google Sheets: {order_id}")
        else:
            print(f"DEBUG: Google Sheet Log Failed ({response.status_code})")
    except Exception as e:
        print(f"DEBUG: Google Sheet Error: {e}")

# Gemini AI Response
def get_ai_response(user_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GOOGLE_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"You are a helpful assistant for a Restaurant Guide and Food Ordering bot. Answer short and politely in Hindi/English mix. User says: {user_text}"
            }]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        return "AI Error: Response invalid."
    except:
        return "AI Service unavailable."

# ==========================================
# ORDER FLOW HANDLERS
# ==========================================

@bot.message_handler(commands=['order'])
@bot.message_handler(func=lambda message: 'order' in message.text.lower())
def start_order(message):
    chat_id = message.chat.id
    user_data[chat_id] = Order()
    msg = bot.send_message(chat_id, "🍴 *Food Order Booking Start!*\n\nअपना नाम लिखें:")
    bot.register_next_step_handler(msg, process_name_step)

def process_name_step(message):
    try:
        chat_id = message.chat.id
        user_data[chat_id].name = message.text
        msg = bot.send_message(chat_id, "अब अपना *Delivery Address* लिखें:")
        bot.register_next_step_handler(msg, process_address_step)
    except:
        bot.reply_to(message, 'Error! Please use /order again.')

def process_address_step(message):
    try:
        chat_id = message.chat.id
        user_data[chat_id].address = message.text
        msg = bot.send_message(chat_id, "आपका *Mobile Number* क्या है?")
        bot.register_next_step_handler(msg, process_phone_step)
    except:
        bot.reply_to(message, 'Error!')

def process_phone_step(message):
    try:
        chat_id = message.chat.id
        user_data[chat_id].phone = message.text
        msg = bot.send_message(chat_id, "आप क्या आर्डर करना चाहते हैं? (Food/Restaurant Name):")
        bot.register_next_step_handler(msg, process_product_step)
    except:
        bot.reply_to(message, 'Error!')

def process_product_step(message):
    try:
        chat_id = message.chat.id
        user_data[chat_id].product = message.text
        
        # Generation Order ID (Simulated)
        order_id = int(datetime.datetime.now().timestamp()) % 10000
        date_str = datetime.datetime.now().strftime("%d-%m-%Y")
        
        # Log to Google Sheets
        log_to_google_sheet(order_id, date_str, user_data[chat_id])
        
        confirmation = (
            f"✅ *Order Confirmed!*\n\n"
            f"🆔 *Order ID:* {order_id}\n"
            f"👤 *Customer:* {user_data[chat_id].name}\n"
            f"📍 *Address:* {user_data[chat_id].address}\n"
            f"📞 *Phone:* {user_data[chat_id].phone}\n"
            f"📦 *Items:* {user_data[chat_id].product}\n\n"
            f"आपका खाना जल्दी पहुँच जाएगा! धन्यवाद! 🙏"
        )
        bot.send_message(chat_id, confirmation, parse_mode="Markdown")
        del user_data[chat_id]
    except Exception as e:
        bot.reply_to(message, f'Error: {e}')

# ==========================================
# GENERAL HANDLERS
# ==========================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        f"नमस्ते {message.from_user.first_name}! 🍴\n\n"
        "मैं आपका *Restaurant Guide & Order Bot* हूँ।\n"
        "🔹 *Menu/Data:* 'data' लिखें\n"
        "🔹 *Order Food:* 'order' लिखें\n"
        "� *AI Chat:* कुछ भी पूछें!"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: 'data' in message.text.lower())
def show_restaurants(message):
    data = load_data()
    if data:
        summary = "🍴 *Available Restaurants & Menu:*\n\n"
        for row in data:
            summary += f"🆔 {row['Restaurant_ID']} | *{row['Restaurant_Name']}* | ⭐ {row['Rating']}\n"
        bot.reply_to(message, summary, parse_mode="Markdown")
    else:
        bot.reply_to(message, "No data available.")

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    text = message.text.strip()
    data = load_data()
    
    # Search logic
    if data:
        for row in data:
            if text.lower() in row['Restaurant_Name'].lower() or text == row['Restaurant_ID']:
                detail = (
                    f"🍴 *{row['Restaurant_Name']}*\n"
                    f"📍 City: {row['City']}\n"
                    f"🍜 Cuisine: {row['Cuisine']}\n"
                    f"⭐ Rating: {row['Rating']}\n"
                    f"💰 Cost: ₹{row['Avg_Cost']}\n"
                    f"📞 Contact: {row['Contact']}"
                )
                bot.reply_to(message, detail, parse_mode="Markdown")
                return

    # AI Fallback
    bot.send_chat_action(message.chat.id, 'typing')
    ai_answer = get_ai_response(text)
    bot.reply_to(message, ai_answer)

if __name__ == "__main__":
    print("Restaurant & Order Bot is starting...")
    bot.infinity_polling()
