from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from PIL import Image, ImageDraw, ImageFont
import openai
import io
import os
import logging
import requests

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

user_state = {}

FONT_PATH = "fonts/YangoText_Bd.ttf"
FONT_SIZE = 120
VACATION_OVERLAY_PATH = "overlays/vacation2.png"

main_menu_options = [
    [InlineKeyboardButton("🛌 Day Off", callback_data='day_off')],
    [InlineKeyboardButton("🏖 Vacation", callback_data='vacation')],
    [InlineKeyboardButton("🎨 AI Vacation", callback_data='ai_vacation')],
    [InlineKeyboardButton("💼 Business Trip", callback_data='business_trip')],
    [InlineKeyboardButton("📆 Public Holidays", callback_data='holidays')],
    [InlineKeyboardButton("✈️ Flight Mode", callback_data='flight')],
]

timezone_options = [
    [InlineKeyboardButton("🌎 LATAM (MSK –8)", callback_data='business_trip_latam')],
    [InlineKeyboardButton("🌍 AFRICA (MSK –3)", callback_data='business_trip_africa')],
    [InlineKeyboardButton("🇵🇰 PAKISTAN (MSK +2)", callback_data='business_trip_pakistan')],
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose avatar type:", reply_markup=InlineKeyboardMarkup(main_menu_options))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "business_trip":
        await query.message.reply_text("Choose a time zone:", reply_markup=InlineKeyboardMarkup(timezone_options))
    elif query.data == "ai_vacation":
        user_state[user_id] = query.data
        await query.message.reply_text("Where are you going to?")
    else:
        user_state[user_id] = query.data
        await update.message.reply_text("Now send me your photo.")

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

        overlay_path = f"overlays/{overlay_type}.png" if overlay_type != "vacation" else VACATION_OVERLAY_PATH
        if not os.path.exists(overlay_path):
            await update.message.reply_text(f"Overlay '{overlay_type}' not found.")
            return

        overlay = Image.open(overlay_path).convert("RGBA").resize(user_img.size)
        combined = Image.alpha_composite(user_img, overlay)

        output = io.BytesIO()
        output.name = "avatar.png"
        combined.save(output, "PNG")
        output.seek(0)

        await update.message.reply_document(document=InputFile(output), filename="avatar.png")

    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        await update.message.reply_text("An error occurred while processing your image. Please try again later.")

    user_state.pop(user_id, None)
    await update.message.reply_text("Avatar created! Want to try again?", reply_markup=InlineKeyboardMarkup(main_menu_options))

async def generate_ai_image(location: str) -> Image.Image:
    try:
        prompt = f"Portrait of a joyful tourist animal character visiting {location}. The animal is native or symbolic to the destination, but varies each time. The character wears stylish, lokal designer-inspired clothing with unique cultural references. Surrounded by a two unexpected, whimsical travel items or accessories — playful, imaginative, and different in every generation. Pixar-style 3D rendering, highly expressive face. Solid bright red background. Square 1:1 avatar format."
        
        response = client.images.generate(
            model="gpt-4-vision-preview",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        image_url = response.data[0].url
        response = requests.get(image_url)
        return Image.open(io.BytesIO(response.content)).convert("RGBA")
    except Exception as e:
        logger.error(f"Failed to generate AI image: {e}")
        raise

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_state.get(user_id)

    if state == "ai_vacation":
        try:
            location = update.message.text.strip()
            if not location:
                await update.message.reply_text("Please provide a valid location (city or country).")
                return
                
            await update.message.reply_text(f"Generating your vacation avatar for {location}... This may take a moment.")
            
            # Generate AI image
            user_img = await generate_ai_image(location)
            
            # Resize to match our standard size
            user_img = user_img.resize((1280, 1280))
            
            # Apply overlay
            overlay = Image.open(VACATION_OVERLAY_PATH).convert("RGBA").resize(user_img.size)
            combined = Image.alpha_composite(user_img, overlay)
            
            # Save and send
            output = io.BytesIO()
            output.name = "avatar.png"
            combined.save(output, "PNG")
            output.seek(0)
            
            await update.message.reply_document(document=InputFile(output), filename="avatar.png")
            user_state.pop(user_id, None)
            await update.message.reply_text("Avatar created! Want to try again?", reply_markup=InlineKeyboardMarkup(main_menu_options))
            
        except Exception as e:
            logger.error(f"Failed to process AI image: {e}")
            await update.message.reply_text("An error occurred while generating your image. Please try again later.")
            user_state.pop(user_id, None)
            await update.message.reply_text("Choose avatar type:", reply_markup=InlineKeyboardMarkup(main_menu_options))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception occurred:", exc_info=context.error)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, image_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)

    app.run_polling()

if __name__ == '__main__':
    main()
