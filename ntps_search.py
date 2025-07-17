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

    # 複数の個数情報を取得
    multiple_units = []
    # 表の構造に対応：th要素で「入数」「販売単位」などを探し、その次のtd要素から取得
    table_rows = soup.find_all('tr')
    for row in table_rows:
        th = row.find('th')
        if th and any(keyword in th.get_text(strip=True) for keyword in ['入数', '販売単位', '個数']):
            td = row.find('td', class_='tano-d-sh-variation-list')
            if td:
                labels = td.find_all('label')
                for label in labels:
                    unit_text = label.get_text(strip=True)
                    if unit_text:
                        multiple_units.append(unit_text)
                break  # 最初に見つかったものだけ処理
    
    # 個数を数値で比較して並べ替え（少ない方から多い方へ）
    def extract_number(unit_text):
        # 全角数字を半角数字に変換
        full_to_half = str.maketrans('０１２３４５６７８９', '0123456789')
        unit_text_converted = unit_text.translate(full_to_half)
        
        print(f"  変換前: '{unit_text}'")
        print(f"  変換後: '{unit_text_converted}'")
        
        # 括弧内の数字を優先的に取得
        bracket_match = re.search(r'[（(](\d+)[）)]', unit_text_converted)
        print(f"  括弧内正規表現テスト: '{unit_text_converted}'")
        if bracket_match:
            result = int(bracket_match.group(1))
            print(f"  括弧内マッチ: {result}")
            return result
        else:
            print(f"  括弧内マッチ失敗")
            # 括弧内の数字を取得（括弧の後に文字が来てもOK）
            bracket_match2 = re.search(r'[（(](\d+)', unit_text_converted)
            if bracket_match2:
                result = int(bracket_match2.group(1))
                print(f"  括弧内マッチ2: {result}")
                return result
            else:
                print(f"  括弧内マッチ2失敗")
        # 括弧がない場合は最初の数字を取得
        number_match = re.search(r'(\d+)', unit_text_converted)
        if number_match:
            result = int(number_match.group(1))
            print(f"  最初の数字: {result}")
            return result
        print(f"  数字なし: 0")
        return 0
    
    # デバッグ用：抽出された数値を確認
    if len(multiple_units) > 1:
        print(f"ソート前: {multiple_units}")
        for unit in multiple_units:
            print(f"  {unit} -> {extract_number(unit)}")
        multiple_units.sort(key=extract_number)
        print(f"ソート後: {multiple_units}")
    
    # 従来の個数情報（販売単位）も取得
    dl = soup.select_one('dl.tano-product-stock-left')
    unit = ""
    if dl:
        dt = dl.find('dt', string="販売単位")
        if dt:
            dd = dt.find_next_sibling('dd')
            if dd:
                unit = dd.get_text(strip=True)

    # 複数の個数情報がある場合は、最初の1つを従来の個数として使用
    if multiple_units and not unit:
        unit = multiple_units[0]
    
    # 複数の個数情報をまとめる
    multiple_units_text = ""
    if len(multiple_units) > 1:
        multiple_units_text = ", ".join(multiple_units)

    product_name = re.sub(r'[\u3000\s]+', ' ', product_name).strip()

    return {
        "製品": product_name,
        "NV小売価格": price,
        "個数_シート": unit,
        "個数_複数": multiple_units_text,
        "申し込み番号": product_code
    }