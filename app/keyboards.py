from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)


class Button:
    def __init__(self, text="", callback=""):
        self.text = text
        self.callback = callback


class TelegramInlineKeyboard:
    def __init__(self, header_buttons=None, footer_buttons=None) -> None:
        """
        Создает объект, хранящий внутри массив кнопок для InlineKeyboardMarkup
        :param header_buttons: Дополнительная первая кнопка
        :param footer_buttons: Дополнительная кнопка в конце
        """
        self.columns_num = 1
        self.buttons = []
        if header_buttons:
            self.header_buttons = InlineKeyboardButton(text=header_buttons.text, callback_data=header_buttons.callback)
        else:
            self.header_buttons = None
        if footer_buttons:
            self.footer_buttons = InlineKeyboardButton(text=footer_buttons.text, callback_data=footer_buttons.callback)
        else:
            self.footer_buttons = None

    def add_button(self, button_text: str, button_callback: str) -> None:
        """
        Добавление одной кнопки. Кнопка добавляется в конец списка
        :param button_text: Текст, который будет отображен на кнопке
        :param button_callback: Строка, которая вернется при нажатии на эту кнопку
        """
        button = [InlineKeyboardButton(text=button_text, callback_data=button_callback)]
        self.buttons.append(button)

    def add_buttons(self, buttons_list: list, columns_num: int) -> None:
        """
        Метод позволяет добавлять кнопки, переданные в виде списка структур
        :param columns_num: количество кнопок в одной строке
        :param buttons_list: список вида [{text:"text", callback:"callback},...]
        """
        self.columns_num = columns_num
        inline_buttons = []
        for button in buttons_list:
            inline_buttons.append(InlineKeyboardButton(text=button.text, callback_data=button.callback))
        menu = [inline_buttons[item:item + columns_num] for item in range(0, len(inline_buttons), columns_num)]
        self.buttons.extend(menu)

    def get_keyboard(self) -> InlineKeyboardMarkup:
        """
        Метод генерирует InlineKeyboardMarkup из массива self.button
        :return: InlineKeyboardMarkup
        """
        if self.header_buttons:
            self.buttons.insert(
                0,
                self.header_buttons
            )
        if self.footer_buttons:
            self.buttons.extend(
                self.footer_buttons
            )
        return InlineKeyboardMarkup(keyboard=self.buttons)
