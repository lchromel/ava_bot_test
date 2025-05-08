
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from PIL import Image, ImageDraw, ImageFont
import io
import os
import logging
import openai  # библиотека OpenAI для генерации изображения

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

user_state = {}
user_temp_data = {}

main_menu_options = [
    [InlineKeyboardButton("🛌 Day Off", callback_data='day_off')],
    [InlineKeyboardButton("🏖 Vacation", callback_data='vacation_entry')],
    [InlineKeyboardButton("💼 Business Trip", callback_data='business_trip')],
    [InlineKeyboardButton("📆 Public Holidays", callback_data='holidays')],
    [InlineKeyboardButton("✈️ Flight Mode", callback_data='flight')],
    [InlineKeyboardButton("🧪 Test", callback_data='test_city')],
]

vacation_submenu_options = [
    [InlineKeyboardButton("🏖 Vacation (no date)", callback_data='vacation')],
    [InlineKeyboardButton("🏖 Vacation (with date)", callback_data='vacation_with_date')],
]

timezone_options = [
    [InlineKeyboardButton("🌎 LATAM (MSK –8)", callback_data='business_trip_latam')],
    [InlineKeyboardButton("🌍 AFRICA (MSK –3)", callback_data='business_trip_africa')],
    [InlineKeyboardButton("🇵🇰 PAKISTAN (MSK +2)", callback_data='business_trip_pakistan')],
]

FONT_PATH = "fonts/YangoText_Bd.ttf"
FONT_SIZE = 120

# Вставьте свой ключ
openai.api_key = os.getenv("OPENAI_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose avatar type:", reply_markup=InlineKeyboardMarkup(main_menu_options))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "vacation_entry":
        await query.message.reply_text("Vacation mode:", reply_markup=InlineKeyboardMarkup(vacation_submenu_options))
    elif query.data == "business_trip":
        await query.message.reply_text("Choose a time zone:", reply_markup=InlineKeyboardMarkup(timezone_options))
    elif query.data == "vacation_with_date":
        user_state[user_id] = "vacation_waiting_date"
        await query.message.reply_text("Until what date? (e.g., 15.06)")
    elif query.data == "test_city":
        user_state[user_id] = "test_waiting_city"
        await query.message.reply_text("Which city are you flying to?")
    else:
        user_state[user_id] = query.data
        await query.message.reply_text("Now send me your photo.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_state.get(user_id)

    if state == "vacation_waiting_date":
        user_state[user_id] = "vacation"
        user_temp_data[user_id] = {"date": update.message.text.strip()}
        await update.message.reply_text("Thanks! Now send me your photo.")
    elif state == "test_waiting_city":
        user_state[user_id] = "test_waiting_photo"
        user_temp_data[user_id] = {"city": update.message.text.strip()}
        await update.message.reply_text("Great! Now send me your photo.")
    else:
        await update.message.reply_text("Please choose avatar type first: /start")

async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    overlay_type = user_state.get(user_id)

    if not overlay_type:
        await update.message.reply_text("Please choose avatar type first: /start")
        return

    try:
        if update.message.photo:
            photo_file = await update.message.photo[-1].get_file()
        elif update.message.document and update.message.document.mime_type.startswith("image/"):
            photo_file = await update.message.document.get_file()
        else:
            await update.message.reply_text("Please send an image file or photo.")
            return

        photo_bytes = await photo_file.download_as_bytearray()
        user_img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")

        width, height = user_img.size
        min_dim = min(width, height)
        user_img = user_img.crop((
            (width - min_dim) // 2,
            (height - min_dim) // 2,
            (width + min_dim) // 2,
            (height + min_dim) // 2
        ))
        user_img = user_img.resize((1280, 1280))

        if overlay_type == "test_waiting_photo":
            await update.message.reply_text("Generating your avatar...")

            city = user_temp_data.get(user_id, {}).get("city", "a beautiful place")
            prompt = f"Generate a square image in Studio Ghibli style, with the environment designed as if I’m traveling in {city}."

            response = openai.Image.create(
                prompt=prompt,
                n=1,
                size="512x512"
            )
            img_url = response["data"][0]["url"]
            import requests
            ghibli_image = Image.open(io.BytesIO(requests.get(img_url).content)).convert("RGBA").resize((1280, 1280))

            overlay_path = "overlays/vacation.png"
            overlay = Image.open(overlay_path).convert("RGBA").resize((1280, 1280))
            combined = Image.alpha_composite(ghibli_image, overlay)

        else:
            overlay_path = f"overlays/{overlay_type}.png"
            overlay = Image.open(overlay_path).convert("RGBA").resize(user_img.size)
            combined = Image.alpha_composite(user_img, overlay)

            if overlay_type == "vacation":
                vacation_data = user_temp_data.get(user_id, {})
                date_text = vacation_data.get("date")
                if date_text:
                    draw = ImageDraw.Draw(combined)
                    try:
                        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
                    except:
                        font = ImageFont.load_default()
                    text = f"Till {date_text}"
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    x = (combined.width - text_width) // 2
                    y = int(combined.height * 0.78)
                    draw.text((x+2, y+2), text, font=font, fill="black")
                    draw.text((x, y), text, font=font, fill="white")

        output = io.BytesIO()
        output.name = "avatar.png"
        combined.save(output, "PNG")
        output.seek(0)

        await update.message.reply_document(document=InputFile(output), filename="avatar.png")

    except Exception as e:
        logger.error(f"Image generation error: {e}")
        await update.message.reply_text("Something went wrong. Please try again later.")

    user_state.pop(user_id, None)
    user_temp_data.pop(user_id, None)

    await update.message.reply_text("Avatar created! Want to try again?", reply_markup=InlineKeyboardMarkup(main_menu_options))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception occurred:", exc_info=context.error)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, image_handler))
    app.add_error_handler(error_handler)

    app.run_polling()

if __name__ == '__main__':
    main()
