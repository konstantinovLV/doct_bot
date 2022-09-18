from zoneinfo import available_timezones
import requests
import telebot
from telebot import types
from auth_data import token
from core import Record, create_menu, json_directions, get_available_date, get_data_from_api, main_btns, button, departments_url, doctors_url, intervals_url
import core
import db_users

text_messages = {
    'start':
        u'Добро пожаловать, {name}!\n'
        u'Я помогу Вам записаться на прием к врачу.\n\n'
        u'1. Выберите направление\n'
        u'2. Выберите врача, свободную дату и время\n'
        u'3. Подтвердите запись\n',
    'contact':
        u'109544, г. Москва, ул. Школьная, д. 49\n'
        u'Режим работы.\n\n'
        u'Пн-Пт: 7:30 — 21:00\n'
        u'Сб: 8:00 — 21:00\n'
        u'Вс: 8:30 — 20:00\n',
}

def telegram_bot(token):
    bot = telebot.TeleBot(token)

    @bot.message_handler(commands=["start"])
    def start(message):
        db_users.check_and_add_user(message) # проверяем наличие юзера в бд, если его нет - создаем
        bot.send_message(message.chat.id, text=text_messages['start'].format(name=message.from_user.first_name), reply_markup=main_btns)
        db_users.set_state(message.from_user.id, core.S_START)


    @bot.message_handler(content_types=['contact']) # Для получения данных о пользователе по запросу
    def contact(message):
        if message.contact is not None:
            user_id = message.from_user.id
            text = 'Ваше имя: ' + message.contact.first_name + ' ' + message.contact.last_name + '\nТелефон: ' + message.contact.phone_number + '\nНажимая кнопку "Записаться" Вы даете <a href="https://doct.ru/rules/">согласие на обработку персональных данных</a>.'
            db_users.set_property(user_id, 'Phone', message.contact.phone_number)
            record_btns = ['✅ Записаться', '❌ Отмена']
            markup = create_menu(record_btns, back=False)
            bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: db_users.get_current_state(message.from_user.id) == core.S_CHOOSE_DIR)
    def choosen_directions(message):
        """
        Функция показывает список докторов по выбранному направлению
        """
        direction_name = message.text
        user_id = message.from_user.id
        db_users.set_property(user_id, 'Direction', direction_name) #сохраняем в бд выбранное направление

        doctors = Record(bot, message, core.S_CHOOSE_DOCTOR)
        doctors.get_record_doctor() # получаем список докторов

    @bot.message_handler(func=lambda message: db_users.get_current_state(message.from_user.id) == core.S_CHOOSE_DOCTOR)
    def choosen_doctors(message):
        """
        Функция показывает список дат по выбранному доктору
        """
        doctor_name = message.text   
        user_id = message.from_user.id
        if doctor_name != "⬅ Назад":
            db_users.set_property(user_id, 'Doctor', doctor_name) #сохраняем в бд выбранного доктора
        
        dates = Record(bot, message, core.S_CHOOSE_DATE)
        dates.get_record_date() # получаем список доступных Дат приема

    @bot.message_handler(func=lambda message: db_users.get_current_state(message.from_user.id) == core.S_CHOOSE_DATE)
    def choosen_date(message):
        """
        Функция показывает список времени приема по выбранной дате
        """
        doctor_date = message.text   
        user_id = message.from_user.id
        db_users.set_property(user_id, 'RecordingDate', doctor_date)

        times = Record(bot, message, core.S_CHOOSE_TIME)
        times.get_record_time() # получаем список доступного времени

    @bot.message_handler(func=lambda message: db_users.get_current_state(message.from_user.id) == core.S_CHOOSE_TIME)
    def choosen_time(message):
        doctor_time = message.text
        user_id = message.from_user.id
        db_users.set_property(user_id, 'RecordingTime', doctor_time) #сохраняем в бд выбранного доктора

        final = Record(bot, message, core.S_RECORD_DONE)
        final.get_record_final() # получаем список доступного времени


    @bot.message_handler(content_types=['text'])
    def func(message):
        if(message.text == "📱 Контакты"):
            bot.send_message(message.chat.id, text=text_messages['contact'], reply_markup=button)
        elif(message.text == "📋 Записаться на прием"):
            directions = Record(bot, message, core.S_CHOOSE_DIR)
            directions.get_record_direction()
        elif(message.text == "❗ Мои записи"):
            user_id = message.from_user.id
            try:
                user_info = db_users.get_user_data(user_id)
                
                if user_info['success'] is not None:
                    records = len(user_info['success'])
                    bot.send_message(message.chat.id, text=f'Всего найдено {records} записей')
                    for success_data in enumerate(user_info['success']):
                        success_text = f'Запись №{success_data[0]+1}: {success_data[1][0]["direction"]}, {success_data[1][0]["doctor"]}, {success_data[1][0]["date"]}, {success_data[1][0]["time"]}.'
                        bot.send_message(message.chat.id, text=success_text)
            except Exception as ex:
                bot.send_message(message.chat.id, text="У вас еще нет записей")
        elif (message.text == "✅ Записаться"):
            user_id = message.from_user.id

            user_info = db_users.get_user_data(user_id) # получаем данные пользователя из бд
            success_msg = f"Уважаемый, {user_info['first_name']} {user_info['last_name']}, Вы успешно записаны на прием к врачу {user_info['Doctor']} \nДата: {user_info['RecordingDate']} \nВремя: {user_info['RecordingTime']}"
            admin_msg = f"Поступила запись с телеграмм бота. \n{user_info['first_name']} {user_info['last_name']} \nТелефон: {user_info['Phone']} \nК врачу {user_info['Doctor']} \nДата: {user_info['RecordingDate']} \nВремя: {user_info['RecordingTime']}"

            db_users.set_success_result(user_id, direction=user_info['Direction'], doctor=user_info['Doctor'], date=user_info['RecordingDate'], time=user_info['RecordingTime'])

            bot.send_message(message.chat.id, success_msg, reply_markup=main_btns)
            bot.send_message(368992399, admin_msg) # тут id админа
        elif (message.text == "❌ Отмена"):
            bot.send_message(message.chat.id, text="Вы вернулись в главное меню", reply_markup=main_btns)
        elif (message.text ==  "⬅ Назад"):
            print(message.text)
            bot.send_message(message.chat.id, text="Вы вернулись в главное меню", reply_markup=main_btns)
            db_users.set_state(message.from_user.id, core.S_START)
        # else:
        #     bot.send_message(message.chat.id, text="На такую комманду я не запрограммирован..", reply_markup=main_btns)



    try:
        bot.infinity_polling(timeout=10, long_polling_timeout = 5)
    except Exception as e:
        print(e)

if __name__ == '__main__':
    telegram_bot(token)