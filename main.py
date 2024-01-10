import ebooklib
import re
import requests
import subprocess
from ebooklib import epub
from bs4 import BeautifulSoup

QUERY_LIMIT = 10_000
PARAGRAPH_PATTERN = re.compile("Body.*|EX|CE")

class Translator:
    def __init__(self):
        self.IAM_TOKEN = subprocess.getoutput('yc iam create-token')
        self.folder_id = re.match(r"id: (?P<id>\S*)", subprocess.getoutput('yc resource-manager folder get default')).group("id")

    def translatePars(self, pars):
        body = {
            "sourceLanguageCode": "en",
            "targetLanguageCode": "ru",
            "texts": pars,
            "format": "HTML",
            "folderId": self.folder_id,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.IAM_TOKEN}"
        }

        response = requests.post('https://translate.api.cloud.yandex.net/translate/v2/translate',
            json = body,
            headers = headers
        ).json()
        # print(response)
        return [x["text"] for x in response["translations"]]

    def translate(self, page):
        page = page.decode("utf-8")
        soup = BeautifulSoup(page, 'html.parser')
        pars = [[]]
        query_len = 0
        for p in soup.find_all('p', {"class": PARAGRAPH_PATTERN}):
            text = ''.join(map(str, p.contents))
            l = len(text)
            if l + query_len > QUERY_LIMIT:
                pars.append([])
                query_len = 0
            pars[-1].append(text)
            query_len += l
        if not pars[-1]:
            pars.pop()
        new_pars = []
        print()
        for i, ps in enumerate(pars):
            print(f"\rQueries TBD: {i} / {len(pars)}", end='')
            new_ps = self.translatePars(ps)
            new_pars.extend(new_ps)
        for p, text in zip(soup.find_all('p', {"class": PARAGRAPH_PATTERN}), new_pars):
            text = BeautifulSoup(text, "html.parser")
            p.clear()
            p.extend(text.contents)
        return str(soup).encode("utf-8")

def main():
    # ts.preaccelerate_and_speedtest()
    book = epub.read_epub('evo.epub')
    t = Translator()
    for i, item in enumerate(book.get_items()):
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            page = t.translate(item.get_content())
            item.set_content(page)
    epub.write_epub("out.epub", book)

if __name__ == "__main__":
    main()
