import argparse
import re
from os import listdir
from os.path import isdir, isfile, join, basename
from pathlib import Path

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
    image_count = 0
    video_count = 0
    audio_count = 0
    file_count = 0
    link_count = 0
    location_count = 0

    message = message.replace("<", "&lt;").replace(">", "&gt;")

    files = re.findall(FILE_REGEX, message)

    if files:
        for match in files:
            if not isfile(join(path, match[1])):
                message = message.replace(match[0], f"<a href=\"{match[1]}\">MISSING FILE</a>")
            elif match[2] in ["jpg", "jpeg", "png"]:
                image_count += 1
                message = message.replace(match[0], f"<br/><a href=\"{match[1]}\"><img src=\"{match[1]}\" width=300 /></a><br />")
            elif match[2] in ["mp4"]:
                video_count += 1
                message = message.replace(match[0], f"<br /><a href=\"{match[1]}\"><video controls><source src=\"{match[1]}\" /></video></a><br />")
            elif match[2] in ["aac"]:
                audio_count += 1
                message = message.replace(match[0], f"<br /><a href=\"{match[1]}\"><audio controls src=\"{match[1]}\"></audio></a><br />")
            else:
                file_count += 1
                message = message.replace(match[0], f"<a href=\"{match[1]}\">{match[1]}</a>")

    urls = list(set(re.findall(URL_REGEX, message)))

    if urls:
        link_count += len(urls)

        for match in urls:
            message = message.replace(match, f"<a href=\"{match}\">{match}</a>")

    geos = re.findall(GEO_REGEX, message)

    if geos:
        location_count += len(geos)

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
        return message_parts.group(1), message_parts.group(2), message_parts.group(3), message_parts.group(4), image_count, video_count, audio_count, file_count, link_count, location_count

    return None, None, None, message, image_count, video_count, audio_count, file_count, link_count, location_count


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

    content = ""
    previous_date = None
    previous_time = None
    previous_align = None

    for i in range(len(messages)):
        date, time, author, message_content, message_image_count, message_video_count, message_audio_count, message_file_count, message_link_count, message_location_count = parse_message(path, messages[i])

        if not date:
            # this message is just a new line of the previous message and was already processed
            continue

        classes = []

        j = i+1
        while j < len(messages):
            # look ahead for messages belonging to this one but seperated by line breaks
            next_date, _, _, next_message_content, next_image_count, next_video_count, next_audio_count, next_file_count, next_link_count, next_location_count = parse_message(path, messages[j])

            if next_date:
                # new message found, no further look-ahead needed
                break

            message_content += f"<br />{next_message_content}"

            if next_image_count:
                classes.append(CLASS_IMAGE)
                image_count += next_image_count

            if next_video_count:
                classes.append(CLASS_VIDEO)
                video_count += next_video_count

            if next_audio_count:
                classes.append(CLASS_AUDIO)
                audio_count += next_audio_count

            if next_file_count:
                classes.append(CLASS_FILE)
                file_count += next_file_count

            if next_link_count:
                classes.append(CLASS_LINK)
                link_count += next_link_count

            if next_location_count:
                classes.append(CLASS_LOCATION)
                location_count += next_location_count

            j += 1

        message_count += 1

        if message_image_count:
            classes.append(CLASS_IMAGE)
            image_count += message_image_count

        if message_video_count:
            classes.append(CLASS_VIDEO)
            video_count += message_video_count

        if message_audio_count:
            classes.append(CLASS_AUDIO)
            audio_count += message_audio_count

        if message_file_count:
            classes.append(CLASS_FILE)
            file_count += message_file_count

        if message_link_count:
            classes.append(CLASS_FILE)
            link_count += message_link_count

        if message_location_count:
            classes.append(CLASS_LOCATION)
            location_count += message_location_count

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

        if date != previous_date:
            content += f"<div class=\"date\">{date}</div>"

        content += f'<div class=\"wrapper wrapper-{align} {" ".join(classes)}\"><div class=\"message {align}\">'

        if author != "Ich":
            content += f'<span class=\"author">{author}</span><br />'

        content += f"{message_content}"

        previous_date = date
        previous_time = time
        previous_align = align

    content += "</div></div>"

    template = Path("src/index_template.html").read_text()

    html = template.replace("$title", name).replace("$content", content).replace("$all", str(message_count)).replace("$no_media_count", str(no_media_count)).replace("$image_count", str(image_count)).replace("$video_count", str(video_count)).replace("$audio_count", str(audio_count)).replace("$file_count", str(file_count)).replace("$link_count", str(link_count)).replace("$location_count", str(location_count))

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
