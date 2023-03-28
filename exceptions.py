class WrongAPIResponse(Exception):
    """
    Exception raised when the response from the API is incorrect.
    """

    def __init__(self, message):
        self.message = "Я.Практикум вернул некорректный ответ сервера"


class MessageNotSent(Exception):
    """
    Exception raised when a message fails to send to bot.
    """

    def __init__(self, message):
        self.message = "Сообщение не удалось отправить"


class StatusNotExpected(Exception):
    """
    Exception raised when the status in the API response is unexpected.
    """

    def __init__(self, message):
        self.message = "Я.Практикум вернул неожиданный статус"
