import argparse
import os
import re
import shutil
from os import listdir
from os.path import isdir, isfile, join, basename
from pathlib import Path

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(join(dname, ".."))

FILE_REGEX = "(&lt;((?:[a-f0-9]{8}|[a-f0-9]{16})-.*?\.([a-z0-9]{3,4}))&gt;)"

URL_REGEX = "(https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)"

MESSAGE_REGEX = "\[(\d{1,2}\.\d{1,2}\.\d{4}), (\d{1,2}:\d{2})\] (.+?): (.*)"

GEO_REGEX = "(&lt;geo:([0-9\.]*),([0-9\.]*)\?.*&gt;)"

CLASS_NO_MEDIA = "no_media"
CLASS_IMAGE = "image"
CLASS_VIDEO = "video"
CLASS_AUDIO = "audio"
CLASS_FILE = "file"
CLASS_LINK = "link"
CLASS_LOCATION = "location"

parser = argparse.ArgumentParser("Threema HTML Generator")
parser.add_argument("folder", help="The folder containing the Threema Chats.")
args = parser.parse_args()

folder = args.folder

if not isdir(folder):
    raise ValueError("Given value for \"folder\" is not an acutal folder on this machine.")


def parse_message(path, message):
    has_image = False
    has_video = False
    has_audio = False
    has_file = False
    has_link = False
    has_location = False

    message = message.replace("<", "&lt;").replace(">", "&gt;")

    files = re.findall(FILE_REGEX, message)

    if files:
        for match in files:
            if not isfile(join(path, match[1])):
                message = message.replace(match[0], f"<a href=\"{match[1]}\">MISSING FILE</a>")
            elif match[2] in ["jpg", "jpeg", "png", "gif"]:
                has_image = True
                message = message.replace(match[0], f"<br/><a href=\"{match[1]}\"><img src=\"{match[1]}\" width=300 /></a><br />")
            elif match[2] in ["mp4"]:
                has_video = True
                message = message.replace(match[0], f"<br /><a href=\"{match[1]}\"><video controls><source src=\"{match[1]}\" /></video></a><br />")
            elif match[2] in ["aac", "opus"]:
                has_audio = True
                message = message.replace(match[0], f"<br /><a href=\"{match[1]}\"><audio controls src=\"{match[1]}\"></audio></a><br />")
            else:
                has_file = True
                message = message.replace(match[0], f"<a href=\"{match[1]}\">{match[1]}</a>")

    urls = list(set(re.findall(URL_REGEX, message)))

    if urls:
        has_link = True

        for match in urls:
            message = message.replace(match, f"<a href=\"{match}\">{match}</a>")

    geos = re.findall(GEO_REGEX, message)

    if geos:
        has_location = True

        for match in geos:
            lat = match[1]
            lon = match[2]

            # the higher this number the further zoomed out the map
            zoom = 0.0016

            box_1 = str(float(lon) - zoom)
            box_2 = str(float(lat) - zoom)
            box_3 = str(float(lon) + zoom)
            box_4 = str(float(lat) + zoom)

            message = message.replace(match[0], f"<iframe src=\"https://www.openstreetmap.org/export/embed.html?bbox={box_1}%2C{box_2}%2C{box_3}%2C{box_4}&amp;layer=mapnik&amp;marker={lat}%2C{lon}\"></iframe><br/><small><a href=\"https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}#map=15/{lat}/{lon}\">View Larger Map</a></small>")

    message_parts = re.search(MESSAGE_REGEX, message)

    if message_parts:
        return message_parts.group(1), message_parts.group(2), message_parts.group(3), message_parts.group(4), has_image, has_video, has_audio, has_file, has_link, has_location

    return None, None, None, message, has_image, has_video, has_audio, has_file, has_link, has_location


def create_html(path):
    message_count = 0
    no_media_count = 0
    image_count = 0
    video_count = 0
    audio_count = 0
    file_count = 0
    link_count = 0
    location_count = 0

    messages_path = join(path, "messages.txt")

    if not isfile(messages_path):
        raise ValueError(f"No messages.txt in {path}")

    name = basename(path)

    with open(messages_path, "r") as f:
        messages = f.readlines()

    min_date = None
    max_date = None

    content = ""
    previous_date = None
    previous_time = None
    previous_align = None

    for i in range(len(messages)):
        date, time, author, message_content, message_has_image, message_has_video, message_has_audio, message_has_file, message_has_link, message_has_location = parse_message(path, messages[i])

        if not date:
            # this message is just a new line of the previous message and was already processed
            continue

        classes = []

        j = i+1
        while j < len(messages):
            # look ahead for messages belonging to this one but seperated by line breaks
            next_date, _, _, next_message_content, next_has_image, next_has_video, next_has_audio, next_has_file, next_has_link, next_has_location = parse_message(path, messages[j])

            if next_date:
                # new message found, no further look-ahead needed
                break

            message_content += f"<br />{next_message_content}"

            if next_has_image:
                message_has_image = True

            if next_has_video:
                message_has_video = True

            if next_has_audio:
                message_has_audio = True

            if next_has_file:
                message_has_file = True

            if next_has_link:
                message_has_link = True

            if next_has_location:
                message_has_location = True

            j += 1

        message_count += 1

        if message_has_image:
            classes.append(CLASS_IMAGE)
            image_count += 1

        if message_has_video:
            classes.append(CLASS_VIDEO)
            video_count += 1

        if message_has_audio:
            classes.append(CLASS_AUDIO)
            audio_count += 1

        if message_has_file:
            classes.append(CLASS_FILE)
            file_count += 1

        if message_has_link:
            classes.append(CLASS_LINK)
            link_count += 1

        if message_has_location:
            classes.append(CLASS_LOCATION)
            location_count += 1

        if not classes:
            classes.append(CLASS_NO_MEDIA)
            no_media_count += 1

        align = "right" if author == "Ich" else "left"

        if previous_time:
            # this is a new message - write time of previous message
            content += f"<br /><span class=\"time time-{previous_align}\">{previous_time}</span>"

        if previous_date:
            # we are not processing the first element
            content += "</div></div>"

        date_parts = date.split(".")

        day = date_parts[0].zfill(2)
        month = date_parts[1].zfill(2)
        year = date_parts[2]

        if date != previous_date:
            content += f"<div class=\"date\">{day}.{month}.{year}</div>"
            max_date = f"{year}-{month}-{day}"

            if not min_date:
                min_date = f"{year}-{month}-{day}"

        content += f'<div class=\"wrapper wrapper-{align} {" ".join(classes)}\" data-date=\"{year}{month}{day}\"><div class=\"message {align}\">'

        if author != "Ich":
            content += f'<span class=\"author">{author}</span><br />'

        content += f"{message_content}"

        previous_date = date
        previous_time = time
        previous_align = align

    content += f"<br /><span class=\"time time-{previous_align}\">{previous_time}</span>"
    content += "</div></div>"

    template = Path("src/index_template.html").read_text()

    html = template.replace("$title", name).replace("$content", content).replace("$all", str(message_count)).replace("$no_media_count", str(no_media_count)).replace("$image_count", str(image_count)).replace("$video_count", str(video_count)).replace("$audio_count", str(audio_count)).replace("$file_count", str(file_count)).replace("$link_count", str(link_count)).replace("$location_count", str(location_count)).replace("$before_date", str(max_date)).replace("$after_date", str(min_date)).replace("$min_date", str(min_date)).replace("$max_date", str(max_date))

    with open(join(path, "index.html"), "w") as f:
        f.write(html)

    shutil.copyfile("src/favicon.ico", join(path, "favicon.ico"))


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
