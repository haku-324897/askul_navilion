import requests
from bs4 import BeautifulSoup
import re
import time
from typing import Dict, Any, Optional

ASKUL_SUFFIX = " - アスクル"
NOT_FOUND = "Not Found"
UNIT_LABEL = "販売単位"
JAN_LABEL = "JANコード"


def get_askul_product_info(url: str, session: Optional[requests.Session] = None) -> Dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0"}
    session = session or requests.Session()
    try:
        res = session.get(url, headers=headers, timeout=10)
        time.sleep(0.5)  # サーバー配慮のためのディレイ
        if res.status_code != 200:
            raise Exception(f"HTTP {res.status_code}")
    except Exception as e:
        return {
            "アスクル品名": "",
            "個数": "",
            "JANコード": "",
            "値段": "",
            "URL": url,
            "エラー": str(e)
        }

    soup = BeautifulSoup(res.text, "lxml")

    # 商品名
    name = ""
    if soup.title and soup.title.string:
        name = soup.title.string.strip()
        if name == NOT_FOUND:
            name = ""
        elif name.endswith(ASKUL_SUFFIX):
            name = name[:-len(ASKUL_SUFFIX)]

    # 値段
    price = ""
    price_tag = soup.select_one("span.item-price-value, span.item-price-taxin")
    if price_tag:
        price = price_tag.get_text(strip=True)
    else:
        price_candidates = soup.find_all(string=re.compile(r"￥[0-9,]+"))
        for candidate in price_candidates:
            text = candidate.strip()
            if re.match(r"^￥[0-9,]+", text):
                price = text
                break
    if price and not price.startswith('￥'):
        price = '￥' + price

    # 販売単位
    quantity = ""
    unit_tag = soup.find(string=re.compile(f"{UNIT_LABEL}[:：]"))
    if unit_tag:
        quantity = re.sub(f"{UNIT_LABEL}[:：]", "", unit_tag).strip()
    else:
        # テーブルやリスト内にある場合も考慮
        unit_label_tag = soup.find(lambda tag: tag.name in ['th', 'dt'] and UNIT_LABEL in tag.get_text())
        if unit_label_tag:
            next_tag = unit_label_tag.find_next_sibling(['td', 'dd'])
            if next_tag:
                quantity = next_tag.get_text(strip=True)

    # JANコード
    jan_code = ""
    jan_tag = soup.find(string=re.compile(f"{JAN_LABEL}[:：]?\s*[0-9]+"))
    if jan_tag:
        m = re.search(r"JANコード[:：]?\s*([0-9]+)", jan_tag)
        if m:
            jan_code = m.group(1)
        else:
            jan_code = jan_tag.strip().replace("JANコード：", "").replace("JANコード:", "").strip()
    else:
        # テーブルやリスト内にある場合も考慮
        jan_label_tag = soup.find(lambda tag: tag.name in ['th', 'dt'] and JAN_LABEL in tag.get_text())
        if jan_label_tag:
            next_tag = jan_label_tag.find_next_sibling(['td', 'dd'])
            if next_tag:
                jan_code = re.sub(r'[^0-9]', '', next_tag.get_text())

    return {
        "アスクル品名": name,
        "個数": quantity,
        "JANコード": jan_code,
        "値段": price,
        "URL": url,
    }
