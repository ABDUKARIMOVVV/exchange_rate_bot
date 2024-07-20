import aiohttp
import asyncio
import xml.etree.ElementTree as ET
import redis
from datetime import datetime
import aioschedule as schedule
import logging

logging.basicConfig(level=logging.INFO)


async def fetch_currency_rates():
	url = 'https://www.cbr.ru/scripts/XML_daily.asp'
	async with aiohttp.ClientSession() as session:
		async with session.get(url) as response:
			return await response.text()


def parse_xml(xml_content):
	root = ET.fromstring(xml_content)
	rates = {}
	for valute in root.findall('Valute'):
		code = valute.find('CharCode').text
		value = float(valute.find('Value').text.replace(',', '.'))
		rates[code] = value
	return rates


def update_redis(rates):
	r = redis.Redis(host='redis', port=6379, db=0)
	for code, value in rates.items():
		r.set(f"currency:{code}", value)
	r.set("last_update", datetime.now().isoformat())


async def update_job():
	logging.info("Updating currency rates...")
	try:
		xml_content = await fetch_currency_rates()
		rates = parse_xml(xml_content)
		update_redis(rates)
		logging.info("Currency rates updated successfully.")
	except Exception as e:
		logging.error(f"Error updating currency rates: {e}")


async def main():
	logging.info("Currency updater started.")
	
	# Выполняем обновление сразу при запуске
	await update_job()
	
	# Планируем обновление каждые 10 минут
	schedule.every(10).minutes.do(update_job)
	
	while True:
		await schedule.run_pending()
		await asyncio.sleep(1)


if __name__ == '__main__':
	asyncio.run(main())