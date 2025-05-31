from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, JobQueue
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import random


import json
import atexit

DATA_FILE = "data.json"

def load_data():
    global user_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            user_data.update(json.load(f))
    except FileNotFoundError:
        pass

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# Tự động lưu dữ liệu khi thoát
atexit.register(save_data)


user_data = {}

IDEAL_MIN = 4
IDEAL_MAX = 8
FAST_CLICK_THRESHOLD = 2
ASK_MOMENT_PROB = 0.3
CHECK_IN_TIMEOUT = 3600

LEVELS = [
    (0, "🥚 Vô danh"),
    (5, "🌱 Mầm tỉnh"),
    (15, "🌿 Gõ nhẹ"),
    (30, "🌼 Sơ thiền"),
    (60, "🔥 Trung thiền"),
    (100, "🌕 Cao duyên"),
    (200, "🌀 Vô niệm")
]

MOMENT_QUESTIONS = [
    ("🧭 Lúc này bạn nghe thấy điều gì nhất?", ["Sự im lặng", "Gió thổi", "Tiếng vọng bên trong"]),
    ("🌕 Nếu phải gọi tên cảm giác vừa rồi, bạn sẽ gọi nó là gì?", ["Nhẹ tênh", "Mơ hồ", "Không biết"]),
    ("🔍 Cú gõ vừa nãy... làm bạn nhớ đến ai?", ["Chính mình", "Một người xưa", "Không nhớ"])
]

CHECKIN_QUESTION = "📖 Câu chuyện của ngày hôm nay. Bạn cảm thấy thế nào?"
CHECKIN_OPTIONS = ["Bình yên", "Xáo động", "Chờ đợi", "Không rõ"]

def get_level(karma):
    level = LEVELS[0][1]
    for k, name in LEVELS:
        if karma >= k:
            level = name
        else:
            break
    return level

async def gong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now()
    data = user_data.get(user_id, {"karma": 0, "last_gong": None, "streak": 0, "mood": None, "last_checkin": None})
    last = data["last_gong"]

    if last:
        diff = (now - last).total_seconds()
        if diff < FAST_CLICK_THRESHOLD:
            return
        if IDEAL_MIN <= diff <= IDEAL_MAX:
            chance = random.random()
            if chance < 0.7:
                data["karma"] += 1
                data["streak"] += 1
                msg = f"🔔 Goong... Nhịp thở đều ({int(diff)}s).\n+1 karma. Tổng: {data['karma']} (chuỗi: {data['streak']})"
            else:
                data["streak"] = 0
                msg = f"🔔 Goong... Nhịp đều ({int(diff)}s) nhưng tâm không định. Không cộng điểm."
        else:
            data["streak"] = 0
            msg = f"🔔 Goong... Nhịp {'quá nhanh' if diff < IDEAL_MIN else 'quá chậm'} ({int(diff)}s). Không cộng điểm."
    else:
        msg = "🔔 Goong đầu tiên. Chỉ cần gõ đúng nhịp thở của bạn…\nHít vào… Goong… Thở ra… Goong…"
        data["streak"] = 0

    data["last_gong"] = now
    user_data[user_id] = data

    await update.message.reply_text(msg)
    await send_mood_prompt(update, context)
    if random.random() < ASK_MOMENT_PROB:
        await send_moment_question(update, context)

async def send_mood_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("Nhẹ lòng", callback_data="mood_calm"),
        InlineKeyboardButton("Loạn tâm", callback_data="mood_chaotic"),
        InlineKeyboardButton("Không biết gì cả", callback_data="mood_empty")
    ]]
    await update.message.reply_text(
        "🧘‍♂️ Hít vào... Thở ra... Bạn cảm thấy...?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_moment_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question, options = random.choice(MOMENT_QUESTIONS)
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"moment_{opt}") for opt in options]]
    await update.message.reply_text(
        question,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def daily_checkin(context: ContextTypes.DEFAULT_TYPE):
    for user_id, data in user_data.items():
        now = datetime.now()
        if data.get("last_checkin") and (now - data["last_checkin"]).total_seconds() < CHECK_IN_TIMEOUT:
            continue

        keyboard = [[InlineKeyboardButton(opt, callback_data=f"checkin_{opt}") for opt in CHECKIN_OPTIONS]]
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=CHECKIN_QUESTION,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            data["pending_checkin"] = True
        except:
            pass

async def mood_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = user_data.get(user_id, {})

    if query.data.startswith("mood_"):
        mood = query.data.replace("mood_", "")
        data["mood"] = mood
        await query.answer()
        await query.edit_message_text(f"🙏 Cảm ơn bạn. Tâm trạng ghi nhận: {mood}.")

    elif query.data.startswith("moment_"):
        moment = query.data.replace("moment_", "")
        await query.answer()
        await query.edit_message_text(f"🌬️ Ghi nhận tâm cảnh: {moment}.")

    elif query.data.startswith("checkin_"):
        feeling = query.data.replace("checkin_", "")
        data["last_checkin"] = datetime.now()
        data["pending_checkin"] = False
        await query.answer()
        await query.edit_message_text(f"📖 Cảm ơn bạn đã ghi nhận ngày hôm nay: {feeling}.")

    user_data[user_id] = data

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data.get(user_id, {"karma": 0, "streak": 0, "mood": "-"})
    level = get_level(data["karma"])
    await update.message.reply_text(
        f"🌱 Karma: {data['karma']}\n🧘‍♂️ Chuỗi đúng nhịp: {data['streak']}\n🧭 Tâm trạng gần nhất: {data['mood']}\n🎚 Cấp bậc hiện tại: {level}"
    )

async def check_pending_checkin(context: ContextTypes.DEFAULT_TYPE):
    for user_id, data in user_data.items():
        if data.get("pending_checkin"):
            data["streak"] = 0
            data["pending_checkin"] = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌀 Chào mừng đến với *TBC – Một Cú Gõ Cho Vạn Kiếp Người*\n"
        "Gõ vào /gong để bắt đầu tỉnh thức.\n"
        "Thở đều – gõ đúng nhịp – đừng quên lắng nghe cảm xúc.\n"
        "Mỗi ngày, hãy kể lại một chút về hành trình của bạn."
    )
import asyncio

async def main():
    app = ApplicationBuilder().token("...").build()

    await app.initialize()
    await app.post_init()

    app.add_handler(...)
    ...
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == '__main__':
    asyncio.run(main())
