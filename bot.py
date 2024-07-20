import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
import redis
import os
import requests
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv('BOT_TOKEN')

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
r = redis.Redis(host='redis', port=6379, db=0)

CBR_URL = 'https://www.cbr.ru/scripts/XML_daily.asp'


def fetch_exchange_rates():
    try:
        response = requests.get(CBR_URL)
        response.raise_for_status()  # Проверяет статус-код ответа
    except requests.RequestException as e:
        logging.error(f"Request failed: {e}")
        return

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        logging.error(f"Failed to parse XML: {e}")
        return

    rates = {"RUB": 1.0}
    for currency in root.findall('Valute'):
        try:
            char_code = currency.find('CharCode').text
            value = float(currency.find('Value').text.replace(',', '.'))
            nominal = float(currency.find('Nominal').text.replace(',', '.'))
            rates[char_code] = value / nominal
        except (AttributeError, ValueError) as e:
            logging.error(f"Error processing currency data: {e}")

    last_update = root.find('Date')
    if last_update is not None:
        r.set("last_update", last_update.text)
    else:
        logging.error("Date element not found in XML response")

    for key, value in rates.items():
        r.set(f"currency:{key}", value)



@dp.message_handler(commands=['start', 'help'])
async def start(message: types.Message):
    await message.reply(
        "Привет! Я бот для отображения курсов валют. Используй /exchange для конвертации или /rates для просмотра курсов."
    )


@dp.message_handler(commands=['exchange'])
async def exchange(message: types.Message):
    logging.info(f"Received exchange command: {message.text}")
    args = message.get_args().split()
    if len(args) != 3:
        await message.reply("Используйте формат : /exchange USD RUB 10")
        return

    from_currency, to_currency, amount = args
    logging.info(f"Parsed args: {from_currency}, {to_currency}, {amount}")
    try:
        amount = float(amount)
    except ValueError:
        await message.reply("Неверный формат суммы")
        return

    from_rate = float(r.get(f"currency:{from_currency}") or 1)
    to_rate = float(r.get(f"currency:{to_currency}") or 1)
    logging.info(f"Rates: {from_currency}={from_rate}, {to_currency}={to_rate}")

    result = (amount * from_rate) / to_rate

    response = f"{amount} {from_currency} = {result:.2f} {to_currency}"
    logging.info(f"Sending response: {response}")
    await message.reply(response)


@dp.message_handler(commands=['rates'])
async def rates(message: types.Message):
    currencies = ["USD", "EUR", "GBP"]
    rates = []
    for currency in currencies:
        rate = r.get(f"currency:{currency}")
        if rate:
            rates.append(f"{currency}: {float(rate):.2f}")

    last_update = r.get("last_update")
    response = "Курсы валют:\n" + "\n".join(rates)
    if last_update:
        response += f"\n\nПоследнее обновление: {last_update.decode()}"

    await message.reply(response)


@dp.message_handler(commands=['debug'])
async def debug(message: types.Message):
    keys = r.keys('currency:*')
    debug_info = "Debug info:\n"
    for key in keys:
        value = r.get(key)
        debug_info += f"{key.decode()}: {value.decode()}\n"
    await message.reply(debug_info)


@dp.errors_handler()
async def errors_handler(update, exception):
    logging.exception(f"Exception occurred: {exception}")
    return True


if __name__ == '__main__':
    logging.info("Fetching initial exchange rates...")
    fetch_exchange_rates()
    logging.info("Starting bot...")
    executor.start_polling(dp, skip_updates=True)
