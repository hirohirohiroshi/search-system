# -*- coding: utf-8 -*-
import os
import json
import streamlit as st
import gdown
import shutil  # フォルダ削除のためにshutilライブラリをインポート
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, STORED
from whoosh.qparser import MultifieldParser, AndGroup
from whoosh.analysis import NgramAnalyzer

# --- ▼ 設定項目 ▼ ---
GOOGLE_DRIVE_FILE_ID = "1FGd89dvLBrG8ZZuwlmYbVx-ySX8snAmP"
JSON_FILE_PATH = "downloaded_database.json"
INDEX_DIR = "search_index"
# --- ▲ 設定項目 ▲ ---


@st.cache_resource
def get_search_index():
    """
    検索インデックスを準備する関数。
    インデックスがなければ、Google Driveからデータをダウンロードして新規作成します。
    """
    ja_analyzer = NgramAnalyzer(2)
    schema = Schema(
        sheet_name=TEXT(stored=True, analyzer=ja_analyzer),
        all_content=TEXT(analyzer=ja_analyzer),
        original_data=STORED
    )

    if not os.path.exists(INDEX_DIR):
        print("インデックスが見つからないため、新規作成を開始します。")
        try:
            print("Google Driveからデータをダウンロードしています...")
            gdown.download(id=GOOGLE_DRIVE_FILE_ID, output=JSON_FILE_PATH, quiet=False)
            print("ダウンロードが完了しました。")

            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                all_sheets_data = json.load(f)

        except Exception as e:
            st.error(f"データダウンロードまたはファイル読み込みエラー: {e}")
            return None
        
        os.mkdir(INDEX_DIR)
        ix = create_in(INDEX_DIR, schema)
        writer = ix.writer()
        
        print("インデックスを作成しています...")
        with st.spinner("データの索引を作成中..."): # スピナーUIを追加
            for sheet_name, rows in all_sheets_data.items():
                for row_data in rows:
                    content_list = [str(value) for value in row_data.values()]
                    combined_content = " ".join(content_list)
                    writer.add_document(
                        sheet_name=sheet_name,
                        all_content=combined_content,
                        original_data=row_data
                    )
            writer.commit()
        print("インデックスの作成が完了しました。")

    else:
        print("既存のインデックスを読み込みます。")
        ix = open_dir(INDEX_DIR)
        
    return ix


def search(index, query_string):
    """キーワードでインデックスを検索する関数"""
    query_parser = MultifieldParser(
        ["sheet_name", "all_content"],
        schema=index.schema,
        group=AndGroup
    )
    query = query_parser.parse(query_string)
    with index.searcher() as searcher:
        results = [hit.fields() for hit in searcher.search(query, limit=50)]
    return results


# --- ▼ Streamlitアプリのメインの見た目と操作部分 ▼ ---
st.title("📂 高速検索システム　はやお")

# --- ▼ 変更点：リフレッシュボタンの追加 ▼ ---
st.write("---")
if st.button("🔄 データを強制リフレッシュ"):
    # search_indexフォルダが存在すれば削除
    if os.path.exists(INDEX_DIR):
        shutil.rmtree(INDEX_DIR)
    # Streamlitのキャッシュをクリア
    st.cache_resource.clear()
    st.success("データのキャッシュをクリアしました。ページを自動でリロードします。")
    # ページをリロードして、データの再取得とインデックス作成を強制する
    st.rerun()

st.write("---")

search_index = get_search_index()

search_keyword = st.text_input("検索キーワードを入力してください", placeholder="例: 破産 賃借")

if search_keyword and search_index:
    normalized_keyword = search_keyword.replace('　', ' ').strip()
    keywords_to_highlight = [k for k in set(normalized_keyword.split()) if k]
    
    search_results = search(search_index, normalized_keyword)
    
    st.write("---")
    st.subheader(f"検索結果: {len(search_results)} 件")

    if not search_results:
        st.warning("該当するデータは見つかりませんでした。")
    else:
        for result in search_results:
            with st.container(border=True):
                original_data = result['original_data']
                st.markdown(f"**シート名:** `{result['sheet_name']}`")
                
                for key, value in original_data.items():
                    display_value = str(value)
                    for keyword in keywords_to_highlight:
                        display_value = display_value.replace(keyword, f"<mark>{keyword}</mark>")
                    
                    st.markdown(f"**{key}:** {display_value}", unsafe_allow_html=True)