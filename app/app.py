from pathlib import Path
import datetime
import telebot
from configparser import ConfigParser
import yaml
import prometheus_client
import logging
import time
from keyboards import TelegramInlineKeyboard, Button
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

opt = Options()
opt.add_argument("--disable-infobars")
opt.add_argument("start-maximized")
opt.add_argument("--disable-extensions")
# Pass the argument 1 to allow and 2 to block
opt.add_experimental_option("prefs", {
    "profile.default_content_setting_values.media_stream_mic": 1,
    "profile.default_content_setting_values.media_stream_camera": 1,
    "profile.default_content_setting_values.geolocation": 1,
    "profile.default_content_setting_values.notifications": 1
})
logging.basicConfig(filename="/QuestionnaireBot/logs/questionnaire_bot.log", level=logging.INFO)
# logging.basicConfig(filename="../logs/questionnaire_bot.log", level=logging.INFO)
using_bot_counter = prometheus_client.Counter(
    "using_bot_count",
    "request to the bot",
    ['method', 'user_id', 'username']
)
parser = ConfigParser()
parser.read(Path('/QuestionnaireBot/config/init_dev.ini').absolute())
# parser.read(Path('../config/init_dev.ini').absolute())
telegram_api_token = parser['telegram']['telegram_api_token']
bot = telebot.TeleBot(token=telegram_api_token)
path: Path = Path(f"/QuestionnaireBot/config/config_dev.yaml").absolute()
# path: Path = Path(f"../config/config_dev.yaml").absolute()


def read_config():
    with open(path, 'r') as stream:
        config = yaml.safe_load(stream)
    return config


def bot_monitoring(message):
    using_bot_counter.labels(message.text, message.from_user.id, message.from_user.full_name).inc()


def bot_logging(message):
    logging.info(
        f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}. "
        f"{message.text},"
        f" {message.from_user.id},"
        f" {message.from_user.full_name}"
    )


def check_first_second_name(dion_names, config_names):
    admins_not_in_dion = []
    for config_admin in config_names:
        for dion_admin in dion_names:
            if config_admin['first_name'] == dion_admin['first_name']:
                if config_admin['second_name'] == dion_admin['second_name']:
                    dion_names.remove(dion_admin)
                    break
            elif config_admin['first_name'] == dion_admin['second_name']:
                if config_admin['second_name'] == dion_admin['first_name']:
                    dion_names.remove(dion_admin)
                    break
        else:
            admins_not_in_dion.append(config_admin)
    return admins_not_in_dion, dion_names


# ?????????????? ?????? ?????????????????? ???????????? ???? ????????????
def generate_report(inline_keyboard):
    report = ''
    inline_keyboard = inline_keyboard[:-1]
    for item in inline_keyboard:
        if item[2]['text'] == "????????????":
            report += f"{item[0]['text']} -> {item[1]['text']}\n"
        else:
            report += f"{item[0]['text']} -> ?\n"
    return report


# ?????????????? ???? ?????????????????? ???????? ?????????? ????????????????
def services_change_state(call, users_or_services):
    """
    ?????????????? ???????????????????? ???????????????????? ?????? ???????????? ?????????? ????????????????
    :param users_or_services:
    :param call:
    :return:
    """
    buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    _, changed_service_type, old_state = call.data.split("_")
    keyboard.add_button("??????", f"{users_or_services}_all")
    buttons_services_list = []
    for buttons_line in buttons_list[1:-1]:
        for button in buttons_line:
            if button['callback_data'] != call.data:
                callback = button['callback_data']
                new_text = button['text']
            else:
                if old_state == 'true':
                    new_text = button['text'][:button['text'].find(" ???")]
                    new_state = 'false'
                else:
                    new_text = f"{button['text']} ???"
                    new_state = 'true'
                callback = f"{users_or_services}_{changed_service_type}_{new_state}"
            buttons_services_list.append(Button(f"{new_text}", f"{callback}"))
    keyboard.add_buttons(buttons_services_list, 2)
    keyboard.add_button("????????????", f"{users_or_services}_start")
    current_list_services = call.message.text.split(":\n")
    changed_service_ru_name = "????????????????????"
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
    keyboard.add_button("??????", f"{users_or_services}_all")
    buttons_services_list = []
    for buttons_line in buttons_list[1:-1]:
        for button in buttons_line:
            _, service_name, old_state = button['callback_data'].split("_")
            if old_state == "false":
                new_text = f"{button['text']} ???"
            else:
                new_text = button['text']
            new_state = 'true'
            callback = f"{users_or_services}_{service_name}_{new_state}"
            buttons_services_list.append(Button(f"{new_text}", f"{callback}"))
    keyboard.add_buttons(buttons_services_list, 2)
    keyboard.add_button("????????????", f"{users_or_services}_start")
    current_list_services = call.message.text.split(":\n")
    new_message_text = f"{current_list_services[0]}:"
    service_types = read_config()['platform']
    for service in service_types:
        new_message_text = f"{new_message_text}\n{service['ru_name']}"
    return new_message_text, keyboard.get_keyboard()


def services_start_questionnaire(call):
    """
    ?????????????? ???????????????????? ???????????????????? ???? ?????????????? ????????????????
    :param call:
    :return:
    """
    buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    services_type_list = []
    for buttons_line in buttons_list[1:-1]:
        for button in buttons_line:
            if button['callback_data'].endswith("true"):
                _, changed_service_type, _ = button['callback_data'].split("_")
                services_type_list.append(changed_service_type)
    platform_config = read_config()['platform']
    for platform in platform_config:
        keyboard = TelegramInlineKeyboard()
        if platform['en_name'] in services_type_list:
            questionnaire_buttons_list = []
            # keyboard.add_button(f"{platform['ru_name']}", f"global_{platform['en_name']}_clicked")
            for service in platform['services']:
                questionnaire_buttons_list.append(
                    Button(f"{service['ris']} {service['mnemo']}", f"service_{service['ris']}_clicked")
                )
                questionnaire_buttons_list.append(
                    Button(f"??????????????", f"service_{service['ris']}_success")
                )
                questionnaire_buttons_list.append(
                    Button(f"????????????", f"service_{service['ris']}_errors")
                )
            keyboard.add_buttons(questionnaire_buttons_list, 3)
            keyboard.add_button(f"?????????????????????????? ??????????", f"report_generate")
            bot.send_message(
                chat_id=call.message.chat.id,
                text=f"{platform['ru_name']}",
                reply_markup=keyboard.get_keyboard()
            )


# ?????????????? ???? ?????????????????? ???????? ????????????????
def service_success_or_errors(call, ris_code, new_state):
    current_buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    for row_buttons in current_buttons_list[:-1]:
        new_buttons_list = []
        button_in_row = 0
        for button in row_buttons:
            button_in_row += 1
            action_type, button_ris, button_action = button['callback_data'].split("_")
            if ris_code == button_ris:
                if button_action == "success":
                    button['text'] = new_state
                    button['callback_data'] = f"{action_type}_{button_ris}_checked"
                elif button_action == "errors":
                    button['text'] = "????????????"
                    button['callback_data'] = f"{action_type}_{button_ris}_cancel"
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
            else:
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
        keyboard.add_buttons(new_buttons_list, button_in_row)
    keyboard.add_button(f"?????????????????????????? ??????????", f"report_generate")
    return keyboard.get_keyboard()


def service_cancel_check(call, ris_code):
    current_buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    for row_buttons in current_buttons_list[:-1]:
        new_buttons_list = []
        button_in_row = 0
        for button in row_buttons:
            button_in_row += 1
            action_type, button_ris, button_action = button['callback_data'].split("_")
            if ris_code == button_ris:
                if button_action == "checked":
                    button['text'] = "??????????????"
                    button['callback_data'] = f"{action_type}_{button_ris}_success"
                elif button_action == "cancel":
                    button['text'] = "????????????"
                    button['callback_data'] = f"{action_type}_{button_ris}_errors"
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
            else:
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
        keyboard.add_buttons(new_buttons_list, button_in_row)
    keyboard.add_button(f"?????????????????????????? ??????????", f"report_generate")
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


# ?????????????? ?????? ???????????? ???????????? ??????????????????????????????
def users_start_questionnaire(call):
    """
    ?????????????? ???????????????????? ???????????????????? ???? ?????????????? ??????????????????????
    :param call:
    :return:
    """
    buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    services_type_list = []
    for buttons_line in buttons_list[1:-1]:
        for button in buttons_line:
            if button['callback_data'].endswith("true"):
                _, changed_service_type, _ = button['callback_data'].split("_")
                services_type_list.append(changed_service_type)
    platform_config = read_config()['platform']
    for platform in platform_config:
        keyboard = TelegramInlineKeyboard()
        if platform['en_name'] in services_type_list:
            questionnaire_buttons_list = []
            # keyboard.add_button(f"{platform['ru_name']}", f"global_{platform['en_name']}_clicked")
            for user in platform['users']:
                questionnaire_buttons_list.append(
                    Button(f"{user['name']}", f"user_{user['id']}_clicked")
                )
                questionnaire_buttons_list.append(
                    Button(f"??????????????", f"user_{user['id']}_success")
                )
                questionnaire_buttons_list.append(
                    Button(f"????????????", f"user_{user['id']}_errors")
                )
            keyboard.add_buttons(questionnaire_buttons_list, 3)
            keyboard.add_button(f"?????????????????????????? ??????????", f"report_generate")
            bot.send_message(
                chat_id=call.message.chat.id,
                text=f"{platform['ru_name']}",
                reply_markup=keyboard.get_keyboard()
            )


# ?????????????? ???? ?????????????????? ???????? ??????????????????????????
def user_success_or_errors(call, user_id, new_state):
    current_buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    for row_buttons in current_buttons_list[:-1]:
        new_buttons_list = []
        button_in_row = 0
        for button in row_buttons:
            button_in_row += 1
            action_type, button_uid, button_action = button['callback_data'].split("_")
            if user_id == button_uid:
                if button_action == "success":
                    button['text'] = new_state
                    button['callback_data'] = f"{action_type}_{button_uid}_checked"
                elif button_action == "errors":
                    button['text'] = "????????????"
                    button['callback_data'] = f"{action_type}_{button_uid}_cancel"
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
            else:
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
        keyboard.add_buttons(new_buttons_list, button_in_row)
    keyboard.add_button(f"?????????????????????????? ??????????", f"report_generate")
    return keyboard.get_keyboard()


def user_cancel_check(call, user_id):
    current_buttons_list = call.message.reply_markup.to_dict()['inline_keyboard']
    keyboard = TelegramInlineKeyboard()
    for row_buttons in current_buttons_list[:-1]:
        new_buttons_list = []
        button_in_row = 0
        for button in row_buttons:
            button_in_row += 1
            action_type, button_uid, button_action = button['callback_data'].split("_")
            if user_id == button_uid:
                if button_action == "checked":
                    button['text'] = "??????????????"
                    button['callback_data'] = f"{action_type}_{button_uid}_success"
                elif button_action == "cancel":
                    button['text'] = "????????????"
                    button['callback_data'] = f"{action_type}_{button_uid}_errors"
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
            else:
                new_buttons_list.append(Button(text=button['text'], callback=button['callback_data']))
        keyboard.add_buttons(new_buttons_list, button_in_row)
    keyboard.add_button(f"?????????????????????????? ??????????", f"report_generate")
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


@bot.message_handler(commands=['who_is_in_the_conference'])
def initial_message(message):
    bot.send_message(
        message.chat.id,
        "?????????????? ?????????? ??????????????????????",
    )
    bot.register_next_step_handler(message, check_dion_room)


def check_dion_room(message):
    browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opt)
    browser.get(f'https://dion.vc/event/{message.text}')
    elem = browser.find_element(By.ID, 'name')
    elem.send_keys('OSCheckBot' + Keys.RETURN)
    while True:
        try:
            connect_btn = browser.find_element(By.CSS_SELECTOR, "#connect-to-call")
            break
        except:
            time.sleep(1)
    connect_btn.click()
    while True:
        try:
            users_btn = browser.find_element(By.CSS_SELECTOR, "#open-speakers-list-button")
            break
        except:
            time.sleep(1)
    users_btn.click()
    user_list = browser.find_element(By.CSS_SELECTOR,
                                     "#root > div.sc-ftvSup.gygqun > div > div.css-m7mn9r > "
                                     "div > div > div.MuiDrawer-root.MuiDrawer-docked.css-uje53d > "
                                     "div > div.css-19tbzjb > div > div > ul"
                                     )
    user_list = user_list.find_elements(By.XPATH, "./li")
    dion_users = []
    for user in user_list:
        name = user.find_elements(By.XPATH, "./div[2]/div[1]/div")
        try:
            firstname, second_name = name[0].text.split(" ")
            dion_users.append({'first_name': firstname, 'second_name': second_name})
        except:
            dion_users.append({'first_name': name[0].text, 'second_name': ""})

    platform_config = read_config()['platform']
    full_config_users = []
    for platform in platform_config:
        if platform['en_name'] == "OS":
            full_config_users = platform['users']
            break
    else:
        print("???????????????????????????????? ???????? ???? ??????????????????")
        exit(-1)
    config_users = []
    for user in full_config_users:
        try:
            firstname, second_name = user['name'].split(" ")
            config_users.append(
                {'first_name': firstname, 'second_name': second_name, 'telegram_id': user['telegram_username']})
        except:
            config_users.append(
                {'first_name': user['name'], 'second_name': "", 'telegram_id': user['telegram_username']})
    admins_not_in_dion, unknown_admins = check_first_second_name(dion_names=dion_users, config_names=config_users)
    answer_message = ""
    answer_message += "??????????????????????:\n"
    for elem in admins_not_in_dion:
        answer_message += f"{elem['first_name']} {elem['second_name']} {elem['telegram_id']}\n"
    if len(unknown_admins) != 1:
        answer_message += "\n?????????????????????? ??????????????????:\n"
        for elem in unknown_admins:
            if elem['first_name'] != 'Oscheckbot':
                answer_message += f"{elem['first_name']} {elem['second_name']}\n"
    browser.close()
    bot.send_message(
        message.chat.id,
        answer_message,
    )


@bot.message_handler(commands=['os_users'])
def status_message(message):
    users_list = get_os_users()
    while len(users_list) >= 10:
        users_slice = users_list[:9]
        users_list = users_list[9:]
        users_slice.append('???????????????????? ??????????????????')
        bot.send_poll(
            message.chat.id,
            question="??????????",
            options=users_slice,
            is_anonymous=False,
        )
    users_list.append('???????????????????? ??????????????????')
    bot.send_poll(
        message.chat.id,
        question="??????????",
        options=users_list,
        is_anonymous=False,
    )


# ?????????????? ????????
@bot.message_handler(commands=['services'])
def status_message(message):
    bot_monitoring(message)
    bot_logging(message)
    keyboard = TelegramInlineKeyboard()
    keyboard.add_button("??????", "services_all")  # ???????????? ???????????? ???????? ?????????? ????????????????
    service_types = read_config()['platform']
    buttons_services_list = []
    for service in service_types:
        buttons_services_list.append(Button(service['ru_name'], f"services_{service['en_name']}_false"))
    keyboard.add_buttons(buttons_services_list, 2)
    keyboard.add_button("????????????", "services_start")
    bot.send_message(
        message.chat.id,
        "???????????????? ?????? ????????????????:",
        # reply_to_message_id=message.id,
        reply_markup=keyboard.get_keyboard()
    )


@bot.message_handler(commands=['users'])
def status_message(message):
    bot_monitoring(message)
    bot_logging(message)
    keyboard = TelegramInlineKeyboard()
    keyboard.add_button("??????", "users_all")  # ???????????? ???????????? ???????? ?????????? ????????????????
    service_types = read_config()['platform']
    buttons_services_list = []
    for service in service_types:
        buttons_services_list.append(Button(service['ru_name'], f"users_{service['en_name']}_false"))
    keyboard.add_buttons(buttons_services_list, 2)
    keyboard.add_button("????????????", "users_start")
    bot.send_message(
        message.chat.id,
        "???????????????? ?????? ????????????????:",
        # reply_to_message_id=message.id,
        reply_markup=keyboard.get_keyboard()
    )


#  ?????????????? ???? ?????????????????? ?????????????? ???? ???????????? ???????????? ????????????????
@bot.callback_query_handler(func=lambda call: call.data.startswith('services'))
def query_handler(call):
    """
    ?????????????? ???????????????????? ?????? ???????????? ?????????? ???????????????? ?????? ?????????????????? ????????????
    :param call:
    :return:
    """
    if call.data != "services_start" and call.data != "services_all":
        changed_text, changed_markup = services_change_state(call, "services")
        bot.answer_callback_query(callback_query_id=call.id, text="????????????")
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif call.data == "services_all":
        changed_text, changed_markup = services_all_chosen(call, "services")
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif call.data == "services_start":
        changed_text = "???????????????? ?????????????????????? ????????????????"
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id
        )
        bot.answer_callback_query(callback_query_id=call.id, text="???????????????? ??????????")
        services_start_questionnaire(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('service'))
def query_handler(call):
    """
    ?????????????? ???????????????????? ?????? ?????????????? ???? ???????????? ??????????????/???????????? ???????????????????? ??????????????
    :param call:
    :return:
    """
    _, ris_code, clicked_state = call.data.split("_")
    if clicked_state == "success":
        changed_text = call.message.text
        changed_markup = service_success_or_errors(call, ris_code, '???')
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "errors":
        changed_text = call.message.text
        changed_markup = service_success_or_errors(call, ris_code, '???')
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
        bot.answer_callback_query(callback_query_id=call.id, text="???????? ??????????????????????????")
        bot.send_message(
            chat_id=call.message.chat.id,
            text=f"?????????????????? ?????????????????? ?????????????? {ris_code}!\n{responsible_list}"
        )


#  ?????????????? ???? ?????????????????? ?????????????? ???? ???????????? ???????????? ??????????????????????????????
@bot.callback_query_handler(func=lambda call: call.data.startswith('users'))
def query_handler(call):
    """
    ?????????????? ???????????????????? ?????? ???????????? ?????????? ???????????????? ?????? ?????????????????? ???????????? ??????????????????????????????
    :param call:
    :return:
    """
    if call.data != "users_start" and call.data != "users_all":
        changed_text, changed_markup = services_change_state(call, "users")
        bot.answer_callback_query(callback_query_id=call.id, text="????????????")
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif call.data == "users_all":
        changed_text, changed_markup = services_all_chosen(call, "users")
        bot.answer_callback_query(callback_query_id=call.id, text="?????????????? ?????? ???????? ????????????????")
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif call.data == "users_start":
        changed_text = "?????????? ??????????????????????"
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id
        )
        bot.answer_callback_query(callback_query_id=call.id, text="???????????????? ??????????")
        users_start_questionnaire(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('user'))
def query_handler(call):
    """
    ?????????????? ???????????????????? ?????? ?????????????? ???? ???????????? ??????????????/???????????? ???????????????????? ??????????????
    :param call:
    :return:
    """
    _, user_id, clicked_state = call.data.split("_")
    if clicked_state == "success":
        changed_text = "?????????? ??????????????????????"
        changed_markup = user_success_or_errors(call, user_id, '???')
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "errors":
        changed_text = "?????????? ??????????????????????"
        changed_markup = user_success_or_errors(call, user_id, '???')
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "cancel":
        changed_text = "?????????? ??????????????????????"
        changed_markup = user_cancel_check(call, user_id)
        bot.edit_message_text(
            text=changed_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=changed_markup
        )
    elif clicked_state == "clicked":
        responsible_list = user_call(int(user_id))
        bot.answer_callback_query(callback_query_id=call.id, text="???????? ????????????????????")
        bot.send_message(
            chat_id=call.message.chat.id,
            text=f"{responsible_list}"
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith('report'))
def query_handler(call):
    bot.answer_callback_query(callback_query_id=call.id, text='?????????????????? ????????????')
    report_message = generate_report(call.message.json['reply_markup']['inline_keyboard'])
    bot.edit_message_text(
        text=report_message,
        chat_id=call.message.chat.id,
        message_id=call.message.id,
    )


if __name__ == '__main__':
    prometheus_client.start_http_server(9300)
    bot.infinity_polling()
