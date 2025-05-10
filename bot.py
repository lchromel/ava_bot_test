from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from PIL import Image, ImageDraw, ImageFont
import openai
import io
import os
import logging
import requests
from datetime import datetime

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
VACATION_OVERLAY_PATH = "overlays/vacation.png"

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

def is_valid_date(date_str: str) -> bool:
    try:
        # Only accept DD.MM format
        date = datetime.strptime(date_str, '%d.%m')
        # Create a date object for the current year
        current_year = datetime.now().year
        full_date = datetime(current_year, date.month, date.day)
        # Check if date is not in the past
        if full_date.date() < datetime.now().date():
            return False
        return True
    except ValueError:
        return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "business_trip":
        await query.message.reply_text("Choose a time zone:", reply_markup=InlineKeyboardMarkup(timezone_options))
    elif query.data == "vacation":
        user_state[user_id] = {"type": query.data, "step": "date"}
        await query.message.reply_text("When are you going? (Please enter the date in DD.MM format, e.g., 25.12)")
    elif query.data == "ai_vacation":
        user_state[user_id] = query.data
        await query.message.reply_text("Where are you going to?")
    else:
        user_state[user_id] = query.data
        await query.message.reply_text("Now send me your photo.")

async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_state.get(user_id)

    if not state:
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

        overlay_type = state["type"] if isinstance(state, dict) else state
        overlay_path = f"overlays/{overlay_type}.png" if overlay_type != "vacation" else VACATION_OVERLAY_PATH
        if not os.path.exists(overlay_path):
            await update.message.reply_text(f"Overlay '{overlay_type}' not found.")
            return

        overlay = Image.open(overlay_path).convert("RGBA").resize(user_img.size)
        combined = Image.alpha_composite(user_img, overlay)

        # Add text overlay for vacation
        if isinstance(state, dict) and state["type"] == "vacation" and state.get("date"):
            draw = ImageDraw.Draw(combined)
            try:
                font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
            except Exception as e:
                logger.error(f"Font loading error: {e}")
                font = ImageFont.load_default()
            
            text = f"Till {state['date']}"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            x = (combined.width - text_width) // 2
            y = int(combined.height * 0.78)
            
            # Add shadow effect
            draw.text((x+2, y+2), text, font=font, fill="black")
            draw.text((x, y), text, font=font, fill="white")

        output = io.BytesIO()
        output.name = "avatar.png"
        combined.save(output, "PNG")
        output.seek(0)

        await update.message.reply_document(document=InputFile(output), filename="avatar.png")

        if isinstance(state, dict) and state["type"] == "vacation":
            await update.message.reply_text(f"Vacation avatar created for {state['date']}! Want to try again?", reply_markup=InlineKeyboardMarkup(main_menu_options))
        else:
            await update.message.reply_text("Avatar created! Want to try again?", reply_markup=InlineKeyboardMarkup(main_menu_options))

    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        await update.message.reply_text("An error occurred while processing your image. Please try again later.")

    user_state.pop(user_id, None)

async def generate_ai_image(location: str) -> Image.Image:
    try:
        prompt = f"Portrait of a joyful tourist animal character visiting {location}. The animal is native or symbolic to the destination, but varies each time. The character wears stylish, lokal designer-inspired clothing with unique cultural references. Surrounded by a two unexpected, whimsical travel items or accessories — playful, imaginative, and different in every generation. Pixar-style 3D rendering, highly expressive face. Solid bright red background. Square 1:1 avatar format."
        
        logger.info(f"Generating AI image for location: {location}")
        logger.info(f"Using prompt: {prompt}")
        
        try:
            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="1024x1024",
                quality="medium",
                n=1,
            )
            logger.info(f"API Response: {response}")
        except Exception as api_error:
            logger.error(f"API Error: {str(api_error)}")
            raise ValueError(f"API Error: {str(api_error)}")
        
        if not response:
            logger.error("Empty response from API")
            raise ValueError("Empty response from API")
            
        if not hasattr(response, 'data'):
            logger.error(f"Response has no data attribute. Response: {response}")
            raise ValueError("Invalid response format: no data attribute")
            
        if not response.data:
            logger.error("Response data is empty")
            raise ValueError("No image data in response")
            
        if not response.data[0]:
            logger.error("First data item is empty")
            raise ValueError("Invalid data format in response")
            
        if not hasattr(response.data[0], 'url'):
            logger.error(f"Data item has no URL. Data: {response.data[0]}")
            raise ValueError("No URL in response data")
            
        image_url = response.data[0].url
        if not image_url:
            logger.error("URL is empty")
            raise ValueError("Empty URL in response")
            
        logger.info(f"Generated image URL: {image_url}")
        
        try:
            response = requests.get(image_url, timeout=120)
            if response.status_code != 200:
                logger.error(f"Failed to download image. Status code: {response.status_code}")
                raise ValueError(f"Failed to download image: HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise ValueError(f"Failed to download image: {str(e)}")
            
        return Image.open(io.BytesIO(response.content)).convert("RGBA")
    except Exception as e:
        logger.error(f"Failed to generate AI image: {str(e)}")
        raise

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_state.get(user_id)

    if not state:
        return

    if isinstance(state, dict) and state["type"] == "vacation":
        if state["step"] == "date":
            date_str = update.message.text.strip()
            if not is_valid_date(date_str):
                await update.message.reply_text("Please enter a valid future date in DD.MM format (e.g., 25.12)")
                return
            
            user_state[user_id] = {"type": "vacation", "step": "photo", "date": date_str}
            await update.message.reply_text("Now send me your photo.")

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
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set")
        return
        
    app = ApplicationBuilder().token(token).connect_timeout(30.0).read_timeout(30.0).write_timeout(30.0).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, image_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)

    logger.info("Bot started successfully")
    app.run_polling()

if __name__ == '__main__':
    main()
