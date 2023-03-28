import logging
import os
import time
import sys

import requests
import telegram
from logging import StreamHandler

from dotenv import load_dotenv

from exceptions import EnvVariableDoesNotExist, ResponseIncorrect
from exceptions import MessageNotSent, StatusNotExpected

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Checks that the required environment variables are set."""
    if not PRACTICUM_TOKEN:
        message = ('Отсутствует обязательная переменная окружения: '
                   'PRACTICUM_TOKEN. Программа принудительно остановлена. ')
        logger.critical(message)
        raise EnvVariableDoesNotExist(message)
    if not TELEGRAM_CHAT_ID:
        message = ('Отсутствует обязательная переменная окружения: '
                   'TELEGRAM_CHAT_ID. Программа принудительно остановлена. ')
        logger.critical(message)
        raise EnvVariableDoesNotExist(message)
    if not TELEGRAM_TOKEN:
        message = ('Отсутствует обязательная переменная окружения: '
                   'TELEGRAM_TOKEN. Программа принудительно остановлена.')
        logger.critical(message)
        raise EnvVariableDoesNotExist(message)


def send_message(bot, message):
    """
    Sends a message to a Telegram chat using the specified bot.

    Args:
        bot (telegram.Bot): The Telegram bot to use.
        message (str): The message to send.
    """
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except MessageNotSent:
        message = 'Сообщение не удалось отправить'
        logger.error(message)
        raise MessageNotSent(message)


def get_api_answer(timestamp):
    """Makes a request homework_statuses to an API Practicum.

    Args:
        timestamp (int): The UNIX timestamp to use in the API request.

    Returns:
        dict: The JSON response from the API.
    """
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=headers, params=payload)
    if response.status_code == 200:
        try:
            homework_statuses = response.json()
        except ValueError:
            message = 'Ошибка декодирования JSON'
            logger.error(message)
            raise ResponseIncorrect(message)
        else:
            return homework_statuses
    else:
        message = 'Я.Практикум недоступен'
        logger.error(message)
        raise ResponseIncorrect(message)


def check_response(response):
    """
    Checks the structure of the response JSON homework_statuses.

    Args:
        response (dict): JSON response received from Practicum API.
    """
    if not (isinstance(response, dict)
            and "homeworks" in response and "current_date" in response):
        message = f'Я.Практикум вернул неожиданную структуру json: {response}'
        logger.error(message)
        raise ResponseIncorrect(message)


def parse_status(homework):
    """
    Parses the status of a homework_statuses.

    Args:
        homework (dict): A dictionary about a homework submission.

    Returns:
        str: A message describing the status of the homework submission.
    """
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        message = f'Я.Практикум вернул неожиданный статус: {status}'
        logger.error(message)
        raise StatusNotExpected(message)


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            homework_statuses = get_api_answer(timestamp - RETRY_PERIOD)
            check_response(homework_statuses)
            if homework_statuses["homeworks"]:
                last_homework = homework_statuses["homeworks"][0]
                message = parse_status(last_homework)
                send_message(bot, message)
                logger.debug(f'Отправлено сообщение: {message}')
            else:
                logger.debug('Сообщений не найдено')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
