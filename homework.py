import logging
import os
import time
import sys

import requests
import telegram
from http import HTTPStatus
from logging import StreamHandler

from dotenv import load_dotenv

from exceptions import WrongAPIResponse
from exceptions import MessageNotSent, StatusNotExpected

from typing import Dict


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
    """
    Checks that the required environment variables are set.

    Returns:
        bool: True if all env variables have value
    """
    tokens = (PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN)
    return all(tokens)


def send_message(bot, message):
    """
    Sends a message to a Telegram chat using the specified bot.

    Args:
        bot (telegram.Bot): The Telegram bot to use.
        message (str): The message to send.
    """
    try:
        logger.debug(f'Отправка сообщения: {message}')
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except telegram.error.TelegramError:
        message = 'Сообщение не удалось отправить'
        logger.error(message)
        raise MessageNotSent(message)
    else:
        logger.debug('Отправлено сообщение')


def get_api_answer(timestamp):
    """Makes a request homework_statuses to an API Practicum.

    Args:
        timestamp (int): The UNIX timestamp to use in the API request.

    Returns:
        dict: The JSON response from the API.
    """
    request_params = {
        'url': ENDPOINT,
        'headers': {'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
        'params': {'from_date': timestamp}
    }
    try:
        logging.info(
            (
                'Начинаем подключение к эндпоинту {url}, с параметрами'
                ' headers = {headers} ;params= {params}.'
            ).format(**request_params)
        )
        response = requests.get(**request_params)
    except Exception as error:
        raise ConnectionError(
            (
                'Во время подключения к эндпоинту {url} произошла'
                ' непредвиденная ошибка: {error}'
                ' headers = {headers}; params = {params};'
            ).format(
                error=error,
                **request_params
            )
        )
    if response.status_code != HTTPStatus.OK:
        raise WrongAPIResponse(
            'Ответ сервера не является успешным:'
            f' request params = {request_params};'
            f' http_code = {response.status_code};'
            f' reason = {response.reason}; content = {response.text}'
        )
    else:
        homework_statuses = response.json()
    return homework_statuses


def check_response(response):
    """
    Checks the structure of the response JSON homework_statuses.

    Args:
        response (dict): JSON response received from Practicum API.
    """
    if not isinstance(response, dict):
        message = f'Я.Практикум вернул неожиданную структуру json: {response}'
        logger.error(message)
        raise TypeError('Ошибка в типе ответа API')
    if "homeworks" not in response or "current_date" not in response:
        message = f'Я.Практикум вернул неожиданную структуру json: {response}'
        logger.error(message)
        raise WrongAPIResponse(message)
    if not isinstance(response.get("homeworks"), list):
        message = f'Я.Практикум вернул неожиданный homeworks: {response}'
        logger.error(message)
        raise TypeError(message)
    return response.get('homeworks')


def parse_status(homework):
    """
    Parses the status of a homework_statuses.

    Args:
        homework (dict): A dictionary about a homework submission.

    Returns:
        str: A message describing the status of the homework submission.
    """
    if "homework_name" in homework:
        homework_name = homework.get('homework_name')
    else:
        message = f'Я.Практикум вернул json без homework_name: {homework}'
        logger.error(message)
        raise WrongAPIResponse(message)
    if "status" in homework:
        status = homework.get('status')
    else:
        message = f'Я.Практикум вернул json без status: {homework}'
        logger.error(message)
        raise WrongAPIResponse(message)
    if status not in HOMEWORK_VERDICTS:
        message = f'Я.Практикум вернул неожиданный статус: {status}'
        logger.error(message)
        raise StatusNotExpected(message)

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = (
            'Отсутсвуют обязательные переменные окружения: PRACTICUM_TOKEN,'
            ' TELEGRAM_TOKEN, TELEGRAM_CHAT_ID.'
            ' Программа принудительно остановлена.'
        )
        logging.critical(message)
        sys.exit(message)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_report: Dict = {'name': '', 'output': ''}
    prev_report: Dict = current_report.copy()

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date', current_timestamp)
            new_homeworks = check_response(response)
            if new_homeworks:
                current_report['name'] = new_homeworks[0]['homework_name']
                current_report['output'] = parse_status(new_homeworks[0])
            else:
                current_report['output'] = (
                    f'За период от {current_timestamp} до настоящего момента'
                    ' домашних работ нет.'
                )
            if current_report != prev_report:
                send_message(bot, current_report)
                prev_report = current_report.copy()
            else:
                logging.debug('В ответе нет новых статусов.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            current_report['output'] = message
            logging.error(message, exc_info=True)
            if current_report != prev_report:
                send_message(bot, current_report)
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
