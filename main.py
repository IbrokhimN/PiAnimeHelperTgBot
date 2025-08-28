import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "ВАШ_TELEGRAM_BOT_TOKEN"

JIKAN_URL = "https://api.jikan.moe/v4"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я аниме-бот 🤖\n\n"
        "Я могу найти информацию об аниме по названию.\n"
        "Просто напиши название аниме, которое хочешь найти!\n\n"
        "Например: Naruto, Attack on Titan, One Piece и т.д."
    )

def search_anime(query):
    try:
        response = requests.get(f"{JIKAN_URL}/anime", params={"q": query, "limit": 5})
        response.raise_for_status()
        return response.json().get("data", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API: {e}")
        return None

def get_anime_details(anime_id):
    try:
        response = requests.get(f"{JIKAN_URL}/anime/{anime_id}/full")
        response.raise_for_status()
        return response.json().get("data")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе деталей аниме: {e}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if len(query) < 3:
        await update.message.reply_text("Пожалуйста, введите название аниме длиннее 2 символов.")
        return
    
    await update.message.reply_text("🔍 Ищу аниме...")
    
    results = search_anime(query)
    
    if not results:
        await update.message.reply_text("Ничего не найдено 😢 Попробуйте другое название.")
        return
    
    if len(results) == 1:
        await send_anime_details(update, context, results[0]['mal_id'])
    else:
        keyboard = []
        for anime in results:
            keyboard.append([InlineKeyboardButton(
                f"{anime['title']} ({anime.get('year', 'N/A')})", 
                callback_data=f"anime_{anime['mal_id']}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Вот что я нашёл. Выберите аниме:",
            reply_markup=reply_markup
        )

async def send_anime_details(update: Update, context: ContextTypes.DEFAULT_TYPE, anime_id):
    anime = get_anime_details(anime_id)
    
    if not anime:
        await update.message.reply_text("Не удалось получить информацию об аниме 😢")
        return
    
    message = f"🎌 <b>{anime['title']}</b>\n\n"
    
    if anime.get('title_japanese'):
        message += f"🇯🇵 <i>{anime['title_japanese']}</i>\n\n"
    
    message += f"📺 <b>Тип:</b> {anime.get('type', 'N/A')}\n"
    message += f"📅 <b>Год:</b> {anime.get('year', 'N/A')}\n"
    message += f"📊 <b>Эпизоды:</b> {anime.get('episodes', 'N/A')}\n"
    message += f"⭐ <b>Рейтинг:</b> {anime.get('score', 'N/A')}/10\n"
    message += f"👥 <b>Статус:</b> {anime.get('status', 'N/A')}\n\n"
    
    synopsis = anime.get('synopsis', 'Описание отсутствует')
    if len(synopsis) > 1000:
        synopsis = synopsis[:1000] + "..."
    message += f"📖 <b>Описание:</b>\n{synopsis}\n\n"
    
    message += f"🔗 <b>Ссылка на MyAnimeList:</b>\nhttps://myanimelist.net/anime/{anime_id}"
    
    if anime.get('images') and anime['images'].get('jpg') and anime['images']['jpg'].get('image_url'):
        try:
            await update.message.reply_photo(
                photo=anime['images']['jpg']['image_url'],
                caption=message,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Не удалось отправить изображение: {e}")
            await update.message.reply_text(message, parse_mode='HTML')
    else:
        await update.message.reply_text(message, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('anime_'):
        anime_id = int(query.data.split('_')[1])
        await send_anime_details(query, context, anime_id)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Аниме-бот Помощь</b>\n\n"
        "Просто напишите название аниме, и я найду информацию о нём!\n\n"
        "Примеры запросов:\n"
        "- Naruto\n"
        "- Attack on Titan\n"
        "- One Piece\n"
        "- My Hero Academia\n\n"
        "Я покажу вам описание, рейтинг, год выпуска и ссылку на MyAnimeList!",
        parse_mode='HTML'
    )

async def random_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{JIKAN_URL}/random/anime")
        response.raise_for_status()
        anime = response.json().get('data')
        
        if anime:
            await send_anime_details(update, context, anime['mal_id'])
        else:
            await update.message.reply_text("Не удалось получить случайное аниме 😢")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе случайного аниме: {e}")
        await update.message.reply_text("Произошла ошибка при поиске случайного аниме.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Исключение при обработке обновления:", exc_info=context.error)
    
    if update and update.message:
        await update.message.reply_text(
            "Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
        )

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("random", random_anime))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.add_error_handler(error_handler)
    
    application.run_polling()

if __name__ == '__main__':
    main()
