import requests
import db_users
from telebot import types
from datetime import datetime, timedelta

now = datetime.now()
thirty_days = timedelta(30)
end = now + thirty_days #сегодня плюс 30 дней

# для доступа к api
departments_url = 'https://chudodoctor.infoclinica.ru/specialists/departments'
doctors_url = 'https://chudodoctor.infoclinica.ru/specialists/doctors?departments='
intervals_url = f'https://chudodoctor.infoclinica.ru/api/reservation/intervals?st={now.strftime("%Y%m%d")}&en={end.strftime("%Y%m%d")}&dcode='
# intervals_url = f'https://chudodoctor.infoclinica.ru/api/reservation/schedule?st={now.strftime("%Y%m%d")}&en={end.strftime("%Y%m%d")}&doctor='

# Контактные данные
contacts_info = '''109544, г. Москва, ул. Школьная, д. 49
    Режим работы
    Пн-Пт: 7:30 — 21:00
    Сб: 8:00 — 21:00
    Вс: 8:30 — 20:00'''

# isRunning = 0
# shedule_bot_msg_1 = shedule_bot_msg_2 = 0

# задаем кнопку назад
button = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
btn_back = types.KeyboardButton("⬅ Назад")
button.add(btn_back)

# задаем основные кнопки меню
main_btns = types.ReplyKeyboardMarkup(resize_keyboard=True)
button1 = types.KeyboardButton("📱 Контакты")
button2 = types.KeyboardButton("📋 Записаться на прием")
button3 = types.KeyboardButton("❗ Мои записи")
main_btns.add(button1, button2)
main_btns.row(button3)

# КОНСТАНТЫ СОСТОЯНИЙ
S_START = 'Старт'
S_CHOOSE_DIR = 'Список направлений'
S_CHOOSE_DOCTOR = 'Выбор врача'
S_CHOOSE_DATE = 'Выбор даты'
S_CHOOSE_TIME = 'Выбор времени'
S_RECORD_DONE = 'Конец записи'

def create_menu(mass, width=2, back=True):
    """
    This function allows to creat menu of buttons.
    mass - the list of string
    back - back button, if true, add a button back. Default back=True
    """
    markup = types.ReplyKeyboardMarkup(row_width=width, resize_keyboard=True)

    if len(mass) == 1:
        markup.row(mass[0])
    else:
        while len(mass) > 0:
            try:
                cut = mass[:2]
                markup.row(cut[0], cut[1])
                del mass[:2]
                
                if len(mass) == 1:
                    markup.row(mass[0])
                    break
            except:
                print('WTF')
    

    if back == True:
        markup.row('⬅ Назад')
    
    return markup

def get_data_from_api(url, id):
    data = requests.get(url + str(id)).json()
    if (data["success"] == True):
        return data["data"]
    else:
        return "Api Error!"

def get_available_date(data, choosenDate=False):
    """Get the date or time from json"""
    key_intervals = []
    for intervals in data:
        for workdates in intervals["workdates"]:
            for date in workdates:
                time_interval = workdates[date][0]["intervals"]
                for time in time_interval:
                    if time['isFree'] == True:
                        if choosenDate != False: # если выбрана дата, значит ищем доступные времена
                            if (choosenDate.replace('.','') == date):
                                key_intervals.append(time['time'])
                        else:
                            date = date[:4] + '.' + date[4:6] + '.' + date[6:8]
                            key_intervals.append(date) #Добавляем дату если в ней есть свободный прием
                            break

    return key_intervals

def json_directions():
    direction_json = requests.get(departments_url).json()
    return direction_json



class Record:
    def __init__(self, bot, message, state):
        self.bot = bot
        self.message = message
        self.state = state

    def get_record_direction(self):

        """Показывает список направлений"""

        user_id = self.message.from_user.id
        direction_json = json_directions()

        if (direction_json["success"] == True):
            key_direction = [types.KeyboardButton(text=direction["name"].strip()) for direction in direction_json["data"]] #cобираем список направлений
            markup = create_menu(list(key_direction), False)
            self.bot.send_message(user_id, 'Выберите направление:', reply_markup=markup) #отправляем текст с кнопками направлений
            db_users.set_state(user_id, self.state)
        else:
            self.bot.send_message(user_id, text="Сервис временно недоступен, попробуйте позже!", reply_markup=main_btns)

    def get_record_doctor(self):

        """Функция входе получает направление и показывает список докторов"""

        user_id = self.message.from_user.id
        direction_name = self.message.text

        if direction_name == "⬅ Назад" and db_users.get_current_state(user_id) == "Выбор даты": # если вернулись с вобора даты, показывает список врачей заного
            direction_name = db_users.get_current_property(user_id, 'Direction') # узнаем id направления, что бы получить врачей
        if direction_name == "⬅ Назад":
            db_users.set_state(user_id, S_START)
            self.bot.send_message(user_id, text="Вы вернулись в главное меню", reply_markup=main_btns)
        
        
        
        direction_json = json_directions()
    
        if (direction_json["success"] == True):
            for direction in direction_json["data"]:
                if (direction['name'].strip() == direction_name):
                    db_users.set_property(user_id, 'DirectionID', direction['id']) # сохраняем id категории, нужно для формирования списка врачей
                    db_users.set_property(user_id, 'Direction', direction_name)
                    self.bot.send_message(self.message.chat.id, 'Вы выбрали ' + direction_name)
                    doctors_json = get_data_from_api(doctors_url, direction['id']) # Получаем список докторов
                    if bool(doctors_json) == True:
                        db_users.set_state(user_id, self.state)
                        key_doctors = [types.KeyboardButton(text=doctor["name"]) for doctor in doctors_json] # Составляем список докторов для кнопок
                        markup = create_menu(list(key_doctors))
                        self.bot.send_message(self.message.chat.id, 'Выберите врача:', reply_markup=markup)
                    else:
                        db_users.set_state(user_id, S_CHOOSE_DIR)
                        key_direction = [types.KeyboardButton(text=direction["name"].strip()) for direction in direction_json["data"]]
                        markup = create_menu(list(key_direction), False)
                        self.bot.send_message(self.message.chat.id, 'В направлении нет врачей, выберите другое направление.', reply_markup=markup)
        else:
            self.bot.send_message(user_id, text="Сервис временно недоступен, попробуйте позже!", reply_markup=main_btns)
    
    def get_record_date(self):

        """Функция входе получает имя врача и показывает список доступных дат"""

        user_id = self.message.from_user.id
        doctor_name = self.message.text
 
        if doctor_name == "⬅ Назад" and db_users.get_current_state(user_id) == "Выбор врача": # если вместо дат, хотим вернуться на выбор направления
            self.get_record_direction()
            db_users.set_state(user_id, S_CHOOSE_DIR)
            return
        elif doctor_name == "⬅ Назад": # если вернулись с выбора времени, то заного показываем список дат
            doctor_name = db_users.get_current_property(user_id, 'Doctor') # получаем доктора из бд, что бы показать список дат
        
        direction_id = db_users.get_current_property(user_id, 'DirectionID') # узнаем id выбранной директории
        doctors_json = get_data_from_api(doctors_url, direction_id) # Получаем список докторов
        for doctor in doctors_json:
            if (doctor['name'] == doctor_name): # Если выбранное имя есть в списке из api то берем его ID
                self.bot.send_message(self.message.chat.id, 'Вы выбрали ' + doctor_name)
                db_users.set_property(user_id, 'DoctorCode', doctor['dcode']) # сохраняем id доктора

                intervals_json = get_data_from_api(intervals_url, doctor['dcode']) # получаем список интервалов для выбранного врача
                available_date = get_available_date(intervals_json) # получаем дату в нужном формате
        
                if bool(available_date) == True:
                    markup = create_menu(list(available_date)) # собираем список дат
                    self.bot.send_message(self.message.chat.id, 'Выберите дату:', reply_markup=markup)
                    db_users.set_state(user_id, self.state)
                else:
                    key_doctors = [types.KeyboardButton(text=doctor["name"]) for doctor in doctors_json] # Если у врача нет свободных дат, составляем список врачей и предлагаем выбрать другого
                    markup = create_menu(list(key_doctors))
                    db_users.set_state(user_id, S_CHOOSE_DOCTOR)
                    self.bot.send_message(self.message.chat.id, text="Нет свободных дат, выберите другого врача!", reply_markup=markup)

    def get_record_time(self):

        """Функция входе получает дату и показывает список времени приема"""

        user_id = self.message.from_user.id
        doctor_date = self.message.text

        if doctor_date == "⬅ Назад":
            self.get_record_doctor() # вернуться на список врачей
            db_users.set_state(user_id, S_CHOOSE_DOCTOR)
            return
    
        self.bot.send_message(user_id, 'Вы выбрали ' + doctor_date)

        doctor_id = db_users.get_current_property(user_id, 'DoctorCode') #узнаем id выбранного доктора
        intervals_json = get_data_from_api(intervals_url, doctor_id) # получаем список интервалов для выбранного врача
        available_time = get_available_date(intervals_json, choosenDate=doctor_date) # получаем дату в нужном формате
        if bool(available_time) == True:
            markup = create_menu(available_time)
            self.bot.send_message(self.message.chat.id, 'Выберите время:', reply_markup=markup)
            db_users.set_state(user_id, self.state)

    def get_record_final(self):

        """Функция входе получает время и выводит запись на финал"""

        user_id = self.message.from_user.id
        doctor_time = self.message.text

        if (doctor_time == "⬅ Назад"): # вернуться на список дат
            self.get_record_date()
            db_users.set_state(user_id, S_CHOOSE_DATE)
            return

        get_contact = [types.KeyboardButton('📲 Отправить контакты для записи', request_contact=True), types.KeyboardButton('❌ Отмена')]

        markup = create_menu(get_contact, width=1, back=False)
        self.bot.send_message(self.message.chat.id, 'Вы выбрали время: ' + doctor_time, reply_markup=markup )
        db_users.set_state(user_id, self.state)