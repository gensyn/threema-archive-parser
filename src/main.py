import argparse
import re
from os import listdir
from os.path import isdir, isfile, join, basename
from pathlib import Path

FILE_REGEX = [
    "<([a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12}\.([a-z0-9]{3,4}))>",
    "<([a-z0-9]{16}-[a-z]*-[0-9]{8}-[0-9]{6,10}\.([a-z0-9]{3,4}))>"
]

URL_REGEX = "(https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)"

parser = argparse.ArgumentParser("Threema HTML Generator")
parser.add_argument("folder", help="The folder containing the Threema Chats.")
args = parser.parse_args()

folder = args.folder

if not isdir(folder):
    raise ValueError("Given value for \"folder\" is not an acutally folder on this machine.")


def create_html(path):
    messages_path = join(path, "messages.txt")

    if not isfile(messages_path):
        raise ValueError(f"No messages.txt in {path}")

    name = basename(path)

    with open(messages_path, "r") as f:
        messages = '\n'.join([f"<p>{message}</p>" for message in f.readlines()])

    template = Path("src/index_template.html").read_text()

    html = template.replace("$title", name).replace("$content", f"<div>{messages}</div>")

    for regex in FILE_REGEX:
        matches = re.findall(regex, html)

        for match in matches:
            if not isfile(join(path, match[0])):
                html = html.replace(f"<{match[0]}>", f"<a href=\"{match[0]}\">DATEI FEHLT</a>")
            elif match[1] in ["jpg", "jpeg", "png"]:
                html = html.replace(f"<{match[0]}>", f"</p><p><a href=\"{match[0]}\"><img src=\"{match[0]}\" width=300 /></a></p><p>")
            elif match[1] in ["mp4"]:
                html = html.replace(f"<{match[0]}>", f"</p><p><a href=\"{match[0]}\"><video controls><source src=\"{match[0]}\" /></video></a></p><p>")
            else:
                html = html.replace(f"<{match[0]}>", f"<a href=\"{match[0]}\">{match[0]}</a>")

    matches = list(set(re.findall(URL_REGEX, html)))

    for match in matches:
        html = html.replace(match, f"<a href=\"{match}\">{match}</a>")

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
