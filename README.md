# 🍴 Telegram Restaurant & Order Bot

A professional, AI-powered Telegram bot designed for restaurant owners to showcase their menu, take customer orders, and manage data seamlessly using Google Sheets.

## 🚀 Features

-   **🍱 Smart Menu/Restaurant Search:** Customers can search for restaurants by name or ID.
-   **🛒 Interactive Ordering:** A smooth step-by-step flow to collect customer name, address, phone number, and items.
-   **📊 Google Sheets Integration:** Every confirmed order is automatically logged into a Google Sheet in real-time.
-   **🤖 Gemini AI Assistant:** Integrated with Google Gemini 1.5 Flash to answer customer queries politely in Hinglish.
-   **☁️ 24/7 Hosting:** Pre-configured to run on GitHub Actions for free, non-stop operation.

## 🛠️ Tech Stack

-   **Language:** Python 3.x
-   **Telegram Library:** `pyTelegramBotAPI`
-   **AI Engine:** Google Gemini AI (v1beta)
-   **Database (Offline):** CSV (local storage)
-   **Database (Online):** Google Sheets (via Apps Script)
-   **Hosting:** GitHub Actions

## ⚙️ Setup & Deployment

To get this bot running 24/7 on GitHub:

1.  **Fork/Clone** this repository.
2.  Go to your Repository **Settings > Secrets and variables > Actions**.
3.  Add the following **Repository Secrets**:
    -   `TELEGRAM_BOT_TOKEN`: Your BotFather token.
    -   `GOOGLE_API_KEY`: Your Google AI Studio API key.
    -   `GOOGLE_SHEET_URL`: Your Google Apps Script Web App URL.
4.  The bot will automatically start via GitHub Actions!

## 📜 Usage

-   Write `/start` to begin.
-   Type `order` to start booking food.
-   Type `data` to see the full list of restaurants.
-   Ask any question to chat with the AI!

---
Developed by **Amresh Kumar** 🚀
