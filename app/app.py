from pathlib import Path
import datetime
import telebot
from configparser import ConfigParser
import yaml
import prometheus_client
import logging
from keyboards import TelegramInlineKeyboard, Button
import argparse


is_dev = 0

# --------------------------------
parser = argparse.ArgumentParser(description="You can run this script locally, using flag --devmode or -d",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-d", "--devmode", action="store_true", help="Developer mode")
parser.add_argument("-m", "--macmode", action="store_true", help="Developer mode macos")
args = parser.parse_args()
config = vars(args)


devmode = config['devmode']
macmode = config['macmode']
if devmode:
    logging.basicConfig(filename="C:\\Users\\amalinko\\PycharmProjects\\QuestionnaireBot\\logs\\questionnaire_bot.log",
                        level=logging.INFO)
elif macmode:
    logging.basicConfig(filename="../QuestionnaireBot/logs/questionnaire_bot.log", level=logging.INFO)
else:
    logging.basicConfig(filename="/QuestionnaireBot/logs/questionnaire_bot.log", level=logging.INFO)
using_bot_counter = prometheus_client.Counter(
    "using_bot_count",
    "request to the bot",
    ['method', 'user_id', 'username']
)

parser = ConfigParser()
if devmode:
    parser.read(Path('C:\\Users\\amalinko\\PycharmProjects\\QuestionnaireBot\\config\\init.ini').absolute())
elif macmode:
    parser.read(Path('../QuestionnaireBot/config/init.ini').absolute())
else:
    parser.read(Path('/QuestionnaireBot/config/init.ini').absolute())
telegram_api_token = parser['telegram']['telegram_api_token']
bot = telebot.TeleBot(token=telegram_api_token)

if devmode:
    path: Path = Path(f"C:\\Users\\amalinko\\PycharmProjects\\QuestionnaireBot\\config\\config.yaml").absolute()
elif macmode:
    path: Path = Path(f"../QuestionnaireBot/config/config.yaml").absolute()
else:
    path: Path = Path(f"/QuestionnaireBot/config/config.yaml").absolute()
# --------------------------------


def read_config():
    with open(path, 'r', encoding='utf-8') as stream:
        config = yaml.safe_load(stream)
    return config


def bot_monitoring(message):
    using_bot_counter.labels(message.text, message.from_user.id, message.from_user.full_name).inc()


def bot_logging(message):
    pass
    logging.info(
        f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}. "
        f"{message.text},"
        f" {message.from_user.id},"
        f" {message.from_user.full_name}"
    )


# Функция для генерации отчета из опроса
def generate_report(inline_keyboard):
    report = ''
    inline_keyboard = inline_keyboard[:-1]
    for item in inline_keyboard:
        if item[2]['text'] == "Отмена":
            report += f"{item[0]['text']} -> {item[1]['text']}\n"
        else:
            report += f"{item[0]['text']} -> ?\n"
    return report


# Функции по обработке меню типов сервисов
def services_change_state(call, users_or_services):
    """
    Функция генерирует клавиатуру для выбора типов сервисов
    :param users_or_services:
    :param call:
    :return:
    """
    buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    _, changed_service_type, old_state = call.data.split("~")
    keyboard.add_button("Все", f"{users_or_services}~all")
    buttons_services_list = []
    for buttons_line in buttons_list[1:-1]:
        for button in buttons_line:
            if button['callback_data'] != call.data:
                callback = button['callback_data']
                new_text = button['text']
            else:
                if old_state == 'true':
                    new_text = button['text'][:button['text'].find(" ✅")]
                    new_state = 'false'
                else:
                    new_text = f"{button['text']} ✅"
                    new_state = 'true'
                callback = f"{users_or_services}~{changed_service_type}~{new_state}"
            buttons_services_list.append(Button(f"{new_text}", f"{callback}"))
    keyboard.add_buttons(buttons_services_list, 2)
    keyboard.add_button("Готово", f"{users_or_services}~start")
    current_list_services = call.message.text.split(":\n")
    changed_service_ru_name = "Неизвестно"
    service_types = read_config()['platform']
    for service in service_types:
        if service['en_name'] == changed_service_type:
            changed_service_ru_name = service['ru_name']
    if old_state == "false":
        new_message_text = f"{call.message.text}\n{changed_service_ru_name}"
    else:
        new_services_list = current_list_services[1].split("\n")
        new_services_list.remove(changed_service_ru_name)
        new_message_text = f"{current_list_services[0]}:\n" + '\n'.join(new_services_list)
    return new_message_text, keyboard.get_keyboard()


def services_all_chosen(call, users_or_services):
    buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    keyboard.add_button("Все", f"{users_or_services}~all")
    buttons_services_list = []
    for buttons_line in buttons_list[1:-1]:
        for button in buttons_line:
            _, service_name, old_state = button['callback_data'].split("~")
            if old_state == "false":
                new_text = f"{button['text']} ✅"
            else:
                new_text = button['text']
            new_state = 'true'
            callback = f"{users_or_services}~{service_name}~{new_state}"
            buttons_services_list.append(Button(f"{new_text}", f"{callback}"))
    keyboard.add_buttons(buttons_services_list, 2)
    keyboard.add_button("Готово", f"{users_or_services}~start")
    current_list_services = call.message.text.split(":\n")
    new_message_text = f"{current_list_services[0]}:"
    service_types = read_config()['platform']
    for service in service_types:
        new_message_text = f"{new_message_text}\n{service['ru_name']}"
    return new_message_text, keyboard.get_keyboard()


def services_start_questionnaire(call):
    """
    Функция генерирует клавиатуру со списком сервисов
    :param call:
    :return:
    """
    buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    services_type_list = []
    for buttons_line in buttons_list[1:-1]:
        for button in buttons_line:
            if button['callback_data'].endswith("true"):
                _, changed_service_type, _ = button['callback_data'].split("~")
                services_type_list.append(changed_service_type)
    platform_config = read_config()['platform']
    for platform in platform_config:
        keyboard = TelegramInlineKeyboard()
        if platform['en_name'] in services_type_list:
            questionnaire_buttons_list = []
            # keyboard.add_button(f"{platform['ru_name']}", f"global~{platform['en_name']}~clicked")
            for service in platform['services']:
                questionnaire_buttons_list.append(
                    Button(f"{service['ris']} {service['mnemo']}", f"service~{service['ris']}~clicked")
                )
                questionnaire_buttons_list.append(
                    Button(f"Успешно", f"service~{service['ris']}~success")
                )
                questionnaire_buttons_list.append(
                    Button(f"Ошибки", f"service~{service['ris']}~errors")
                )
            keyboard.add_buttons(questionnaire_buttons_list, 3)
            keyboard.add_button(f"Сгенерировать отчет", f"report_generate")
            bot.send_message(
                chat_id=call.message.chat.id,
                text=f"{platform['ru_name']}",
                reply_markup=keyboard.get_keyboard()
            )


# Функции по обработке меню сервисов
def service_success_or_errors(call, ris_code, new_state):
    current_buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    for row_buttons in current_buttons_list[:-1]:
        new_buttons_list = []
        button_in_row = 0
        for button in row_buttons:
            button_in_row += 1
            action_type, button_ris, button_action = button['callback_data'].split("~")
            if ris_code == button_ris:
                if button_action == "success":
                    button['text'] = new_state
                    button['callback_data'] = f"{action_type}~{button_ris}~checked"
                elif button_action == "errors":
                    button['text'] = "Отмена"
                    button['callback_data'] = f"{action_type}~{button_ris}~cancel"
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
            else:
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
        keyboard.add_buttons(new_buttons_list, button_in_row)
    keyboard.add_button(f"Сгенерировать отчет", f"report_generate")
    return keyboard.get_keyboard()


def service_cancel_check(call, ris_code):
    current_buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    for row_buttons in current_buttons_list[:-1]:
        new_buttons_list = []
        button_in_row = 0
        for button in row_buttons:
            button_in_row += 1
            action_type, button_ris, button_action = button['callback_data'].split("~")
            if ris_code == button_ris:
                if button_action == "checked":
                    button['text'] = "Успешно"
                    button['callback_data'] = f"{action_type}~{button_ris}~success"
                elif button_action == "cancel":
                    button['text'] = "Ошибки"
                    button['callback_data'] = f"{action_type}~{button_ris}~errors"
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
            else:
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
        keyboard.add_buttons(new_buttons_list, button_in_row)
    keyboard.add_button(f"Сгенерировать отчет", f"report_generate")
    return keyboard.get_keyboard()


def service_call_responsible_admins(ris_code):
    platform_config = read_config()['platform']
    break_flag = False
    responsible_admins_to_call = ""
    responsible_admins_id = []
    for platform in platform_config:
        for service in platform['services']:
            if service['ris'] == ris_code:
                break_flag = True
                responsible_admins_id = service['responsible_admins_id']
                break
        if break_flag:
            for user in platform['users']:
                if user['id'] in responsible_admins_id:
                    if user['telegram_username']:
                        responsible_admins_to_call += f"\n{user['telegram_username']}"
                    else:
                        responsible_admins_to_call += f"\n{user['name']}"
            break
    return responsible_admins_to_call


# Функции для старта опроса администраторов
def users_start_questionnaire(call):
    """
    Функция генерирует клавиатуру со списком сотрудников
    :param call:
    :return:
    """
    buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    services_type_list = []
    for buttons_line in buttons_list[1:-1]:
        for button in buttons_line:
            if button['callback_data'].endswith("true"):
                _, changed_service_type, _ = button['callback_data'].split("~")
                services_type_list.append(changed_service_type)
    platform_config = read_config()['platform']
    for platform in platform_config:
        keyboard = TelegramInlineKeyboard()
        if platform['en_name'] in services_type_list:
            questionnaire_buttons_list = []
            # keyboard.add_button(f"{platform['ru_name']}", f"global~{platform['en_name']}~clicked")
            for user in platform['users']:
                questionnaire_buttons_list.append(
                    Button(f"{user['name']}", f"user~{user['id']}~clicked")
                )
                questionnaire_buttons_list.append(
                    Button(f"Успешно", f"user~{user['id']}~success")
                )
                questionnaire_buttons_list.append(
                    Button(f"Ошибки", f"user~{user['id']}~errors")
                )
            keyboard.add_buttons(questionnaire_buttons_list, 3)
            keyboard.add_button(f"Сгенерировать отчет", f"report_generate")
            bot.send_message(
                chat_id=call.message.chat.id,
                text=f"{platform['ru_name']}",
                reply_markup=keyboard.get_keyboard()
            )


# Функции по обработке меню пользователей
def user_success_or_errors(call, user_id, new_state):
    current_buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    for row_buttons in current_buttons_list[:-1]:
        new_buttons_list = []
        button_in_row = 0
        for button in row_buttons:
            button_in_row += 1
            action_type, button_uid, button_action = button['callback_data'].split("~")
            if user_id == button_uid:
                if button_action == "success":
                    button['text'] = new_state
                    button['callback_data'] = f"{action_type}~{button_uid}~checked"
                elif button_action == "errors":
                    button['text'] = "Отмена"
                    button['callback_data'] = f"{action_type}~{button_uid}~cancel"
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
            else:
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
        keyboard.add_buttons(new_buttons_list, button_in_row)
    keyboard.add_button(f"Сгенерировать отчет", f"report_generate")
    return keyboard.get_keyboard()


def user_cancel_check(call, user_id):
    current_buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    for row_buttons in current_buttons_list[:-1]:
        new_buttons_list = []
        button_in_row = 0
        for button in row_buttons:
            button_in_row += 1
            action_type, button_uid, button_action = button['callback_data'].split("~")
            if user_id == button_uid:
                if button_action == "checked":
                    button['text'] = "Успешно"
                    button['callback_data'] = f"{action_type}~{button_uid}~success"
                elif button_action == "cancel":
                    button['text'] = "Ошибки"
                    button['callback_data'] = f"{action_type}~{button_uid}~errors"
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
            else:
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
        keyboard.add_buttons(new_buttons_list, button_in_row)
    keyboard.add_button(f"Сгенерировать отчет", f"report_generate")
    return keyboard.get_keyboard()


def user_call(user_id):
    platform_config = read_config()['platform']
    break_flag = False
    admin_id = ""
    for platform in platform_config:
        for user in platform['users']:
            if user['id'] == user_id:
                break_flag = True
                if user['telegram_username']:
                    admin_id = user['telegram_username']
                else:
                    admin_id = user['name']
                break
        if break_flag:
            break
    return admin_id


def get_os_users():
    users = []
    platform_config = read_config()['platform']
    for platform in platform_config:
        if platform['en_name'] == 'OS':
            for user in platform['users']:
                users.append(user['name'])
    return users


def get_os_usernames():
    users = []
    platform_config = read_config()['platform']
    for platform in platform_config:
        if platform['en_name'] == 'OS':
            for user in platform['users']:
                users.append(user['telegram_username'])
    return users


@bot.message_handler(commands=['os_users'])
def status_message(message):
    users_list = get_os_users()
    while len(users_list) >= 10:
        users_slice = users_list[:9]
        users_list = users_list[9:]
        users_slice.append('Посмотреть результат')
        bot.send_poll(
            message.chat.id,
            question="Опрос",
            options=users_slice,
            is_anonymous=False,
        )
    users_list.append('Посмотреть результат')
    bot.send_poll(
        message.chat.id,
        question="Опрос",
        options=users_list,
        is_anonymous=False,
    )


@bot.message_handler(commands=['os_all'])
def status_message(message):
    users_list = get_os_usernames()
    bot.send_message(
        message.chat.id,
        f"ALL ping\n{users_list}",
    )


# Команды боту
@bot.message_handler(commands=['services'])
def status_message(message):
    bot_monitoring(message)
    bot_logging(message)
    keyboard = TelegramInlineKeyboard()
    keyboard.add_button("Все", "services~all")  # Кнопка выбора всех типов сервисов
    service_types = read_config()['platform']
    buttons_services_list = []
    for service in service_types:
        buttons_services_list.append(Button(service['ru_name'], f"services~{service['en_name']}~false"))
    keyboard.add_buttons(buttons_services_list, 2)
    keyboard.add_button("Готово", "services~start")
    bot.send_message(
        message.chat.id,
        "Выберите тип сервисов:",
        # reply_to_message_id=message.id,
        reply_markup=keyboard.get_keyboard()
    )


@bot.message_handler(commands=['users'])
def status_message(message):
    bot_monitoring(message)
    bot_logging(message)
    keyboard = TelegramInlineKeyboard()
    keyboard.add_button("Все", "users~all")  # Кнопка выбора всех типов сервисов
    service_types = read_config()['platform']
    buttons_services_list = []
    for service in service_types:
        buttons_services_list.append(Button(service['ru_name'], f"users~{service['en_name']}~false"))
    keyboard.add_buttons(buttons_services_list, 2)
    keyboard.add_button("Готово", "users~start")
    bot.send_message(
        message.chat.id,
        "Выберите тип сервисов:",
        # reply_to_message_id=message.id,
        reply_markup=keyboard.get_keyboard()
    )


#  Функции по обработке нажатий на кнопки опроса сервисов
@bot.callback_query_handler(func=lambda call: call.data.startswith('services'))
def query_handler(call):
    """
    Событие происходит при выборе типов сервисов для генерации опроса
    :param call:
    :return:
    """
    if call.data != "services~start" and call.data != "services~all":
        changed_text, changed_markup = services_change_state(call, "services")
        bot.answer_callback_query(callback_query_id=call.id, text="Готово")
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif call.data == "services~all":
        changed_text, changed_markup = services_all_chosen(call, "services")
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif call.data == "services~start":
        changed_text = "Проверка доступности сервисов"
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id
        )
        bot.answer_callback_query(callback_query_id=call.id, text="Запускаю опрос")
        services_start_questionnaire(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('service'))
def query_handler(call):
    """
    Событие происходит при нажатии на кнопку Успешно/Ошибки отдельного сервиса
    :param call:
    :return:
    """
    _, ris_code, clicked_state = call.data.split("~")
    if clicked_state == "success":
        changed_text = call.message.text
        changed_markup = service_success_or_errors(call, ris_code, '✅')
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "errors":
        changed_text = call.message.text
        changed_markup = service_success_or_errors(call, ris_code, '❌')
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "cancel":
        changed_text = call.message.text
        changed_markup = service_cancel_check(call, ris_code)
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "clicked":
        responsible_list = service_call_responsible_admins(ris_code)
        bot.answer_callback_query(callback_query_id=call.id, text="Пинг ответственных")
        bot.send_message(
            chat_id=call.message.chat.id,
            text=f"Проверьте состояние сервиса {ris_code}!\n{responsible_list}"
        )


#  Функции по обработке нажатий на кнопки опроса администраторов
@bot.callback_query_handler(func=lambda call: call.data.startswith('users'))
def query_handler(call):
    """
    Событие происходит при выборе типов сервисов для генерации опроса администраторов
    :param call:
    :return:
    """
    if call.data != "users~start" and call.data != "users~all":
        changed_text, changed_markup = services_change_state(call, "users")
        bot.answer_callback_query(callback_query_id=call.id, text="Готово")
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif call.data == "users~all":
        changed_text, changed_markup = services_all_chosen(call, "users")
        bot.answer_callback_query(callback_query_id=call.id, text="Выбраны все типы сервисов")
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif call.data == "users~start":
        changed_text = "Опрос сотрудников"
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id
        )
        bot.answer_callback_query(callback_query_id=call.id, text="Запускаю опрос")
        users_start_questionnaire(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('user'))
def query_handler(call):
    """
    Событие происходит при нажатии на кнопку Успешно/Ошибки отдельного сервиса
    :param call:
    :return:
    """
    _, user_id, clicked_state = call.data.split("~")
    if clicked_state == "success":
        changed_text = "Опрос сотрудников"
        changed_markup = user_success_or_errors(call, user_id, '✅')
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "errors":
        changed_text = "Опрос сотрудников"
        changed_markup = user_success_or_errors(call, user_id, '❌')
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "cancel":
        changed_text = "Опрос сотрудников"
        changed_markup = user_cancel_check(call, user_id)
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "clicked":
        responsible_list = user_call(int(user_id))
        bot.answer_callback_query(callback_query_id=call.id, text="Пинг сотрудника")
        bot.send_message(
            chat_id=call.message.chat.id,
            text=f"{responsible_list}"
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith('report'))
def query_handler(call):
    bot.answer_callback_query(callback_query_id=call.id, text='Генерация отчета')
    report_message = generate_report(call.message.json['reply_markup']['inline_keyboard'])
    bot.edit_message_text(
        text=report_message,
        chat_id=call.message.chat.id,
        message_id=call.message.id,
    )


if __name__ == '__main__':
    prometheus_client.start_http_server(9300)
    bot.infinity_polling()
