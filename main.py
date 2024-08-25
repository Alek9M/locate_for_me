import asyncio
import logging
import os

from shapely import Point
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    filters,
    InlineQueryHandler,
    CallbackContext,
    CallbackQueryHandler,
    ApplicationBuilder
)
from geopandas.tools import geocode
from aws import save_to_database, check_in_database
import geopandas as gpd
from dotenv import load_dotenv

load_dotenv('.env')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
LOGGER = logging.getLogger(__name__)

RUS = {
    'please_share': 'Пожалуйста поделитесь Вашей *живой* локацией',
    'share_with_whom': "С кем Вы хотите поделиться страной?",
    'no_receiver': 'Пожалуйста, введите имя пользователя еще раз или попросите пользователя перезапустить список получателей.',
    'unknown_location': "Страна не определена.",
    'registered': "Теперь Вы сможете получать страны!",
    'please_share_again': 'Пожалуйста поделитесь Вашей **живой** локацией, Вы отправили __обычную__ локацию',
    'language_set': 'Ваши настройки языка сохранены'
}

ENG = {
    'please_share': 'Please share your *live* location',
    'please_share_again': 'Please share your *live* location, you sent a __regular__ location',
    'share_with_whom': "Who would you like to share your country with?",
    'no_receiver': 'Please enter username again or ask user to reenter our receivers list.',
    'unknown_location': "Country not identified.",
    'registered': "You will now be able to receive countries!",
    'language_set': 'Your language settings are saved'
}


async def start(update: Update, context: CallbackContext):
    keyboard = [
        [
            InlineKeyboardButton("Accept locations", callback_data='accept'),
            InlineKeyboardButton("Provide location", callback_data='provide'),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('What you wanna do?', reply_markup=reply_markup)


async def select_language(update: Update, context: CallbackContext):
    keyboard = [
        [
            InlineKeyboardButton("English", callback_data='ENG'),
            InlineKeyboardButton("Русский", callback_data='RUS'),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Please select language', reply_markup=reply_markup)


async def set_language(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if query.data == 'ENG':
        context.user_data['language'] = ENG
    elif query.data == 'RUS':
        context.user_data['language'] = RUS
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=get_text('language_set', context))
    await start_sharing(update, context)


def get_text(key: str, context: CallbackContext):
    language = context.user_data.get('language')
    if language == RUS:
        return RUS[key]
    return ENG[key]


async def start_receiving(update: Update, context: CallbackContext):
    await _start_receiving(context, update.message.chat.id, update.message.chat.username)


async def _start_receiving(context: CallbackContext, chat_id: int, username: str):
    save_to_database(chat_id, username.lower())
    await context.bot.send_message(chat_id=chat_id,
                                   text=get_text('registered', context))


async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if query.data == 'accept':
        await _start_receiving(context, query.message.chat.id, query.message.chat.username)
    elif query.data == 'provide':
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=get_text('share_with_whom', context))
        return contact_exchange


async def process_location(update: Update, context: CallbackContext):
    if update.message is None:
        return
    user_location = update.message.location
    if user_location is None or user_location.live_period is None:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=get_text('please_share_again', context), parse_mode='MarkdownV2')
    else:
        await send_live_location(user_location, update, context)


async def send_live_location(location, update, context: CallbackContext):
    lon, lat = location.longitude, location.latitude
    await context.bot.send_message(chat_id=update.message.chat_id,
                                   text=f"Locating...")
    gdf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs='EPSG:4326')
    gdf = gdf.to_crs(epsg=4326)  # Make sure CRS is in WGS84
    loop = asyncio.get_event_loop()
    # Run the I/O-bound operation in an executor to avoid blocking the event loop
    world = await loop.run_in_executor(None, gpd.read_file, f"{os.getenv('MAP_PATH')}/ne_110m_admin_0_countries.shp")

    # Run the spatial join in the executor as well since it can be CPU-intensive
    point_in_poly = await loop.run_in_executor(
        None,
        lambda: gpd.sjoin(gdf, world, how="inner", predicate='intersects')
    )

    if not point_in_poly.empty:
        country = point_in_poly.iloc[0]['NAME']
        recipient_chat_id = context.user_data.get('chat_id')
        if recipient_chat_id:
            await context.bot.send_message(chat_id=recipient_chat_id,
                                           text=f"@{update.message.chat.username} is in {country}.")
            context.user_data['chat_id'] = None
            await context.bot.send_message(chat_id=update.message.chat_id,
                                           text=f"Your country ({country}) was shared")
    else:
        await context.bot.send_message(chat_id=update.message.chat_id, text=get_text('unknown_location'))


async def contact_exchange(update: Update, context: CallbackContext):
    username = update.message.text.strip('@'.lower())
    chat_id = check_in_database(username)
    if chat_id:
        context.user_data['chat_id'] = chat_id
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=get_text('please_share', context), parse_mode='MarkdownV2')
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=get_text('no_receiver', context))


async def start_sharing(update: Update, context: CallbackContext):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=get_text('share_with_whom', context))
    return contact_exchange


def main():
    app = ApplicationBuilder().token(os.getenv('TELEGRAM')).build()
    app.add_handler(CommandHandler('start', start_sharing))
    app.add_handler(CommandHandler('register', start_receiving))
    app.add_handler(CommandHandler('language', select_language))
    app.add_handler(CallbackQueryHandler(set_language))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), contact_exchange))
    app.add_handler(MessageHandler(filters.LOCATION, process_location))

    app.run_polling()


if __name__ == '__main__':
    main()
