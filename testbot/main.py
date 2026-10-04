import telebot
from telebot import types
import random
import time
import threading
import json
import re

from google import genai
from config import TOKEN, GEMINI_API_KEY
from database import load_users, save_users
import telebot.apihelper as apihelper

# ================= CONFIG =================
apihelper.CONNECT_TIMEOUT = 60
apihelper.READ_TIMEOUT = 60

bot = telebot.TeleBot(TOKEN, threaded=False)

client = genai.Client(api_key=GEMINI_API_KEY)

user_data = load_users()

# ================= USER =================
def get_user(uid):
    if uid not in user_data:
        user_data[uid] = {
            "coin": 0,
            "score": 0,
            "q_index": 0,
            "shuffled": [],
            "current_question": None,
            "current_options": [],
            "user_answered": False,
            "waiting_for_book": False,
            "book_name": None
        }
    return user_data[uid]


def init_test(user, questions):
    user["shuffled"] = random.sample(questions, min(20, len(questions)))
    user["q_index"] = 0
    user["score"] = 0


# ================= AI =================
def generate_questions_ai(book_name):
    prompt = f"""
"{book_name}" kitobi bo'yicha 20 ta test savol tuz.

Qoidalar:
- 3 ta variant
- 1 ta to'g'ri javob
- JSON formatda qaytar

[
  {{
    "question": "...",
    "options": ["A", "B", "C"],
    "answer": "A"
  }}
]
"""

    response = client.models.generate_content(
        contents=prompt
    )

    raw = response.text.strip()
    raw = re.sub(r"```json|```", "", raw)

    return json.loads(raw)


# ================= TIMER =================
def question_timer(chat_id, q_index):
    time.sleep(10)

    uid = str(chat_id)
    user = get_user(uid)

    if user["user_answered"]:
        return

    if user["q_index"] != q_index:
        return

    q = user["current_question"]

    bot.send_message(
        chat_id,
        f"⏰ Vaqt tugadi!\n\n✔️ To‘g‘ri javob: {q['answer']}"
    )

    user["q_index"] += 1
    user["user_answered"] = True
    save_users(user_data)

    send_question(chat_id)


# ================= SEND QUESTION =================
def send_question(chat_id):
    uid = str(chat_id)
    user = get_user(uid)

    if user["q_index"] >= len(user["shuffled"]):
        bot.send_message(chat_id, f"✅ Test tugadi!\n💰 Coin: {user['coin']}")
        return

    q = user["shuffled"][user["q_index"]]
    user["current_question"] = q
    user["user_answered"] = False

    options = q["options"].copy()
    random.shuffle(options)
    user["current_options"] = options

    markup = types.InlineKeyboardMarkup()
    for i, opt in enumerate(options):
        markup.add(types.InlineKeyboardButton(opt, callback_data=f"opt_{i}"))

    bot.send_message(
        chat_id,
        f"📚 Savol {user['q_index']+1}/{len(user['shuffled'])}\n\n{q['question']}",
        reply_markup=markup
    )

    threading.Thread(
        target=question_timer,
        args=(chat_id, user["q_index"]),
        daemon=True
    ).start()


# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.chat.id)
    user = get_user(uid)
    user["waiting_for_book"] = False

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📖 Kitob tanlash", callback_data="choose"))

    bot.send_message(
        message.chat.id,
        "📚 Kitob nomini yozing yoki tanlang",
        reply_markup=markup
    )


# ================= CHOOSE BOOK =================
@bot.callback_query_handler(func=lambda call: call.data == "choose")
def choose(call):
    uid = str(call.message.chat.id)
    user = get_user(uid)
    user["waiting_for_book"] = True
    save_users(user_data)

    bot.send_message(call.message.chat.id, "📖 Kitob nomini kiriting")


# ================= ANSWER =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("opt_"))
def answer(call):
    uid = str(call.message.chat.id)
    user = get_user(uid)

    if user["user_answered"]:
        return

    user["user_answered"] = True

    idx = int(call.data.split("_")[1])
    selected = user["current_options"][idx]
    correct = user["current_question"]["answer"]

    if selected == correct:
        user["coin"] += 5
        user["score"] += 1
        bot.answer_callback_query(call.id, "✅ To‘g‘ri +5 coin")
    else:
        bot.answer_callback_query(call.id, f"❌ Noto‘g‘ri\nJavob: {correct}")

    user["q_index"] += 1
    save_users(user_data)

    send_question(call.message.chat.id)


# ================= TEXT =================
@bot.message_handler(content_types=['text'])
def text_handler(message):
    uid = str(message.chat.id)
    user = get_user(uid)

    if user["waiting_for_book"]:
        book = message.text
        user["waiting_for_book"] = False
        user["book_name"] = book

        msg = bot.send_message(message.chat.id, "🤖 AI savollar yaratmoqda...")

        try:
            questions = generate_questions_ai(book)

            init_test(user, questions)
            save_users(user_data)

            bot.edit_message_text(
                "✅ Tayyor! Test boshlanmoqda...",
                message.chat.id,
                msg.message_id
            )

            send_question(message.chat.id)

        except Exception as e:
            bot.edit_message_text(
                f"❌ Xatolik: {str(e)[:200]}",
                message.chat.id,
                msg.message_id
            )

    elif message.text == "💰 Coinlarim":
        bot.send_message(message.chat.id, f"💰 Coin: {user['coin']}")


# ================= RUN =================
print("Bot ishlayapti...")

while True:
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print("Restart:", e)
        time.sleep(5)