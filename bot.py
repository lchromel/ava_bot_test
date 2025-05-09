
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from PIL import Image, ImageDraw, ImageFont
import openai
import io
import os
import logging
import requests

# Конфигурация OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# Telegram logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

user_state = {}
user_temp_data = {}

FONT_PATH = "fonts/YangoText_Bd.ttf"
FONT_SIZE = 120

main_menu_options = [
    [InlineKeyboardButton("🛌 Day Off", callback_data='day_off')],
    [InlineKeyboardButton("🏖 Vacation", callback_data='vacation_entry')],
    [InlineKeyboardButton("💼 Business Trip", callback_data='business_trip')],
    [InlineKeyboardButton("📆 Public Holidays", callback_data='holidays')],
    [InlineKeyboardButton("✈️ Flight Mode", callback_data='flight')],
    [InlineKeyboardButton("🧪 Test", callback_data='test_city')],
]

vacation_overlay_path = "overlays/vacation2.png"

def is_valid_city_country(text: str) -> bool:
    return "," in text and len(text.split(",")) == 2 and all(part.strip() for part in text.split(","))

def optimize_prompt_with_gpt4(raw_prompt: str) -> str:
    messages = [
        {"role": "system", "content": "You are a prompt engineer for DALL·E 3. Rewrite the input to maximize visual detail and quality."},
        {"role": "user", "content": raw_prompt}
    ]
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages,
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

def generate_ghibli_image(prompt: str) -> Image.Image:
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1
    )
    img_url = response.data[0].url
    img_data = requests.get(img_url).content
    return Image.open(io.BytesIO(img_data)).convert("RGBA")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose avatar type:", reply_markup=InlineKeyboardMarkup(main_menu_options))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "test_city":
        user_state[user_id] = "test_waiting_location"
        await query.message.reply_text("Please enter city and country (e.g., Tokyo, Japan):")
    else:
        await query.message.reply_text("Feature in development.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_state.get(user_id)

    if state == "test_waiting_location":
        location = update.message.text.strip()
        if not is_valid_city_country(location):
            await update.message.reply_text("❌ Format must be: City, Country (e.g., Tokyo, Japan)")
            return

        await update.message.reply_text("🧠 Generating your avatar... please wait a moment!")

        # Формируем промпт
        base_prompt = (
            f"Portrait of a joyful tourist animal character visiting {location}. "
            "The animal is native or symbolic to the destination, but varies each time. "
            "The character wears stylish, lokal designer-inspired clothing with unique cultural references. "
            "Surrounded by two unexpected, whimsical travel items or accessories — playful, imaginative, and different in every generation. "
            "Pixar-style 3D rendering, highly expressive face. Solid bright red background. Square 1:1 avatar format."
        )

        try:
            enhanced_prompt = optimize_prompt_with_gpt4(base_prompt)
            img = generate_ghibli_image(enhanced_prompt)

            # Добавим vacation-оверлей
            if os.path.exists(vacation_overlay_path):
                overlay = Image.open(vacation_overlay_path).convert("RGBA").resize(img.size)
                img = Image.alpha_composite(img, overlay)

            output = io.BytesIO()
            output.name = "avatar.png"
            img.save(output, "PNG")
            output.seek(0)

            await update.message.reply_document(document=InputFile(output), filename="avatar.png")
        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            await update.message.reply_text("❌ Something went wrong during generation. Please try again later.")

        user_state.pop(user_id, None)
        await update.message.reply_text("Want to try again?", reply_markup=InlineKeyboardMarkup(main_menu_options))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception occurred:", exc_info=context.error)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
    app.add_error_handler(error_handler)

    app.run_polling()

if __name__ == '__main__':
    main()
