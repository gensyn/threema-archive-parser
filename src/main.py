import argparse
import re
from os import listdir
from os.path import isdir, isfile, join, basename
from pathlib import Path

FILE_REGEX = "(&lt;((?:[a-f0-9]{8}|[a-f0-9]{16})-.*?\.([a-z0-9]{3,4}))&gt;)"

URL_REGEX = "(https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)"

MESSAGE_REGEX = "\[(\d{1,2}\.\d{1,2}\.\d{4}), (\d{1,2}:\d{2})\] (.+?): (.*)"

parser = argparse.ArgumentParser("Threema HTML Generator")
parser.add_argument("folder", help="The folder containing the Threema Chats.")
args = parser.parse_args()

folder = args.folder

if not isdir(folder):
    raise ValueError("Given value for \"folder\" is not an acutal folder on this machine.")


def parse_message(path, message):
    message = message.replace("<", "&lt;").replace(">", "&gt;")

    matches = re.findall(FILE_REGEX, message)

    for match in matches:
        if not isfile(join(path, match[1])):
            message = message.replace(f"{match[0]}", f"<a href=\"{match[1]}\">DATEI FEHLT</a>")
        elif match[2] in ["jpg", "jpeg", "png"]:
            message = message.replace(f"{match[0]}", f"<br/><a href=\"{match[1]}\"><img src=\"{match[1]}\" width=300 /></a><br />")
        elif match[2] in ["mp4"]:
            message = message.replace(f"{match[0]}", f"<br /><a href=\"{match[1]}\"><video controls><source src=\"{match[1]}\" /></video></a><br />")
        else:
            message = message.replace(f"{match[0]}", f"<a href=\"{match[1]}\">{match[1]}</a>")

    matches = list(set(re.findall(URL_REGEX, message)))

    for match in matches:
        message = message.replace(match, f"<a href=\"{match}\">{match}</a>")

    match = re.search(MESSAGE_REGEX, message)

    if match:
        return match.group(1), match.group(2), match.group(3), match.group(4)

    return None, None, None, message


def create_html(path):
    messages_path = join(path, "messages.txt")

    if not isfile(messages_path):
        raise ValueError(f"No messages.txt in {path}")

    name = basename(path)

    with open(messages_path, "r") as f:
        messages = f.readlines()

    content = ""
    previous_date = None
    previous_time = None
    previous_align = None

    for message in messages:
        date, time, author, message_content = parse_message(path, message)

        if not date:
            # this message is just a new line of the previous message
            content += f"<br />{message_content}"
            continue

        align = "right" if author == "Ich" else "left"

        if previous_time:
            # this is a new message - write time of previous message
            content += f"<br /><span class=\"time time-{previous_align}\">{previous_time}</span>"

        if previous_date:
            # we are not processing the first element
            content += "</div></div>"

        if date != previous_date:
            content += f"<div class=\"date\">{date}</div>"

        content += f'<div class=\"wrapper wrapper-{align}\"><div class=\"message {align}\">'

        if author != "Ich":
            content += f'<span class=\"author">{author}</span><br />'

        content += f"{message_content}"

        previous_date = date
        previous_time = time
        previous_align = align

    content += "</div></div>"

    template = Path("src/index_template.html").read_text()

    html = template.replace("$title", name).replace("$content", f"{content}")

    with open(join(path, "index.html"), "w") as f:
        f.write(html)


def traverse(path):
    items = listdir(path)

    if "messages.txt" in items:
        create_html(path)
        return

    for item in listdir(path):
        full_path = join(path, item)

        if isdir(full_path):
            traverse(full_path)


traverse(folder)
