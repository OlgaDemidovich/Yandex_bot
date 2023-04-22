from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CommandHandler, MessageHandler, filters, \
    Application, ConversationHandler
import sqlite3
import logging
import random
import string
import datetime
import os
import time
import threading

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)

conn = sqlite3.connect('school_bot.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, user_id TEXT, group_id TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS schedule
             (id INTEGER PRIMARY KEY, schedules TEXT, group_id TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS homework
             (id INTEGER PRIMARY KEY, subject TEXT, 
             task TEXT, day TEXT, group_id TEXT)''')
day = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
short_day = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб']


async def start(update, context):
    """Приветствие пользователя и озвучка команд, выполняемых ботом"""
    await update.message.reply_text(
        "Привет! Я школьный бот Общий дневник, "
        "которым может пользоваться весь твой класс! Вот что я могу:\n"
        "/schedule - создать или присединиться к расписанию\n"
        "/get_schedule - получить расписание на сегодня\n"
        "/add_task - добавить домашнее задание\n"
        "/get_task - получить домашнее задание\n"
        "/leave_schedule - покинуть данное расписание",
        reply_markup=ReplyKeyboardRemove())


async def schedule(update, context):
    """Cтартовый вопрос диалога для создания или добавления пользователя в
        расписание"""
    reply_keyboard = [['Создать расписание', 'Присоединиться к расписанию']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
    user_id = str(update.message.from_user.id)
    if (user_id,) in c.execute(f'SELECT user_id '
                               f'FROM users').fetchall():
        await update.message.reply_text(
            f"Вы уже добавлены в расписание. \n"
            f"Введите /leave_schedule чтобы покинуть расписание",
            reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    await update.message.reply_text(
        'Выбери: создать расписание или '
        'присоединиться к уже существующему, которое создал кто-то из '
        'вашего класса/группы. Команда прерывания создания расписания: /stop',
        reply_markup=markup)
    return 1


async def alternating_or_not(update, context):
    """Вопрос о чередовании расписания или о ключевом слове группы"""
    locality = update.message.text
    if locality == 'Создать расписание':
        reply_keyboard = [['Чередующееся', 'Не чередующееся']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
        await update.message.reply_text(
            "Какое у тебя расписание: чередующееся или нет?",
            reply_markup=markup)
        return 2
    elif locality == 'Присоединиться к расписанию':
        await update.message.reply_text(
            "Напиши ключевое слово вашей группы. Узнай у одноклассников",
            reply_markup=ReplyKeyboardRemove())
        return 4


async def create_schedule(update, context):
    """Обработка ответа о чередовании расписания"""
    locality = update.message.text
    if locality == 'Чередующееся':
        context.user_data['day'] = day + day
    elif 'Не чередующееся':
        context.user_data['day'] = day
    await update.message.reply_text(
        "Какое расписание в Понедельник? Напиши предметы через запятую "
        "(регистр не важен)",
        reply_markup=ReplyKeyboardRemove())
    context.user_data['schedule'] = []
    return 3


async def adding_subjects(update, context):
    """Добавление расписания по дням недели, запись в БД"""
    new_day = [i.strip() for i in list(update.message.text.lower().split(","))]
    context.user_data['schedule'].append(new_day)

    if len(context.user_data['day']) == 1:
        while True:
            letters_and_digits = string.ascii_letters + string.digits
            key = ''.join(random.sample(letters_and_digits, 6))
            if key not in c.execute(f'SELECT group_id '
                                    f'FROM users').fetchall():
                break

        await update.message.reply_text(f"Дни недели закончились! "
                                        f"Ваше ключевое слово расписания: ")
        await update.message.reply_text(key)
        user_id = update.message.from_user.id
        c.execute(
            f'INSERT INTO users(user_id, group_id) '
            f'VALUES("{user_id}", "{key}")')
        schedule = context.user_data['schedule']
        if len(schedule) == 6:
            schedule += schedule
        c.execute(
            f'INSERT INTO schedule(group_id, schedules) '
            f'VALUES("{key}", '
            f'"{schedule}")')
        conn.commit()
        return ConversationHandler.END
    else:
        context.user_data['day'] = context.user_data['day'][1:]
        await update.message.reply_text(
            f"Какие предметы в {context.user_data['day'][0]}? "
            f"Напиши предметы через запятую "
            f"(регистр не важен)")
        return 3


async def authorized(update, context):
    """Авторизация по ключевому слову группы, запись пользователя в БД"""
    global conn, c
    locality = update.message.text
    user_id = str(update.message.from_user.id)

    if (locality,) in c.execute(f'SELECT group_id '
                                f'FROM schedule').fetchall():
        c.execute(
            f'INSERT INTO users(user_id, group_id) '
            f'VALUES ("{user_id}", "{locality}")')
        conn.commit()
        await update.message.reply_text("Вы успешно добавлены к расписанию")
    else:
        await update.message.reply_text("Такого расписания нет")
    return ConversationHandler.END


async def stop_schedule(update, context):
    """Досрочное прерывание диалога создания или добавления пользователя в
    расписание"""
    await update.message.reply_text("Создание расписания прервано!",
                                    reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def leave_the_schedule(update, context):
    """Удаление пользователя из расписания и БД"""
    global conn, c
    user_id = str(update.message.from_user.id)
    if (user_id,) in c.execute(f'SELECT user_id '
                               f'FROM users').fetchall():
        key = c.execute(f'SELECT group_id '
                        f'FROM users '
                        f'WHERE user_id="{user_id}"').fetchall()
        c.execute(f'DELETE FROM users '
                  f'WHERE user_id="{user_id}"')
        conn.commit()
        await update.message.reply_text(
            f"Вы успешно удалены из расписания {key[0][0]}")
    else:
        await update.message.reply_text(
            f"Вы не добавлены ни в одно расписание. Введите /start чтобы "
            f"создать расписание либо присоединиться к существующему")


async def get_schedule(update, context):
    """Отправка расписания на сегодня"""
    user_id = str(update.message.from_user.id)
    if (user_id,) in c.execute(f'SELECT user_id '
                               f'FROM users').fetchall():
        id_day_week = int(datetime.datetime.today().strftime('%w')) - 1
        group_id = c.execute(f'SELECT group_id '
                             f'FROM users '
                             f'WHERE user_id="{user_id}"').fetchone()[0]

        schedule = c.execute(f'SELECT schedules '
                             f'FROM schedule '
                             f'WHERE group_id="{group_id}"').fetchone()[0]
        await update.message.reply_text(f'Расписание на {day[id_day_week]}\n' +
                                        '\n'.join(eval(schedule.lower())[
                                                      id_day_week]))
    else:
        await update.message.reply_text(
            f"Вы не добавлены ни в одно расписание. Введите /start чтобы "
            f"создать расписание либо присоединиться к существующему")


async def add_task(update, context):
    """Стартовый вопрос добавления домашнего задания"""
    user_id = str(update.message.from_user.id)
    if (user_id,) in c.execute(f'SELECT user_id '
                               f'FROM users').fetchall():
        group_id = c.execute(f'SELECT group_id '
                             f'FROM users '
                             f'WHERE user_id="{user_id}"').fetchone()[0]
        schedules = c.execute(f'SELECT schedules '
                              f'FROM schedule '
                              f'WHERE group_id="{group_id}"').fetchone()[0]
        lessons = []
        for i in eval(schedules.lower()):
            lessons = lessons + i
        lessons = sorted(list(set(lessons)))
        len_list = int(len(lessons) ** 0.5) + 1
        lessons_markup = []
        for i in range(len_list):
            if (i + 1) * len_list > len(lessons):
                lessons_markup.append(lessons[i * len_list:])
            else:
                lessons_markup.append(lessons[i * len_list:(i + 1) * len_list])
        markup = ReplyKeyboardMarkup(lessons_markup, one_time_keyboard=False)
        await update.message.reply_text(
            "Начато добавление задания. Команда прерывания добавления "
            "задания: /stop \nПо какому предмету?",
            reply_markup=markup)
        return 1
    else:
        await update.message.reply_text(
            f"Вы не добавлены ни в одно расписание. Введите /start чтобы "
            f"создать расписание либо присоединиться к существующему")
        return ConversationHandler.END


async def adding_subject(update, context):
    """Сохранение информации о предмете, запрос введения задания"""
    context.user_data['homework'] = [update.message.text]

    await update.message.reply_text(
        f"Введите домашнее задание(текст, картинка, картинка+подпись)",
        reply_markup=ReplyKeyboardRemove())
    return 2


async def adding_task(update, context):
    """Сохранение информации о задании, запрос введения даты задания"""
    message = update.message
    task = dict()
    task_text = ''
    path = ''
    if message.photo:
        caption = message.caption or ''
        if caption.strip():
            task_text = caption

        photo = update.message.photo[-1]
        file_id = photo.file_id

        dir_name = 'images'
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        path = f'{dir_name}/{photo.file_id}.jpg'
        file = await context.bot.get_file(file_id)

        await file.download_to_drive(custom_path=path)

    elif message.text:
        task_text = message.text
    task['text'] = [task_text]
    task['photo'] = [path]
    context.user_data['homework'].append(task)

    reply_keyboard = [['Пропустить'], short_day,
                      ['Сл пн', 'Сл вт', 'Сл ср', 'Сл чт', 'Сл пт', 'Сл сб']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
    await update.message.reply_text(
        f"Введите:\n"
        f"Конкретную дату(дд.мм.гггг) - на которую нужно записать "
        f"задание \nили\n"
        f"<пн, вт, ср, чт, пт, сб> - задание будет записано на эту "
        f"неделю \nили\n"
        f"Сл <пн, вт, ср, чт, пт, сб> - задание будет записано на конкретный "
        f"день недели на следующей неделе \nили\n"
        f"Пропустить - задание будет записано на ближайшее "
        f"появление предмета",
        reply_markup=markup)
    return 3


async def adding_date(update, context):
    """Запись задания в БД"""
    global c, conn
    cur_date = False
    mess_of_date = update.message.text.lower()
    user_id = str(update.message.from_user.id)
    group_id = c.execute(f'SELECT group_id '
                         f'FROM users '
                         f'WHERE user_id="{user_id}"').fetchone()[0]

    if 'сл' in mess_of_date:
        today = datetime.date.today()
        ind_day_week = int(datetime.datetime.today().strftime('%w'))
        ind = short_day.index(mess_of_date.split()[1]) + 1

        cur_date = today + datetime.timedelta(
            days=7 - ind_day_week + ind)

    if mess_of_date in short_day:
        today = datetime.date.today()
        ind_day_week = int(datetime.datetime.today().strftime('%w'))
        ind = short_day.index(mess_of_date.split()[1]) + 1
        if ind > ind_day_week:
            cur_date = today + datetime.timedelta(
                days=ind_day_week + ind)
        else:
            cur_date = today - datetime.timedelta(
                days=ind_day_week - ind)

    if mess_of_date.count('.') == 2:
        mess_of_date = mess_of_date.split('.')
        try:
            cur_date = datetime.date(int(mess_of_date[2]),
                                     int(mess_of_date[1]), int(mess_of_date[0]))
        except (ValueError, IndexError):
            cur_date = False

    if not cur_date:
        ind_day_week = int(datetime.datetime.today().strftime('%w'))
        today = datetime.date.today()
        schedule = c.execute(f'SELECT schedules '
                             f'FROM schedule '
                             f'WHERE group_id="{group_id}"').fetchone()[0]
        for ind, i in enumerate(eval(schedule)):
            if context.user_data['homework'][0] in i and ind > ind_day_week:
                cur_date = today + datetime.timedelta(
                    days=ind - ind_day_week + ind // 7)
                break
    old_task = c.execute(
        f'SELECT task '
        f'FROM homework '
        f'WHERE group_id="{group_id}" AND '
        f'subject="{context.user_data["homework"][0]}" AND '
        f'day="{cur_date}"').fetchone()

    if old_task:
        old_task = eval(old_task[0])
        new_task = context.user_data["homework"][1]
        if new_task['text'][0]:
            if old_task['text'][0]:
                old_task['text'].append(new_task['text'][0])
            else:
                old_task['text'] = [new_task['text'][0]]
        if new_task['photo'][0]:
            if old_task['photo'][0]:
                old_task['photo'].append(new_task['photo'][0])
            else:
                old_task['photo'] = [new_task['photo'][0]]

        c.execute(f'UPDATE homework '
                  f'SET task="{old_task}" '
                  f'WHERE subject="{context.user_data["homework"][0]}" AND '
                  f'day="{cur_date}" AND group_id="{group_id}"')
    else:
        c.execute(f'INSERT INTO homework(subject, task, day, group_id) '
                  f'VALUES('
                  f'"{context.user_data["homework"][0]}", '
                  f'"{context.user_data["homework"][1]}", '
                  f'"{cur_date}", '
                  f'"{group_id}")')
    conn.commit()
    await update.message.reply_text(
        f"Задание записано на {cur_date}",
        reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def stop_add_task(update, context):
    """Досрочное прерывание диалога записи домашнего задания"""
    await update.message.reply_text("Добавление задания прервано",
                                    reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def get_task(update, context):
    """Cтартовый вопрос диалога получения домашнего задания по предмету или
    на день недели"""
    user_id = str(update.message.from_user.id)
    if (user_id,) in c.execute(f'SELECT user_id '
                               f'FROM users').fetchall():
        reply_keyboard = [['Предмет', 'День недели']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
        await update.message.reply_text(
            f"Выберите: 'Предмет', чтобы узнать все задания по предмету, "
            f"или 'День недели', чтобы узнать все задания на конкретный день. "
            f"Команда прерывания: /stop",
            reply_markup=markup)
        return 1
    else:
        await update.message.reply_text(
            f"Вы не добавлены ни в одно расписание. Введите /start чтобы "
            f"создать расписание либо присоединиться к существующему")
        return ConversationHandler.END


async def subject_or_day_week(update, context):
    """Вопрос о конкретном предмете или дне недели"""
    message = update.message.text
    if message == 'Предмет':
        user_id = str(update.message.from_user.id)
        group_id = c.execute(f'SELECT group_id '
                             f'FROM users '
                             f'WHERE user_id="{user_id}"').fetchone()[0]
        schedules = c.execute(f'SELECT schedules '
                              f'FROM schedule '
                              f'WHERE group_id="{group_id}"').fetchone()[0]
        lessons = []
        for i in eval(schedules.lower()):
            lessons = lessons + i
        lessons = sorted(list(set(lessons)))
        len_list = int(len(lessons) ** 0.5) + 1
        lessons_markup = []
        for i in range(len_list):
            if (i + 1) * len_list > len(lessons):
                lessons_markup.append(lessons[i * len_list:])
            else:
                lessons_markup.append(lessons[i * len_list:(i + 1) * len_list])
        markup = ReplyKeyboardMarkup(lessons_markup, one_time_keyboard=True)
        await update.message.reply_text(
            "По какому предмету?",
            reply_markup=markup)
        return 2
    elif message == 'День недели':
        reply_keyboard = [short_day]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        await update.message.reply_text(
            f"На какой день недели?",
            reply_markup=markup)
        return 3
    else:
        await update.message.reply_text(
            f"Неправильный формат ввода",
            reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


async def getting_task_subject(update, context):
    """Отправка всех заданий по предмету"""
    subject = update.message.text.lower()
    chat_id = update.message.chat_id
    user_id = str(update.message.from_user.id)
    group_id = c.execute(f'SELECT group_id '
                         f'FROM users '
                         f'WHERE user_id="{user_id}"').fetchone()[0]

    schedules = c.execute(f'SELECT schedules '
                          f'FROM schedule '
                          f'WHERE group_id="{group_id}"').fetchone()[0]
    lessons = []
    for i in eval(schedules.lower()):
        lessons = lessons + i
    lessons = sorted(list(set(lessons)))

    if subject not in lessons:
        await update.message.reply_text(
            f"Такого предмета нет в расписании",
            reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    task_list = c.execute(f'SELECT day, task '
                          f'FROM homework '
                          f'WHERE subject="{subject}" AND '
                          f'group_id ="{group_id}"').fetchall()

    task_list = sorted(task_list)
    homework_list = []
    for date, task in task_list:
        task = eval(task)
        if task['text'][0]:
            homework_list.append(date +
                                 ": \n\t" + '\n\t'.join(task['text']))
        if task['photo'][0]:
            homework_list.append([date, task['photo']])

    if not homework_list:
        await update.message.reply_text(
            f"По предмету {subject} нет домашних заданий.",
            reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(
            f"Задания по предмету {subject}:",
            reply_markup=ReplyKeyboardRemove())
        for homework in homework_list:
            if type(homework) == list:
                caption = homework[0]
                for path in homework[1]:
                    if path:
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=open(path, 'rb'),
                            caption=caption)
            else:
                await update.message.reply_text(
                    homework)

    return ConversationHandler.END


async def getting_task_day_week(update, context):
    """Отправка заданий на день недели"""
    mess_of_date = update.message.text.lower()

    user_id = str(update.message.from_user.id)
    group_id = c.execute(f'SELECT group_id '
                         f'FROM users '
                         f'WHERE user_id="{user_id}"').fetchone()[0]
    if mess_of_date in short_day:
        ind = short_day.index(mess_of_date) + 1
        today = datetime.date.today()
        ind_day_week = int(datetime.datetime.today().strftime('%w'))
        if ind < ind_day_week:
            cur_date = today - datetime.timedelta(days=ind_day_week - ind)
        else:
            cur_date = today + datetime.timedelta(days=ind - ind_day_week)
    else:
        await update.message.reply_text(
            f"Неправильный формат ввода",
            reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    task_list = c.execute(f'SELECT subject, task '
                          f'FROM homework '
                          f'WHERE day="{cur_date}" AND '
                          f'group_id ="{group_id}"').fetchall()
    homework_list = []
    photo_list = []
    for subject, task in task_list:
        task = eval(task)
        if task['text'][0]:
            homework_list.append(subject.upper() + ": \n\t" +
                                 '\n\t'.join(task['text']))
        if task['photo'][0]:
            photo_list.append([subject, task['photo']])

    if not homework_list and not photo_list:
        await update.message.reply_text(
            f"На {cur_date} нет домашнего задания.")
    else:
        chat_id = update.message.chat_id
        if homework_list:
            await update.message.reply_text(
                f'Задание на {cur_date}:\n' + '\n'.join(homework_list),
                reply_markup=ReplyKeyboardRemove())
        if photo_list:
            if not homework_list:
                await update.message.reply_text(
                    f'Задание на {cur_date}:',
                    reply_markup=ReplyKeyboardRemove())
            for subject, path in photo_list:
                for image_path in path:
                    await context.bot.send_photo(chat_id=chat_id,
                                                 photo=open(image_path, 'rb'),
                                                 caption=subject)
    return ConversationHandler.END


async def stop_get_task(update, context):
    """Досрочное прерывание диалога получения домашнего задания"""
    await update.message.reply_text(
        f"Видимо узнать домашку не сильно хочется.. Понимаю",
        reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def shuffle_schedule():
    """Изменение расписания в БД (нужно для чередующегося расписания) по
    воскресеньям"""
    global c, conn
    while True:
        if datetime.datetime.now().weekday() == 6:
            try:
                schedules = c.execute(f'SELECT schedules, group_id '
                                      f'FROM schedule"').fetchall()
                for schedule, group_id in schedules:
                    schedule = schedule[6:] + schedule[:6]
                    c.execute(f'UPDATE schedule'
                              f'SET schedules="{schedule}"'
                              f'WHERE group_id="{group_id}"')
                conn.commit()
            except (sqlite3.OperationalError, sqlite3.ProgrammingError):
                pass
        time.sleep(86400)


def main():
    application = Application.builder().token(
        '6073309009:AAGDg26EuFL_pWC3Xnc7SlnIe1k-C14MfQo').build()

    start_dialog = ConversationHandler(
        entry_points=[CommandHandler('schedule', schedule)],

        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               alternating_or_not)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               create_schedule)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               adding_subjects)],
            4: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               authorized)]

        },

        fallbacks=[CommandHandler('stop', stop_schedule)]
    )

    add_task_dialog = ConversationHandler(
        entry_points=[CommandHandler('add_task', add_task)],

        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               adding_subject)],
            2: [MessageHandler(filters.PHOTO & ~filters.COMMAND |
                               filters.TEXT & ~filters.COMMAND,
                               adding_task)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               adding_date)]

        },

        fallbacks=[CommandHandler('stop', stop_add_task)]
    )

    get_task_dialog = ConversationHandler(
        entry_points=[CommandHandler('get_task', get_task)],

        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               subject_or_day_week)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               getting_task_subject)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               getting_task_day_week)]

        },

        fallbacks=[CommandHandler('stop', stop_get_task)]
    )
    application.add_handler(CommandHandler('start', start))
    application.add_handler(start_dialog)
    application.add_handler(
        CommandHandler('leave_schedule', leave_the_schedule))
    application.add_handler(add_task_dialog)
    application.add_handler(get_task_dialog)

    application.add_handler(CommandHandler('get_schedule', get_schedule))
    threading.Thread(target=shuffle_schedule, daemon=True).start()

    application.run_polling()


if __name__ == '__main__':
    main()
