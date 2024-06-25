import argparse

import ebooklib
import re
import requests
import subprocess
from ebooklib import epub
from bs4 import BeautifulSoup

QUERY_LIMIT = 10_000


class Translator:
    def __init__(self):
        status, message = subprocess.getstatusoutput("yc iam create-token")
        if status != 0:
            if message.startswith("ERROR: Failed to get credentials"):
                print(
                    "Please create a profile by Following instructions: https://yandex.cloud/ru/docs/cli/operations/profile/profile-create#interactive-create"
                )
            else:
                print(
                    "Install Yandex Cloud CLI: https://yandex.cloud/ru/docs/cli/operations/install-cli"
                )
            exit(status)
        self.IAM_TOKEN = message
        self.clouds = self.get_clouds()
        self.folder_id = None
        self.set_folder()

    @staticmethod
    def get_clouds() -> set[str]:
        clouds = subprocess.getoutput("yc resource-manager cloud list").split("|")
        clouds = {clouds[6 + i * 5].strip() for i in range((len(clouds) - 6) // 5)}
        return clouds

    def set_folder(self):
        folder_id = subprocess.getoutput("yc resource-manager folder get default")
        self.folder_id = re.match(
            r"id: (?P<id>\S*)",
            folder_id,
        ).group("id")
        print()

    def change_cloud(self, error_message: str):
        bad_cloud = re.fullmatch(
            r"The cloud '(?P<bad_cloud>[^']+)' is inactive", error_message
        ).group("bad_cloud")
        if bad_cloud not in self.clouds:
            print("No active clouds found.")
            exit(1)
        self.clouds.remove(bad_cloud)
        cloud = next(iter(self.clouds))
        subprocess.getoutput(f"yc config set cloud-id {cloud}")
        self.set_folder()

    def translate_paragraphs(self, pars: list[str]):
        body = {
            "sourceLanguageCode": "en",
            "targetLanguageCode": "ru",
            "texts": pars,
            "format": "HTML",
            "folderId": self.folder_id,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.IAM_TOKEN}",
        }

        while True:
            response = requests.post(
                "https://translate.api.cloud.yandex.net/translate/v2/translate",
                json=body,
                headers=headers,
            ).json()
            if response["code"] == 7:
                self.change_cloud(error_message=response["message"])
            else:
                return [x["text"] for x in response["translations"]]

    def translate(self, page):
        page = page.decode("utf-8")
        soup = BeautifulSoup(page, "html.parser")
        pars = [[]]
        query_len = 0
        for p in soup.find_all("p"):
            text = "".join(map(str, p.contents))
            text_len = len(text)
            if text_len + query_len > QUERY_LIMIT:
                pars.append([])
                query_len = 0
            pars[-1].append(text)
            query_len += text_len
        if not pars[-1]:
            pars.pop()
        new_pars = []
        print()
        for i, ps in enumerate(pars):
            print(f"\rQueries TBD: {i} / {len(pars)} ", end="")
            new_ps = self.translate_paragraphs(ps)
            new_pars.extend(new_ps)
        for p, text in zip(soup.find_all("p"), new_pars):
            text = BeautifulSoup(text, "html.parser")
            p.clear()
            p.extend(text.contents)
        return str(soup).encode("utf-8")


def main(epub_path: str, out_path: str):
    t = Translator()
    book = epub.read_epub(name=epub_path, options={"ignore_ncx": True})
    for i, item in enumerate(book.get_items()):
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            page = t.translate(page=item.get_content())
            item.set_content(content=page)
    epub.write_epub(out_path, book)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate an EPUB file.")
    parser.add_argument(
        "epub_path", type=str, help="Path to the EPUB file to be translated."
    )
    parser.add_argument("out_path", type=str, help="Output path.")
    args = parser.parse_args()
    main(args.epub_path, args.out_path)
