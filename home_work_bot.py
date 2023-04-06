import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, Application
import sqlite3
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)

logger = logging.getLogger(__name__)

conn = sqlite3.connect('school_bot.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS schedule
             (day TEXT, subject1 TEXT, subject2 TEXT, 
             subject3 TEXT, subject4 TEXT, subject5 TEXT, 
             subject6 TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS homework
             (subject TEXT, task TEXT, day TEXT)''')

dispatcher = Application.builder().token('5251331561:AAERoqyk9eYXq8sv-dCospS2W8n-hJC8Nhs').build()


async def start(update, context):
    await update.message.reply_text("Привет! Я школьный бот! Что нужно сделать?")


async def add_rasp(update, context):
    global day
    day = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    await update.message.reply_text("Какие предметы в Понедельник?")


async def handle_subjects(update, context):
    global day
    if not day:
        await update.message.reply_text("Дни недели закончились! Используйте /add_work, чтобы добавить задание.")
    else:
        subject_list = update.message.text.split(", ")
        c.execute("INSERT INTO schedule VALUES (?, ?, ?, ?, ?, ?, ?)", (
            day.pop(0), subject_list[0], subject_list[1], subject_list[2], subject_list[3], subject_list[4],
            subject_list[5]))
        conn.commit()
        if day:
            await update.message.reply_text("Какие предметы в " + day[0] + "?")


async def add_work(update, context):
    await update.message.reply_text("Введите предмет, домашнее задание и день (через запятую).")


async def handle_homework(update, context):
    homework_list = update.message.text.split(", ")
    c.execute("INSERT INTO homework VALUES (?, ?, ?)", (homework_list[0], homework_list[1], homework_list[2]))
    conn.commit()
    await update.message.reply_text("Домашнее задание добавлено.")


async def get_work(update, context):
    query = str(update.message.text).lower()
    if query in ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота']:
        c.execute("SELECT subject1, subject2, subject3, subject4, subject5, subject6 FROM schedule WHERE day=?",
                  (query,))
        subject_list = c.fetchone()
        homework_list = []
        for subject in subject_list:
            c.execute("SELECT task FROM homework WHERE subject=? AND day=?", (subject, query))
            task = c.fetchone()
            if task:
                homework_list.append(subject + ": " + task[0])
        if not homework_list:
            await update.message.reply_text("На этот день нет домашнего задания.")
        else:
            await update.message.reply_text("\n".join(homework_list))
    else:
        c.execute("SELECT task FROM homework WHERE subject=?", (query,))
        task = c.fetchone()
        if task:
            await update.message.reply_text(query.capitalize() + ": " + task[0])
        else:
            await update.message.reply_text("На этот предмет нет домашнего задания.")


dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('add_rasp', add_rasp))
dispatcher.add_handler(CommandHandler('add_work', add_work))
dispatcher.add_handler(CommandHandler('get_work', get_work))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subjects))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_homework))

dispatcher.run_polling()
