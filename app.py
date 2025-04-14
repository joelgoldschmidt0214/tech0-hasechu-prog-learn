import streamlit as st
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from supabase import create_client, Client

# --- 初期設定 ---
# .envファイルから環境変数を読み込む
load_dotenv()

# Gemini APIキーの設定
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("エラー: GOOGLE_API_KEYが設定されていません。.envファイルを確認してください。")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# Supabaseクライアントの設定 (今回は直接使用しないが雛形として用意)
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# if SUPABASE_URL and SUPABASE_KEY:
#     try:
#         supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
#         # print("Supabase client created successfully.") # デバッグ用
#     except Exception as e:
#         st.warning(f"Supabaseへの接続に失敗しました: {e}")
#         supabase = None
# else:
#     st.warning("SupabaseのURLまたはキーが.envファイルに設定されていません。")
#     supabase = None

# Geminiモデルの設定 (Flash無料枠)
# Note: 2024/05時点では gemini-1.5-flash-latest が最新のFlashモデルです
# "2.0 Flash" という名前のモデルは存在しないため、最新のFlashを指定します。
try:
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    st.error(f"Geminiモデルの読み込みに失敗しました: {e}")
    st.stop()

# --- Streamlit UI ---
st.set_page_config(page_title="プログラミング学習サポート", layout="wide")
st.title("🚀 プログラミング学習サポート")
st.caption("Gemini API と Supabase を活用した学習アプリ")

# --- サイドバー: ユーザー入力 ---
with st.sidebar:
    st.header("⚙️ 設定")

    # 言語選択
    languages = ["Python", "HTML", "CSS", "JavaScript", "SQL"]
    selected_language = st.selectbox("学習したい言語を選択してください:", languages)

    # 目的選択
    goals = ["困りごとの解決", "プログラミング学習"]
    selected_goal = st.selectbox("目的を選択してください:", goals)

    # 技術レベル選択
    levels = ["初学者", "何となくコードを読める", "自分でコーディングできる", "自力でバグ解消できる"]
    selected_level = st.selectbox("現在の技術レベルを選択してください:", levels)

    # ファイルアップロード (任意)
    uploaded_file = st.file_uploader(
        "関連するファイルをアップロード (任意、.py または .ipynb):",
        type=["py", "ipynb"]
    )

    # 依頼ボタン
    submit_button = st.button("🤖 Geminiに依頼する")

# --- メイン画面: 結果表示 ---

# 依頼ボタンが押された場合の処理
if submit_button:
    # --- 1. プロンプト生成 ---
    st.subheader("📝 Geminiへの依頼内容")

    # アップロードされたファイルの読み込み
    file_content = ""
    if uploaded_file is not None:
        try:
            # ファイルタイプに応じて読み込み方法を変更
            if uploaded_file.name.endswith(".py"):
                file_content = uploaded_file.getvalue().decode("utf-8")
                st.text_area("アップロードされたファイルの内容 (.py)", file_content, height=150)
            elif uploaded_file.name.endswith(".ipynb"):
                # ipynbはJSON形式なので、コードセルを抽出する (簡易的な抽出)
                try:
                    notebook = json.loads(uploaded_file.getvalue().decode("utf-8"))
                    code_cells = [cell['source'] for cell in notebook.get('cells', []) if cell.get('cell_type') == 'code']
                    file_content = "\n\n".join(["".join(cell) for cell in code_cells])
                    st.text_area("アップロードされたファイルの内容 (.ipynb - コードセル)", file_content, height=150)
                except json.JSONDecodeError:
                    st.warning(".ipynbファイルの解析に失敗しました。テキストとして扱います。")
                    file_content = uploaded_file.getvalue().decode("utf-8") # 解析失敗時はテキストとして
                    st.text_area("アップロードされたファイルの内容 (.ipynb - RAW)", file_content, height=150)
                except Exception as e:
                     st.error(f"ファイルの処理中にエラーが発生しました: {e}")
                     file_content = "# ファイル処理エラー" # エラー発生時の代替テキスト

        except UnicodeDecodeError:
            st.error("ファイルのデコードに失敗しました。UTF-8形式のファイルか確認してください。")
            file_content = "# デコードエラー"
        except Exception as e:
            st.error(f"ファイルの読み込み中に予期せぬエラーが発生しました: {e}")
            file_content = "# 読み込みエラー"

    # プロンプトの組み立て
    prompt_parts = [
        f"あなたはプログラミング学習をサポートする親切なAIアシスタントです。",
        f"対象言語: {selected_language}",
        f"ユーザーの目的: {selected_goal}",
        f"ユーザーの技術レベル: {selected_level}",
        "\n以下の情報に基づいて、ユーザーのリクエストに応じた回答を生成してください。"
    ]

    if file_content:
        prompt_parts.append("\n--- ユーザーが提供したコード ---")
        prompt_parts.append(file_content)
        prompt_parts.append("--- コードここまで ---")

    # 目的別の指示を追加
    if selected_goal == "困りごとの解決":
        prompt_parts.append("\n# 指示:")
        prompt_parts.append("- ユーザーが困っているであろう点を推測し、具体的な解決策やコード例を提示してください。")
        prompt_parts.append("- **重要:** 回答の最後に、参考文献として役立つ可能性のあるWebサイトのURLを必ず3つから5つ提示してください。形式は問いませんが、リスト形式などが望ましいです。")
        prompt_parts.append("- 回答はマークダウン形式で、読みやすく記述してください。")
    elif selected_goal == "プログラミング学習":
        prompt_parts.append("\n# 指示:")
        prompt_parts.append(f"- {selected_language}の{selected_level}レベルのユーザー向けに、提供された情報（もしあればコードも含む）に関連する基本的な概念や書き方を解説してください。")
        prompt_parts.append("- **重要:** 解説の最後に、内容の理解度を確認するための簡単なクイズを1つ作成してください。クイズは具体的な質問と、ユーザーが答えを入力できる形式（例: `Q: [質問文]`）で提示してください。正解も内部的に保持しておいてください（ユーザーには見せない）。")
        prompt_parts.append("- 回答はマークダウン形式で、読みやすく記述してください。")

    final_prompt = "\n".join(prompt_parts)

    with st.expander("🤖 Geminiに送信するプロンプト（確認用）"):
        st.text(final_prompt)

    # --- 2. Gemini API呼び出し ---
    st.subheader("💡 Geminiからの回答")
    try:
        with st.spinner("Geminiが回答を生成中です..."):
            response = model.generate_content(final_prompt)
            gemini_response_text = response.text

            # 生成されたテキストをセッション状態に保存 (クイズ用)
            st.session_state.gemini_response = gemini_response_text
            st.session_state.quiz_active = (selected_goal == "プログラミング学習") # 学習目的の場合のみクイズアクティブ
            st.session_state.quiz_evaluated = False # 評価済みフラグをリセット

    except Exception as e:
        st.error(f"Gemini APIの呼び出し中にエラーが発生しました: {e}")
        st.session_state.gemini_response = None
        st.session_state.quiz_active = False

# --- 3. 回答表示とインタラクション ---
if 'gemini_response' in st.session_state and st.session_state.gemini_response:
    st.markdown(st.session_state.gemini_response)

    # --- 4. クイズ機能 (プログラミング学習の場合) ---
    if 'quiz_active' in st.session_state and st.session_state.quiz_active:
        st.markdown("---")
        st.subheader("クイズに挑戦！")

        user_answer = st.text_input("クイズの答えを入力してください:", key="quiz_answer_input")
        submit_quiz_button = st.button("✍️ 採点する", key="submit_quiz")

        if submit_quiz_button and user_answer:
            # Geminiに採点を依頼するプロンプトを作成
            evaluation_prompt = f"""
            あなたはプログラミングクイズの採点者です。
            以下の「元の解説とクイズ」と「ユーザーの解答」を比較し、ユーザーの解答がクイズの意図に合っているか、正解と言えるかを判断してください。
            判断結果と、簡単な解説（なぜ正解/不正解なのか）をユーザーにフィードバックしてください。

            # 元の解説とクイズ:
            {st.session_state.gemini_response}

            # ユーザーの解答:
            {user_answer}

            # フィードバック形式:
            - 採点結果（例：正解です！、惜しい！もう少しです、不正解です、など）
            - 解説（なぜその評価なのか、正解は何だったのか、などを簡潔に）
            """
            try:
                with st.spinner("採点中です..."):
                    evaluation_response = model.generate_content(evaluation_prompt)
                    st.markdown("---")
                    st.subheader("採点結果")
                    st.markdown(evaluation_response.text)
                    st.session_state.quiz_evaluated = True # 評価済みフラグを立てる
                    # st.session_state.quiz_active = False # 採点後はクイズモードを終了する場合

            except Exception as e:
                st.error(f"採点中にエラーが発生しました: {e}")
        elif submit_quiz_button and not user_answer:
            st.warning("クイズの答えを入力してください。")

        # 採点後にテキスト入力欄を非表示にする場合 (オプション)
        # if 'quiz_evaluated' in st.session_state and st.session_state.quiz_evaluated:
        #    pass # 何もしないことで、次のボタンクリックまで入力欄が再度表示されるのを防ぐ
        #    # もしくは、ここで st.empty() などを使って要素を消すことも可能

# セッション状態の初期化（必要に応じて）
# if not submit_button and 'gemini_response' in st.session_state:
#    # ボタンが押されていない状態でページがリロードされた場合などに状態をクリアする
#    # ただし、クイズの回答途中などを保持したい場合はこのクリア処理は不要
#    # del st.session_state.gemini_response
#    # del st.session_state.quiz_active
#    pass