import argparse
from datetime import datetime
from typing import List, Tuple, Dict

import mysql.connector
import os
import re
from contextlib import closing
from os import listdir
from os.path import isdir, isfile, join, basename

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(join(dname, ".."))

REGEX_SPLIT_BY_NAME = (r"\[(\d{1,2})\.(\d{1,2})\.(\d{4}),\s(\d{1,2}):(\d{2})\]\s(.+?):\s(.*?)("
                       r"?=\n\[\d{1,2}\.\d{1,2}\.\d{4},\s\d{1,2}:\d{2}\]|$)")

FILE_REGEX = (r"(Bild|Video|Audio|Datei)(?:\:\s){0,1}(?:\s\(\d\d\:\d\d\)){0,1}(.*?)\s<((?:["
              r"a-f0-9]{8}|[a-f0-9]{16})-.*?\.[a-z0-9]{3,4})>")

URL_REGEX = r'(?:(?:http|https|ftp)://|www\.)[a-zA-Z0-9-._~:/?#[\]@!$&\'()*+,;=%]+(?:\.[a-zA-Z]{2,})(?:/[^\s]*)?|(?:^|\s)(www\.[\S]+(?:\.[a-zA-Z]{2,})(?:/[^\s]*)?)'

GEO_REGEX = r"Ort(?:\:\s){0,1}(.*?)\s(?:<geo:([0-9\.]*),([0-9\.]*)\?.*>)"

DATE_FORMAT = "%Y-%m-%d %H:%M"

MESSAGE_ID = -1

parser = argparse.ArgumentParser("Threema DB generator")
parser.add_argument("--user", help="The chat messages' owner.")
parser.add_argument("--folder", help="The folder containing the Threema Chats.")
parser.add_argument("--dbHost", help="The DB host.")
parser.add_argument("--dbUser", help="The DB user.")
parser.add_argument("--dbPassword", help="The DB password.")
parser.add_argument("--dbDb", help="The DB DB.")
args = parser.parse_args()

user = args.user.lower()

if user not in ["christoph", "juliane"]:
    raise ValueError("Invalid user")

folder = args.folder

if not isdir(folder):
    raise ValueError("Given value for \"folder\" is not an actual folder on this machine.")

db_host = args.dbHost
db_user = args.dbUser
db_password = args.dbPassword
db_db = args.dbDb

if not db_host or not db_user or not db_password or not db_db:
    raise ValueError("Missing DB settings.")


def get_db_connection():
    return mysql.connector.connect(
        host=db_host, user=db_user, password=db_password, database=db_db)



def parse_message(path, message):
    message_parsed: str = message
    has_no_media: bool = True
    image: str = ""
    video: str = ""
    audio: str = ""
    file: str = ""
    location: str = ""
    has_link: bool = False
    is_media_missing: bool = False

    files = re.findall(FILE_REGEX, message, re.DOTALL)
    base = basename(path)

    if files:
        has_no_media = False

        for match in files:
            message_parsed = match[1]
            link = f"{base}/{match[2]}".replace("'", "''")
            if not isfile(join(path, match[2])):
                is_media_missing = True

            if match[0] == "Bild":
                image = link
            elif match[0] == "Video":
                video = link
            elif match[0] == "Audio":
                audio = link
            else:
                file = link

    urls = re.findall(URL_REGEX, message_parsed)

    if urls:
        has_link = True
        has_no_media = False

        def replace_url(match):
            url = match.group(0).strip()
            text = url
            if not '://' in url:
                url = '//' + url
            return f'<a href="{url}" target="_blank">{text}</a>'

        message_parsed = re.sub(URL_REGEX, replace_url, message_parsed)

    geos = re.findall(GEO_REGEX, message_parsed)

    if geos:
        has_no_media = False

        message_parsed = geos[0][0]

        lat = geos[0][1]
        lon = geos[0][2]

        location = f"{lat},{lon}"

    message_parsed = message_parsed.replace("\n", "<br>").replace("'", "''")

    return (message_parsed, has_no_media, image, video, audio, file, location, has_link,
            is_media_missing)


def parse(path):
    messages_path = join(path, "messages.txt")

    if not isfile(messages_path):
        raise ValueError(f"No messages.txt in {path}")

    with open(messages_path, "r") as f:
        messages = f.read()

    messages_tuple = re.findall(REGEX_SPLIT_BY_NAME, messages, re.DOTALL)

    messages_list = []

    for message in messages_tuple:
        messages_list.append(get_message_details(message))

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()

        chat = basename(path)

        cursor.execute(f"SELECT max(chat_id) FROM {user}")
        result = cursor.fetchone()[0]

        if result is None:
            chat_id = 1
        else:
            chat_id = result + 1

        for i, message in enumerate(messages_list):
            message_parsed, message_has_no_media, message_image, message_video, message_audio, message_file, message_location, message_has_link, message_is_media_missing = parse_message(path, message["message"])

            context = find_context(messages_list, i)

            insert_query = f'''
            INSERT INTO {user} (message_id, chat, chat_id, author, date, time, 
            message, has_no_media, image, video, audio,
            file, location, has_link, is_media_missing, context) VALUES
            ('{message["id"]}', '{chat}', {chat_id}, '{message["author"]}', '{message["date"]}', '{message["time"]}',
            '{message_parsed}', {message_has_no_media}, '{message_image}', '{message_video}', '{message_audio}',
            '{message_file}', '{message_location}', {message_has_link}, {message_is_media_missing}, '{context}');
            '''
            cursor.execute(insert_query)

        cursor.close()
        connection.commit()

    pass


def find_context(messages: List[Dict], index: int) -> str:
    context = []

    # gather at least 5 context messages before the message and then every message within 30 minutes of the previous
    if len(messages[:index]) >= 5:
        context.extend(messages[index-5:index])
    else:
        context.extend(messages[:index])

    if len(messages[:index]) > 5:
        for i in range(index-5, 0 , -1):
            dt_prev = get_datetime(context[0])
            dt_current = get_datetime(messages[i])

            if abs((dt_prev - dt_current).total_seconds()) <= 1800:
                context.insert(0, messages[i])
            else:
                break

    # gather at least 5 context messages after the message and then every message within 30 minutes of the previous
    if len(messages[index+1:]) >= 5:
        context.extend(messages[index+1:index+6])
    else:
        context.extend(messages[index:])

    if len(messages[index+1:]) > 5:
        for i in range(len(messages))[index+6:]:
            dt_prev = get_datetime(context[-1])
            dt_current = get_datetime(messages[i])

            if abs((dt_prev - dt_current).total_seconds()) <= 1800:
                context.append(messages[i])
            else:
                break

    return ",".join([str(m["id"]) for m in context])


def get_message_details(message: Tuple) -> Dict:
    author = message[5]
    if author.startswith("~"):
        author = author[1:]

    m_date = f'{message[2]}-{str(message[1].zfill(2))}-{str(message[0].zfill(2))}'

    m_time = f'{message[3]}:{message[4]}'

    return {
        "id": get_next_message_id(),
        "author": author,
        "date": m_date,
        "time": m_time,
        "message": message[6]
    }

def get_next_message_id() -> int:
    global MESSAGE_ID
    MESSAGE_ID += 1
    return MESSAGE_ID


def get_datetime(message: Dict) -> datetime:
    dt_string = f"{message["date"]} {message["time"]}"
    return datetime.strptime(dt_string, DATE_FORMAT)


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
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()

        drop_table_query = f'''
        DROP TABLE IF EXISTS {user};
        '''
        cursor.execute(drop_table_query)

        create_table_query = f'''
        CREATE TABLE {user} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id INT NOT NULL,
            chat VARCHAR(255) NOT NULL,
            chat_id INT NOT NULL,
            author VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            time TIME NOT NULL,
            message VARCHAR(8191) NOT NULL,
            has_no_media BOOLEAN NOT NULL,
            image VARCHAR(255) NOT NULL,
            video VARCHAR(255) NOT NULL,
            audio VARCHAR(255) NOT NULL,
            file VARCHAR(255) NOT NULL,
            location VARCHAR(255) NOT NULL,
            has_link BOOLEAN NOT NULL,
            is_media_missing BOOLEAN NOT NULL,
            context VARCHAR(4095) NOT NULL
        );
        '''
        cursor.execute(create_table_query)

        cursor.close()
        connection.commit()


init_db()
traverse(folder)
