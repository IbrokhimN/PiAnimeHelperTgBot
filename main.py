import logging
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "ВАШ_TELEGRAM_BOT_TOKEN"

JIKAN_URL = "https://api.jikan.moe/v4"
ADULT_KEYWORDS = ['''Your bad words list''']
ADULT_GENRES = {'''Your forbiden genres'''}

def contains_adult_keywords(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    for pat in ADULT_KEYWORDS:
        if re.search(pat, t):
            return True
    return False

def is_adult_content(anime: dict) -> bool:
    genres = anime.get("genres", []) or anime.get("demographics", []) or []
    for g in genres:
        name = g.get("name") if isinstance(g, dict) else str(g)
        if name and name in ADULT_GENRES:
            return True

    synopsis = anime.get("synopsis") or ""
    if contains_adult_keywords(synopsis):
        return True

    rating = (anime.get("rating") or "").lower()
    if "rx" in rating or "hentai" in rating:
        return True

    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я аниме-бот 🤖\n\n"
        "Я могу найти информацию об аниме по названию.\n"
        "Просто напиши название аниме, которое хочешь найти!\n\n"
        "Например: Naruto, Attack on Titan, One Piece и т.д."
    )

def search_anime(query):
    try:
        response = requests.get(f"{JIKAN_URL}/anime", params={"q": query, "limit": 5}, timeout=10)
        response.raise_for_status()
        return response.json().get("data", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API: {e}")
        return None

def get_anime_details(anime_id):
    try:
        response = requests.get(f"{JIKAN_URL}/anime/{anime_id}/full", timeout=10)
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

    if results is None:
        await update.message.reply_text("Произошла ошибка при запросе внешнего сервиса. Попробуйте позже.")
        return

    if not results:
        await update.message.reply_text("Ничего не найдено 😢 Попробуйте другое название.")
        return

    if len(results) == 1:
        await send_anime_details(update, context, results[0]['mal_id'])
    else:
        keyboard = []
        for anime in results:
            title = anime.get('title') or "Unknown"
            year = anime.get('year') or 'N/A'
            keyboard.append([InlineKeyboardButton(
                f"{title} ({year})",
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
        if update and getattr(update, "effective_chat", None):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Не удалось получить информацию об аниме 😢")
        else:
            logger.error("Не удалось отправить сообщение: нет chat_id")
        return

    adult = is_adult_content(anime)

    title = anime.get('title') or "Unknown"
    title_jp = anime.get('title_japanese')
    typ = anime.get('type') or 'N/A'
    year = anime.get('year') or 'N/A'
    episodes = anime.get('episodes') or 'N/A'
    score = anime.get('score') or 'N/A'
    status = anime.get('status') or 'N/A'

    message = f"🎌 <b>{title}</b>\n\n"
    if title_jp:
        message += f"🇯🇵 <i>{title_jp}</i>\n\n"

    message += f"📺 <b>Тип:</b> {typ}\n"
    message += f"📅 <b>Год:</b> {year}\n"
    message += f"📊 <b>Эпизоды:</b> {episodes}\n"
    message += f"⭐ <b>Рейтинг:</b> {score}/10\n"
    message += f"👥 <b>Статус:</b> {status}\n\n"

    if adult:
        message += "⚠️ <b>Возрастной контент (18+)</b>\n"
        message += "📖 Описание скрыто, так как содержит материалы для взрослых или описания, " \
                   "которые могут быть несовместимы с правилами платформы.\n\n"
    else:
        synopsis = anime.get('synopsis') or 'Описание отсутствует'
        if len(synopsis) > 1000:
            synopsis = synopsis[:1000] + "..."
        synopsis = re.sub(r"<[^>]+>", "", synopsis)
        message += f"📖 <b>Описание:</b>\n{synopsis}\n\n"

    message += f"🔗 <b>Ссылка на MyAnimeList:</b>\nhttps://myanimelist.net/anime/{anime_id}"

    chat_id = update.effective_chat.id if update and getattr(update, "effective_chat", None) else None
    if not chat_id:
        logger.error("Не могу определить chat_id для отправки сообщения")
        return

    try:
        if not adult and anime.get('images') and anime['images'].get('jpg') and anime['images']['jpg'].get('image_url'):
            image_url = anime['images']['jpg']['image_url']
            await context.bot.send_photo(chat_id=chat_id, photo=image_url, caption=message, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML', disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Ошибка при отправке деталей: {e}")
        try:
            await context.bot.send_message(chat_id=chat_id, text="Произошла ошибка при отправке информации. Попробуйте позже.")
        except Exception as e2:
            logger.error(f"Не удалось отправить резервное сообщение: {e2}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data.startswith('anime_'):
        try:
            anime_id = int(data.split('_')[1])
        except Exception:
            await query.message.reply_text("Неверный идентификатор аниме.")
            return
        await send_anime_details(update, context, anime_id)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Аниме-бот Помощь</b>\n\n"
        "Просто напишите название аниме, и я найду информацию о нём!\n\n"
        "Примеры запросов:\n"
        "- Naruto\n"
        "- Attack on Titan\n"
        "- One Piece\n\n"
        "Я покажу вам описание, рейтинг, год выпуска и ссылку на MyAnimeList!\n\n"
        "Если тайтл содержит контент 18+, описание будет скрыто.",
        parse_mode='HTML'
    )

async def random_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{JIKAN_URL}/random/anime", timeout=10)
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
    try:
        if update and getattr(update, "effective_chat", None):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

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
