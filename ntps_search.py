import requests
from bs4 import BeautifulSoup
import re
import time
from typing import List, Dict, Any, Optional

NTPS_TOP_URL = "https://www.ntps-shop.com/shop/wellstech/"
NTPS_SEARCH_URL = "https://www.ntps-shop.com/search/res/{jan_code}/"
NTPS_PRODUCT_URL = "https://www.ntps-shop.com/product/{product_code}/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_product_urls_from_jan(session: requests.Session, jan_code: str) -> List[str]:
    headers = {"User-Agent": USER_AGENT}
    session.headers.update(headers)
    search_url = NTPS_SEARCH_URL.format(jan_code=jan_code)
    try:
        response = session.get(search_url)
        time.sleep(0.5)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')
    except requests.exceptions.RequestException:
        return []

    links = soup.select('td.tano-center a[href*="/product/"]')
    product_urls: List[str] = []
    if links:
        a_tag = links[0]
        href = a_tag['href']
        m = re.search(r'(/product/\d+/)', href)
        if m:
            relative_url = m.group(1)
            product_urls.append(f"https://www.ntps-shop.com{relative_url}")
    if not product_urls:
        a_tag = soup.select_one('div.tano-item-detail-right a.tano-item-name')
        if a_tag and a_tag.has_attr('href'):
            href = a_tag['href']
            m = re.search(r'(/product/\d+/)', href)
            if m:
                relative_url = m.group(1)
                product_urls.append(f"https://www.ntps-shop.com{relative_url}")

    return product_urls

def get_giftechs_product_info(session: requests.Session, product_code: str) -> Dict[str, Any]:
    headers = {"User-Agent": USER_AGENT}
    session.headers.update(headers)
    product_url = NTPS_PRODUCT_URL.format(product_code=product_code)
    try:
        response = session.get(product_url)
        time.sleep(0.5)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')
    except requests.exceptions.RequestException as e:
        return {"エラー": str(e)}

    product_name_element = soup.select_one('h1#tano-h1 > span, h1.tano-h1-type-01 > span, section.entry-content h1 > span')
    product_name = product_name_element.get_text(strip=True) if product_name_element else ""

    price_element = soup.select_one('span#tano-sale-price > span')
    price = price_element.get_text(strip=True) if price_element else ""
    if price and not price.startswith('￥'):
        price = '￥' + price

    dl = soup.select_one('dl.tano-product-stock-left')
    unit = ""
    if dl:
        dt = dl.find('dt', string="販売単位")
        if dt:
            dd = dt.find_next_sibling('dd')
            if dd:
                unit = dd.get_text(strip=True)

    product_name = re.sub(r'[\u3000\s]+', ' ', product_name).strip()

    return {
        "製品": product_name,
        "NV小売価格": price,
        "個数_シート": unit,
        "申し込み番号": product_code
    }