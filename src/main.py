import argparse
import os
import re
import shutil
import sqlite3
from os import listdir, remove, mknod
from os.path import isdir, isfile, join, basename

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(join(dname, ".."))

REGEX_SPLIT_BY_NAME = (r"\[(\d{1,2})\.(\d{1,2})\.(\d{4}),\s(\d{1,2}):(\d{2})\]\s(.+?):\s(.*?)("
                       r"?=\n\[\d{1,2}\.\d{1,2}\.\d{4},\s\d{1,2}:\d{2}\]|$)")

FILE_REGEX = (r"(Bild|Video|Audio|Datei)(?:\:\s){0,1}(?:\s\(\d\d\:\d\d\)){0,1}(.*?)\s<((?:["
              r"a-f0-9]{8}|[a-f0-9]{16})-.*?\.[a-z0-9]{3,4})>")

URL_REGEX = r"(https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)"

GEO_REGEX = r"Ort(?:\:\s){0,1}(.*?)\s(?:<geo:([0-9\.]*),([0-9\.]*)\?.*>)"

parser = argparse.ArgumentParser("Threema SQLite generator")
parser.add_argument("--user", help="The chat messages' owner.")
parser.add_argument("--folder", help="The folder containing the Threema Chats.")
parser.add_argument("--dbFile", help="The SQLite db file.")
args = parser.parse_args()

user = args.user.lower()

if user not in ["christoph", "juliane"]:
    raise ValueError("Invalid user")

folder = args.folder

if not isdir(folder):
    raise ValueError("Given value for \"folder\" is not an actual folder on this machine.")

db_file = args.dbFile

tmp_file = "/tmp/threema.sqlite"


def parse_message(path, message):
    message_parsed = message
    has_no_media = 1
    image = ""
    video = ""
    audio = ""
    file = ""
    location = ""
    has_link = 0
    is_media_missing = 0

    files = re.findall(FILE_REGEX, message, re.DOTALL)
    base = basename(path)

    urls = list(set(re.findall(URL_REGEX, message)))

    if files:
        has_no_media = 0

        for match in files:
            message_parsed = match[1]
            link = f"{base}/{match[2]}".replace("'", "''")
            if not isfile(join(path, match[2])):
                is_media_missing = 1

            if match[0] == "Bild":
                image = link
            elif match[0] == "Video":
                video = link
            elif match[0] == "Audio":
                audio = link
            else:
                file = link

    if urls:
        has_link = 1
        has_no_media = 0

    geos = re.findall(GEO_REGEX, message)

    if geos:
        has_no_media = 0

        message_parsed = geos[0][0]

        lat = geos[0][1]
        lon = geos[0][2]

        location = f"{lat},{lon}"

    message_parsed = message_parsed.replace("'", "''")

    return (message_parsed, has_no_media, image, video, audio, file, location, has_link,
            is_media_missing)


def parse(path):
    messages_path = join(path, "messages.txt")

    if not isfile(messages_path):
        raise ValueError(f"No messages.txt in {path}")

    with open(messages_path, "r") as f:
        messages = f.read()

    messages_by_name = re.findall(REGEX_SPLIT_BY_NAME, messages, re.DOTALL)

    with sqlite3.connect(tmp_file) as connection:
        cursor = connection.cursor()

        chat = basename(path)

        result = cursor.execute(f"SELECT max(chat_id) FROM {user}").fetchone()[0]

        if result is None:
            chat_id = 1
        else:
            chat_id = result + 1

        for message in messages_by_name:
            message_parsed, message_has_no_media, message_image, message_video, message_audio, message_file, message_location, message_has_link, message_is_media_missing = parse_message(path, message[6])

            insert_query = f'''
            INSERT INTO {user} (chat, chat_id, author, date, time, message, has_no_media, image, 
            video, audio, file, location, has_link, is_media_missing) VALUES
            ('{chat}', {chat_id}, '{message[5]}', '{message[2]}-{str(message[1].zfill(2))}-
{str(message[0].zfill(2))}', '{message[3]}:{message[4]}', '{message_parsed}', 
{message_has_no_media}, '{message_image}', '{message_video}', '{message_audio}', 
'{message_file}', '{message_location}', {message_has_link}, {message_is_media_missing});
            '''
            cursor.execute(insert_query)

        cursor.close()
        connection.commit()

    pass


def traverse(path):
    items = listdir(path)

    if "messages.txt" in items:
        parse(path)
        return

    for item in listdir(path):
        full_path = join(path, item)

        if isdir(full_path):
            traverse(full_path)


def init_db():
    if isfile(tmp_file):
        remove(tmp_file)

    if not isfile(db_file):
        mknod(tmp_file)

    with sqlite3.connect(tmp_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        cursor = connection.cursor()

        drop_table_query = f'''
        DROP TABLE IF EXISTS {user};
        '''
        cursor.execute(drop_table_query)

        create_table_query = f'''
        CREATE TABLE {user} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            message TEXT NOT NULL,
            has_no_media INTEGER NOT NULL,
            image string NOT NULL,
            video string NOT NULL,
            audio string NOT NULL,
            file string NOT NULL,
            location string NOT NULL,
            has_link INTEGER NOT NULL,
            is_media_missing INTEGER NOT NULL
        );
        '''
        cursor.execute(create_table_query)

        cursor.close()
        connection.commit()


init_db()
traverse(folder)
shutil.copyfile(tmp_file, db_file)
