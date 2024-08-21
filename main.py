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


async def start(update: Update, context: CallbackContext):
    keyboard = [
        [
            InlineKeyboardButton("Accept locations", callback_data='accept'),
            InlineKeyboardButton("Provide location", callback_data='provide'),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('What you wanna do?', reply_markup=reply_markup)



async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if query.data == 'accept':
        save_to_database(query.message.chat.id, query.message.chat.username)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Noted!")
    elif query.data == 'provide':
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Whom would you like to share?")
        return contact_exchange


async def process_location(update: Update, context: CallbackContext):
    if update.message is None:
        return
    user_location = update.message.location
    if user_location is None or user_location.live_period is None:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Please share your live location.")
    else:
        await send_live_location(user_location, update, context)

async def send_live_location(location, update, context: CallbackContext):
    lon, lat = location.longitude, location.latitude
    gdf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs='EPSG:4326')
    gdf = gdf.to_crs(epsg=4326)  # Make sure CRS is in WGS84
    loop = asyncio.get_event_loop()
    # Run the I/O-bound operation in an executor to avoid blocking the event loop
    world = await loop.run_in_executor(None, gpd.read_file, "ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp")

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
    else:
        await context.bot.send_message(chat_id=update.message.chat_id, text="Country not identified.")


async def contact_exchange(update: Update, context: CallbackContext):
    username = update.message.text
    chat_id = check_in_database(username)
    if chat_id:
        context.user_data['chat_id'] = chat_id
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Please share your live location.')
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Please enter username again or ask user to reenter our list.')


async def location_share(update: Update, context: CallbackContext):
    location_message = update.edited_message
    if location_message:
        location = location_message.location
        if location.live_period:
            point = geocode({"type": "Point", "coordinates": [location.longitude, location.latitude]},
                            provider='nominatim', user_agent='myGeocoder')
            await context.bot.send_message(chat_id=context.user_data['chat_id'],
                                     text=f'The country is {point["ADDRESS"]["country"]}')
            await context.bot.send_message(chat_id=update.effective_chat.id, text='Country sent.')


def main():
    app = ApplicationBuilder().token(os.getenv('TELEGRAM')).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), contact_exchange))
    app.add_handler(MessageHandler(filters.LOCATION, process_location))

    app.run_polling()


if __name__ == '__main__':
    main()
