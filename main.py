import streamlit as st
st.set_page_config(layout="wide")
import pandas as pd
import re
import time
import requests
import unicodedata
from typing import List, Dict, Any, Optional
import concurrent.futures

from askul_info import get_askul_product_info
from ntps_search import get_product_urls_from_jan, get_giftechs_product_info

# 定数定義
ASKUL_SUFFIX = " - アスクル"
NOT_FOUND = "Not Found"
UNIT_LABEL = "販売単位"
JAN_LABEL = "JANコード"

# ユーティリティ関数

def extract_price(text: str) -> int:
    """価格文字列から数値部分のみを抽出してintで返す"""
    if not text:
        return 0
    return int(re.sub(r'[^0-9]', '', text))

def normalize_text(text: str) -> str:
    """全角→半角、空白・記号除去"""
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', str(text))
    return re.sub(r'[\s\u3000\(\)（）・,、，]', '', text)

def add_yen(val: Any) -> str:
    if not val:
        return ''
    val = str(val)
    if not val.startswith('￥'):
        return '￥' + val
    return val

def calc_diff(row: pd.Series) -> str:
    nv_price = row.get('NV小売価格', '')
    askul_price = row.get('値段', '')
    unit_sheet = normalize_text(row.get('個数_シート', ''))
    unit_askul = normalize_text(row.get('個数', ''))
    if not nv_price or not askul_price or unit_sheet != unit_askul:
        return ''
    nv_price_num = extract_price(nv_price)
    askul_price_num = extract_price(askul_price)
    try:
        diff = nv_price_num - askul_price_num
        if diff > 0:
            return f'+{diff}'
        else:
            return f'{diff}'
    except Exception:
        return ''

st.title("アスクル&ナビリオン商品情報取得")
st.write("商品番号またはURLを1行ずつ入力してください。商品番号のみでもOKです。")

input_text = st.text_area("商品番号またはURL（1行に1つ）", height=200)

if st.button("情報取得"):
    lines: List[str] = [line.strip() for line in input_text.splitlines() if line.strip()]
    urls: List[str] = []
    for line in lines:
        if line.startswith("http"):
            urls.append(line)
        else:
            urls.append(f"https://www.askul.co.jp/p/{line}/")

    results: List[Dict[str, Any]] = []
    progress = st.progress(0)
    ntps_session = requests.Session()
    # トップページに一度だけアクセスしてセッションを確立
    try:
        NTPS_TOP_URL = "https://www.ntps-shop.com/shop/wellstech/"
        ntps_session.get(NTPS_TOP_URL)
        time.sleep(0.5)
    except Exception as e:
        st.error(f"NTPSトップページ接続失敗: {e}")

    def fetch_info(url):
        try:
            askul_info = get_askul_product_info(url, session=ntps_session)
        except Exception as e:
            st.error(f"アスクル情報取得失敗: {url} ({e})")
            askul_info = {"アスクル品名": "", "個数": "", "JANコード": "", "値段": "", "URL": url}
        jan_code = askul_info.get("JANコード", "")

        giftechs_info = {
            "同一商品判定": "該当商品なし",
            "製品": "",
            "個数_シート": "",
            "申し込み番号": "",
            "NV小売価格": "",
            "URL_シート": ""
        }

        if jan_code:
            try:
                product_urls = get_product_urls_from_jan(ntps_session, jan_code)
            except Exception as e:
                st.error(f"NTPS商品URL取得失敗: {jan_code} ({e})")
                product_urls = []
            if product_urls:
                giftechs_url = product_urls[0]
                m = re.search(r'/product/(\d+)/', giftechs_url)
                if m:
                    product_code = m.group(1)
                    try:
                        giftechs_data = get_giftechs_product_info(ntps_session, product_code)
                    except Exception as e:
                        st.error(f"Giftechs情報取得失敗: {product_code} ({e})")
                        giftechs_data = {}
                    if giftechs_data:
                        giftechs_info = {
                            "同一商品判定": "同類商品",
                            "製品": giftechs_data.get("製品", ""),
                            "個数_シート": giftechs_data.get("個数_シート", ""),
                            "申し込み番号": giftechs_data.get("申し込み番号", ""),
                            "NV小売価格": giftechs_data.get("NV小売価格", ""),
                            "URL_シート": giftechs_url
                        }
                    else:
                        giftechs_info["同一商品判定"] = "情報取得失敗"
                else:
                    giftechs_info["同一商品判定"] = "URLパターン不一致"
            else:
                giftechs_info["同一商品判定"] = "類似商品"
                giftechs_info["URL_シート"] = f"https://www.ntps-shop.com/search/res/{jan_code}/"
        else:
            giftechs_info["同一商品判定"] = ""
            giftechs_info["URL_シート"] = ""

        # 出力用辞書をカラム名に合わせて作成
        result_row = {
            "as製品": askul_info.get("アスクル品名", ""),
            "as員数": askul_info.get("個数", ""),
            "JANコード": askul_info.get("JANコード", ""),
            "asURL": askul_info.get("URL", ""),
            "as価格": askul_info.get("値段", ""),
            "as数量": "",
            "購入額": "",
            "種類": giftechs_info.get("同一商品判定", ""),
            "nv製品": giftechs_info.get("製品", ""),
            "nv員数": giftechs_info.get("個数_シート", ""),
            "nv申し込み番号": giftechs_info.get("申し込み番号", ""),
            "NV小売価格": giftechs_info.get("NV小売価格", ""),
            "nv数量": "",
            "購入額.1": "",
            "nvURL": giftechs_info.get("URL_シート", ""),
            "備考": "",
            # ナビリオン値差は後で計算
        }
        time.sleep(0.5)  # サーバー配慮
        return result_row

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_to_idx = {executor.submit(fetch_info, url): i for i, url in enumerate(urls)}
        for count, future in enumerate(concurrent.futures.as_completed(future_to_idx)):
            i = future_to_idx[future]
            try:
                result = future.result()
            except Exception as exc:
                st.error(f"情報取得失敗: {urls[i]} ({exc})")
                result = {"アスクル品名": "", "個数": "", "JANコード": "", "値段": "", "URL": urls[i]}
            results.append(result)
            progress.progress((count + 1) / len(urls), text=f"処理中: {count + 1} / {len(urls)}")

    progress.empty()
    if not results:
        st.warning("データが取得できませんでした。入力内容をご確認ください。")
    else:
        df = pd.DataFrame(results)
        # 差額列を計算
        df['NV小売価格'] = df['NV小売価格'].apply(add_yen)
        df['as価格'] = df['as価格'].apply(add_yen)
        # ナビリオン値差を計算
        def calc_navi_diff(row):
            nv_price = row.get('NV小売価格', '')
            askul_price = row.get('as価格', '')
            unit_sheet = normalize_text(row.get('nv員数', ''))
            unit_askul = normalize_text(row.get('as員数', ''))
            if not nv_price or not askul_price or unit_sheet != unit_askul:
                return ''
            nv_price_num = extract_price(nv_price)
            askul_price_num = extract_price(askul_price)
            try:
                diff = nv_price_num - askul_price_num
                if diff > 0:
                    return f'+{diff}'
                else:
                    return f'{diff}'
            except Exception:
                return ''
        df['ナビリオン値差'] = df.apply(calc_navi_diff, axis=1)
        # 17個目の見出し（空白）を追加
        def mark_circle(row):
            try:
                val = row.get('ナビリオン値差', '')
                if val and isinstance(val, str) and val.strip().startswith('-'):
                    return '〇'
                return ''
            except Exception:
                return ''
        df[''] = df.apply(mark_circle, axis=1)
        # カラム順序を明示
        columns = [
            "as製品", "as員数", "JANコード", "asURL", "as価格", "as数量", "購入額", "種類",
            "nv製品", "nv員数", "nv申し込み番号", "NV小売価格", "nv数量", "購入額.1", "nvURL", "備考", "ナビリオン値差", ""
        ]
        df = df.reindex(columns=columns)
        st.dataframe(df)
        # ダウンロードボタン追加
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="CSVダウンロード",
            data=csv,
            file_name="askul_gifshop_result.csv",
            mime="text/csv"
        )