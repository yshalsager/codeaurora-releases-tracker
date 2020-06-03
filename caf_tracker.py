import json
import re
from datetime import datetime
from os import environ, system
from pathlib import Path
from time import sleep

from bs4 import BeautifulSoup
from requests import get, post

# telegram_chat = "@CAFReleases"
telegram_chat = "-1001238231370"
bottoken = environ['bottoken']
GIT_OAUTH_TOKEN = environ['XFU']

URLS = ['https://wiki.codeaurora.org/xwiki/bin/QAEP/release',
        'https://wiki.codeaurora.org/xwiki/bin/QLBEP/release']


class Scraper:
    def __init__(self, url):
        self.url = url
        self.table = BeautifulSoup(get(self.url).content, 'html.parser').find("table")
        self.name = '_'.join(self.url.split('/')[5:])
        self.head = [th.text.strip() for th in self.table.find_all('th')]
        self.data = {}
        self.to_json()

    def to_json(self):
        for row in self.table.find_all('tr')[1:]:
            cells = row.find_all('td')
            self.data.update({
                cells[1].text.strip(): {
                    title: cell.text.strip() for title, cell in zip(self.head, cells)
                }
            })
        return self.data

    def to_markdown(self):
        markdown = '|'.join(i for i in self.head) + '|\n'
        markdown += '|' + ''.join('---|' for _ in range(len(self.head))) + '\n'
        for item in self.data.keys():
            markdown += '|'.join(i for i in self.data[item].values()) + '|\n'
        return markdown


def diff(old, new):
    return [new.get(item) for item in new.keys() if item not in old.keys()]


def get_security_patch(tag):
    page = BeautifulSoup(get(f"https://source.codeaurora.org/quic/la/platform/build/"
                             f"tree/core/version_defaults.mk?h={tag}").content, "html.parser").get_text()
    info = re.search(r'(?:PLATFORM_SECURITY_PATCH := )(\d{4}-\d{2}-\d{2})', page).group(1)
    return info


def generate_telegram_message(update):
    tag = update.get('Tag / Build ID')
    manifest_url = f"https://source.codeaurora.org/quic/la/platform/manifest/tree/{update.get('Manifest')}?h={tag}"
    message = f"New CAF release detected!: \n" \
              f"Chipset: *{update.get('Chipset')}* \n" \
              f"*Tag:* `{tag}` \n"
    if "Android Version" in update.keys():
        message += f"Android: *{update.get('Android Version')}* \n" \
                   f"Security Patch: *{get_security_patch(tag)}*\n"
    message += f"Manifest: [Here]({manifest_url}) \n" \
               f"Date: {update.get('Date')}"
    return message


def send_telegram_message(telegram_message, chat):
    params = (
        ('chat_id', chat),
        ('text', telegram_message),
        ('parse_mode', "Markdown"),
        ('disable_web_page_preview', "yes")
    )
    telegram_url = "https://api.telegram.org/bot" + bottoken + "/sendMessage"
    response = post(telegram_url, params=params)
    if not response.status_code == 200:
        print(f"Response: {response.reason}")
    sleep(3)


def post_updates(changes, chat):
    for update in changes:
        telegram_message = generate_telegram_message(update)
        send_telegram_message(telegram_message, chat)


def write_markdown(file, content):
    with open(file, 'w') as out:
        out.write(content)


def write_json(file, content):
    with open(file, 'w') as out:
        json.dump(content, out, indent=1)


def read_json(file):
    with open(file, 'r') as json_file:
        return json.load(json_file)


def git_command_push():
    # commit and push
    system(
        f'git add *.md *.json && git -c "user.name=XiaomiFirmwareUpdater" -c '
        f'"user.email=xiaomifirmwareupdater@gmail.com" commit -m '
        f'"[skip ci] sync: {datetime.today().strftime("%d-%m-%Y")}" && '
        f'git push -q https://{GIT_OAUTH_TOKEN}@github.com/androidtrackers/'
        f'codeaurora-releases-tracker.git HEAD:master')


def main():
    for url in URLS:
        scraper = Scraper(url)
        print(f"Working on {scraper.name}")
        file = Path(f"{scraper.name}.json")
        if file.exists():
            file.rename(f'{file}.bak')
        write_json(file, scraper.data)
        write_markdown(f'{file.stem}.md', scraper.to_markdown())
        changes = diff(read_json(f'{file}.bak'), scraper.data)
        if changes:
            post_updates(changes, telegram_chat)
    git_command_push()


if __name__ == '__main__':
    main()
