import re

from bs4 import BeautifulSoup
from datetime import datetime







def get_patch():
    pass



def get_hotfix_list(html: bytes) -> list[datetime]:
    wiki_soup = BeautifulSoup(html, "lxml")
    #patch_content = wiki_soup.find("div", class_="mw-body-content mw-content-ltr")
    hotfix_title = wiki_soup.find(id="Hotfixes")
    hotfix_content = hotfix_title.parent
    hotfix_list = []
    if hotfix_content:
        offset_list = hotfix_title.find_all_next(id=re.compile("Hotfix"))
        for offset in offset_list:
            hotfix = offset.text
            hotfix = hotfix.replace(" Hotfix", "")
            month, day = hotfix.split()
            day = int(day[:-2])
            hotfix = datetime(datetime.now().year, datetime.strptime(month, "%B").month, day)
            hotfix_list.append(hotfix)
    return hotfix_list