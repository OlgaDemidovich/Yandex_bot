from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, \
    Application, ConversationHandler
import sqlite3
import logging
import random
import string
import datetime

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
             (id INTEGER PRIMARY KEY, subject TEXT, task TEXT, day TEXT)''')
day = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
schedule = []


async def stop(update, context):
    await update.message.reply_text("Создание расписания прервано!",
                                    reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def start(update, context):
    reply_keyboard = [['Создать расписание', 'Присоединиться к расписанию']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
    await update.message.reply_text(
        'Привет! Я школьный бот! Выбери: создать расписание или '
        'присоединиться к уже существующему, которое создал кто-то из '
        'вашего класса/группы. Команда прерывания создания расписания: /stop',
        reply_markup=markup)
    return 1


async def before_start(update, context):
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
    global day
    locality = update.message.text
    if locality == 'Чередующееся':
        day = day + day
    elif 'Не чередующееся':
        day = day
    await update.message.reply_text(
        "Какое расписание в Понедельник? Напиши предметы через запятую",
        reply_markup=ReplyKeyboardRemove())
    return 3


async def handle_subjects(update, context):
    global day, schedule, conn, c
    schedule.append(update.message.text.split(", "))

    if len(day) == 1:
        while True:
            letters_and_digits = string.ascii_letters + string.digits
            key = ''.join(random.sample(letters_and_digits, 6))

            if key not in c.execute(f'SELECT group_id '
                                    f'FROM users').fetchall():
                break
        await update.message.reply_text(f"Дни недели закончились! "
                                        f"Ваше ключевое слово расписания: ")
        await update.message.reply_text(key)
        print(str(schedule))
        user_id = update.message.from_user.id
        c.execute(
            f'INSERT INTO users(user_id, group_id) '
            f'VALUES("{user_id}", "{key}")')
        c.execute(
            f'INSERT INTO schedule(group_id, schedules) '
            f'VALUES("{key}", '
            f'"{schedule}")')
        conn.commit()
        return ConversationHandler.END
    else:
        day.pop(0)
        await update.message.reply_text(f"Какие предметы в {day[0]}?"
                                        f" Напиши предметы через запятую")
        return 3


async def authorized(update, context):
    global conn, c
    locality = update.message.text
    user_id = str(update.message.from_user.id)
    print((locality, user_id))
    print(c.execute(f'SELECT group_id, user_id '
                    f'FROM users').fetchall())

    if (locality, user_id) in \
            c.execute(f'SELECT group_id, user_id '
                      f'FROM users').fetchall():
        await update.message.reply_text("Вы уже добавлены к этому расписанию")
        return ConversationHandler.END
    elif user_id in c.execute(f'SELECT user_id '
                              f'FROM users').fetchall()[0]:
        await update.message.reply_text(
            "Вы уже добавлены к другому расписанию.\n "
            "Введите /leave_the_schedule чтобы покинуть расписание")
        return ConversationHandler.END
    elif locality in c.execute(f'SELECT group_id '
                               f'FROM users').fetchall()[0]:
        c.execute(
            f'INSERT INTO users(user_id, group_id) '
            f'VALUES ("{user_id}", "{locality}")')
        conn.commit()
        await update.message.reply_text("Вы успешно добавлены к расписанию")
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Такого расписания нет")


async def help_command(update, context):
    await update.message.reply_text(
        "/start - создать или присединиться к расписанию\n"
        "/add_work <предмет>, <задание>, <опционально: дата>\n"
        "/get_work <предмет или день недели>\n"
        "/leave_schedule - покинуть данное расписание")


async def add_work(update, context):
    await update.message.reply_text(
        "Введите предмет, домашнее задание и день (через запятую).")


async def leave_the_schedule(update, context):
    global conn, c
    user_id = str(update.message.from_user.id)
    if user_id in c.execute(f'SELECT user_id '
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


# async def alternating_or_not(update, context):
#     global day
#         subject_list = update.message.text.split(", ")
#         c.execute("INSERT INTO schedule VALUES (?, ?, ?, ?, ?, ?, ?)", (
#             , subject_list))
#         conn.commit()
#         if day:
#             await update.message.reply_text(
#                 "Какие предметы в " + day[0] + "?")
#     return 2
#
#
# async def add_rasp(update, context):
#     global day
#     day = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
#     await update.message.reply_text("Какие предметы в Понедельник?")
#
#
# async def handle_subjects(update, context):
#     global day
#     if not day:
#         await update.message.reply_text(
#             "Дни недели закончились! Используйте /add_work, чтобы добавить задание.")
#     else:
#         subject_list = update.message.text.split(", ")
#         c.execute("INSERT INTO schedule VALUES (?, ?, ?, ?, ?, ?, ?)", (
#             day.pop(0), subject_list))
#         conn.commit()
#         if day:
#             await update.message.reply_text("Какие предметы в " + day[0] + "?")
#
#
# async def add_work(update, context):
#     await update.message.reply_text(
#         "Введите предмет, домашнее задание и день (через запятую).")
#
#
# async def handle_homework(update, context):
#     homework_list = update.message.text.split(", ")
#     c.execute("INSERT INTO homework VALUES (?, ?, ?)",
#               (homework_list[0], homework_list[1], homework_list[2]))
#     conn.commit()
#     await update.message.reply_text("Домашнее задание добавлено.")
#
#
# async def get_work(update, context):
#     query = str(update.message.text).lower()
#     if query in ['понедельник', 'вторник', 'среда', 'четверг', 'пятница',
#                  'суббота']:
#         c.execute(
#             "SELECT subject1, subject2, subject3, subject4, subject5, subject6 FROM schedule WHERE day=?",
#             (query,))
#         subject_list = c.fetchone()
#         homework_list = []
#         for subject in subject_list:
#             c.execute("SELECT task FROM homework WHERE subject=? AND day=?",
#                       (subject, query))
#             task = c.fetchone()
#             if task:
#                 homework_list.append(subject + ": " + task[0])
#         if not homework_list:
#             await update.message.reply_text(
#                 "На этот день нет домашнего задания.")
#         else:
#             await update.message.reply_text("\n".join(homework_list))
#     else:
#         c.execute("SELECT task FROM homework WHERE subject=?", (query,))
#         task = c.fetchone()
#         if task:
#             await update.message.reply_text(query.capitalize() + ": " + task[0])
#         else:
#             await update.message.reply_text(
#                 "На этот предмет нет домашнего задания.")


def main():
    application = Application.builder().token(
        '5251331561:AAERoqyk9eYXq8sv-dCospS2W8n-hJC8Nhs').build()

    conv_handler = ConversationHandler(
        # Точка входа в диалог.
        # В данном случае — команда /start. Она задаёт первый вопрос.
        entry_points=[CommandHandler('start', start)],

        # Состояние внутри диалога.
        # Вариант с двумя обработчиками, фильтрующими текстовые сообщения.
        states={
            # Функция читает ответ на первый вопрос и задаёт второй.
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               before_start)],
            # Функция читает ответ на второй вопрос и завершает диалог.
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               create_schedule)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               handle_subjects)],
            4: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                               authorized)]

        },

        # Точка прерывания диалога. В данном случае — команда /stop.
        fallbacks=[CommandHandler('stop', stop)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(
        CommandHandler('leave_schedule', leave_the_schedule))

    # application.add_handler(CommandHandler('add_work', add_work))
    # application.add_handler(CommandHandler('get_work', get_work))
    # application.add_handler(
    #     MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subjects))
    # application.add_handler(
    #     MessageHandler(filters.TEXT & ~filters.COMMAND, handle_homework))

    application.run_polling()


if __name__ == '__main__':
    main()
