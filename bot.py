
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from PIL import Image, ImageDraw, ImageFont
import io
import os
import logging

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

user_state = {}
user_temp_data = {}

overlay_options = [
    [InlineKeyboardButton("🛌 Day Off", callback_data='day_off')],
    [InlineKeyboardButton("🏖 Vacation (no date)", callback_data='vacation')],
    [InlineKeyboardButton("🏖 Vacation (with date)", callback_data='vacation_with_date')],
    [InlineKeyboardButton("💼 Business Trip", callback_data='business_trip')],
]

timezone_options = [
    [InlineKeyboardButton("🌎 LATAM (MSK –8)", callback_data='business_trip_latam')],
    [InlineKeyboardButton("🌍 AFRICA (MSK –3)", callback_data='business_trip_africa')],
    [InlineKeyboardButton("🇵🇰 PAKISTAN (MSK +2)", callback_data='business_trip_pakistan')],
]

FONT_PATH = "fonts/YangoText_Bd.ttf"
FONT_SIZE = 120

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose avatar type:", reply_markup=InlineKeyboardMarkup(overlay_options))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "business_trip":
        await query.message.reply_text("Choose a time zone:", reply_markup=InlineKeyboardMarkup(timezone_options))
    elif query.data == "vacation_with_date":
        user_state[user_id] = "vacation_waiting_date"
        await query.message.reply_text("Until what date? (e.g., 15.06)")
    else:
        user_state[user_id] = query.data
        await query.message.reply_text("Now send me your photo.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    current_state = user_state.get(user_id)

    if current_state == "vacation_waiting_date":
        user_state[user_id] = "vacation"
        user_temp_data[user_id] = {"date": update.message.text.strip()}
        await update.message.reply_text("Thanks! Now send me your photo.")
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

        # Crop to square and resize to 1280x1280
        width, height = user_img.size
        min_dim = min(width, height)
        user_img = user_img.crop((
            (width - min_dim) // 2,
            (height - min_dim) // 2,
            (width + min_dim) // 2,
            (height + min_dim) // 2
        ))
        user_img = user_img.resize((1280, 1280))

        overlay_path = f"overlays/{overlay_type}.png"
        if not os.path.exists(overlay_path):
            await update.message.reply_text(f"Overlay '{overlay_type}' not found.")
            return

        overlay = Image.open(overlay_path).convert("RGBA").resize(user_img.size)
        combined = Image.alpha_composite(user_img, overlay)

        if overlay_type == "vacation":
            vacation_data = user_temp_data.get(user_id, {})
            date_text = vacation_data.get("date")
            if date_text:
                draw = ImageDraw.Draw(combined)
                try:
                    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
                except Exception as e:
                    logger.error(f"Font loading error: {e}")
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
        logger.error(f"Failed to process image: {e}")
        await update.message.reply_text("An error occurred while processing your image. Please try again later.")

    # Reset user session
    user_state.pop(user_id, None)
    user_temp_data.pop(user_id, None)

    await update.message.reply_text("Avatar created! Want to try again?", reply_markup=InlineKeyboardMarkup(overlay_options))

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
