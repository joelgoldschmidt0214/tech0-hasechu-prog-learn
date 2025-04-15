import streamlit as st
import google.generativeai as genai
import os
import json
import re
from dotenv import load_dotenv
# from supabase import create_client, Client # Supabase未使用のためコメントアウト継続

# --- 初期設定 ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("エラー: GOOGLE_API_KEYが設定されていません。.envファイルを確認してください。")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)

try:
    # モデル名を一般的な最新Flashモデルに戻す
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    st.error(f"Geminiモデルの読み込みに失敗しました: {e}")
    st.stop()

# --- Streamlit UI ---
st.set_page_config(page_title="プログラミング学習サポート", layout="wide")
st.title("プログラミング学習サポート")
st.caption("Gemini API を活用した学習アプリ") # Supabaseは未使用なので削除

# --- サイドバー: ユーザー入力 (フォーム化) ---
# クリアボタンはフォームの外に配置
if st.sidebar.button("結果をクリア"):
    keys_to_delete = [
        'gemini_response', 'explanation', 'quiz_question', 'quiz_active',
        'quiz_evaluated', 'user_name', 'selected_language', 'selected_goal',
        'selected_level', 'problem_details', 'uploaded_file_info' # 必要に応じてクリアする項目を追加
        ]
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    # st.rerun() を使うとフォーム送信直後の状態に戻る可能性があるため、
    # session_stateをクリアした後はページリロードを促すか、
    # 各ウィジェットのデフォルト値をsession_stateから取得しないようにする
    st.rerun()

with st.sidebar:
    with st.form(key="settings_form"):
        st.header("設定")

        # --- ユーザー名入力 ---
        st.text_input("お名前 (任意):", key="user_name", value=st.session_state.get("user_name", ""))

        # 言語選択
        languages = ["Python", "HTML", "CSS", "JavaScript", "SQL"]
        st.selectbox("学習したい言語を選択してください:", languages, key="selected_language", index=languages.index(st.session_state.get("selected_language", "Python")))

        # 目的選択
        goals = ["困りごとの解決", "プログラミング学習"]
        st.selectbox("目的を選択してください:", goals, key="selected_goal", index=goals.index(st.session_state.get("selected_goal", "プログラミング学習")))

        # 技術レベル選択
        levels = ["初学者", "何となくコードを読める", "自分でコーディングできる", "自力でバグ解消できる"]
        st.selectbox("現在の技術レベルを選択してください:", levels, key="selected_level", index=levels.index(st.session_state.get("selected_level", "初学者")))

        # --- 困りごと入力 (Ctrl+Enterで送信期待) ---
        st.text_area("困りごとや質問の詳細を具体的に記入してください:", height=150, key="problem_details", value=st.session_state.get("problem_details", ""))

        # ファイルアップロード（許可タイプは前回同様）
        allowed_text_extensions = [
            "py", "html", "css", "js", "sql", "txt", "md", "log",
            "json", "yaml", "toml", "ini", "xml", "csv",
            "xhtml", "htm", "mjs", "cjs", "ipynb"
            ]
        st.file_uploader(
            f"関連するテキストファイルをアップロード (任意):",
            type=allowed_text_extensions,
            key="uploaded_file_info" # file_uploader自体もキーで状態管理
        )

        # --- 実行ボタン (フォーム送信) ---
        submit_button = st.form_submit_button("実行する")

# --- メイン画面: 結果表示 ---

# クイズ抽出関数 (変更なし)
def extract_quiz(response_text):
    # ... (前回のコードと同じ) ...
    lines = response_text.strip().split('\n')
    quiz_question = None
    explanation_lines = []
    quiz_pattern = re.compile(r"^(Q:|質問:|問題:|クイズ：)\s*", re.IGNORECASE)
    found_quiz = False
    temp_explanation = []
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if quiz_pattern.match(stripped_line):
             quiz_question = line
             found_quiz = True
             explanation_lines.extend(temp_explanation)
             temp_explanation = []
        elif found_quiz:
             pass
        else:
             temp_explanation.append(line)
    if not found_quiz:
        explanation_lines.extend(temp_explanation)
    explanation_text = "\n".join(explanation_lines).strip()
    if found_quiz and not explanation_text:
         q_index = -1
         for i, line in enumerate(lines):
              if quiz_pattern.match(line.strip()):
                   q_index = i
                   break
         if q_index > 0:
             explanation_text = "\n".join(lines[:q_index]).strip()
         else:
             explanation_text = ""
    if not quiz_question:
        explanation_text = response_text.strip()
    return explanation_text, quiz_question


# --- フォーム送信時 (実行ボタン押下時) の処理 ---
if submit_button:
    # --- ファイル処理ロジック (変更なし) ---
    file_content = None
    file_info = ""
    encoding_used = None
    process_file = True
    # サイドバーのフォームから値を取得
    uploaded_file = st.session_state.get("uploaded_file_info") # キーを使って取得

    if uploaded_file is not None:
        file_name = uploaded_file.name
        file_size = uploaded_file.size
        st.write(f"アップロードされたファイル: `{file_name}` ({file_size / 1024:.1f} KB)")
        file_info = f"ファイル名: {file_name}"

        try:
            if file_name.endswith(".ipynb"):
                # ... (ipynb処理、変更なし) ...
                file_info += " (.ipynb)"
                try:
                    uploaded_file.seek(0)
                    notebook_content = uploaded_file.getvalue().decode("utf-8")
                    notebook = json.loads(notebook_content)
                    code_cells = [cell['source'] for cell in notebook.get('cells', []) if cell.get('cell_type') == 'code']
                    file_content = "\n\n".join(["".join(cell) for cell in code_cells])
                    encoding_used = "utf-8 (ipynb code cells)"
                    st.text_area("抽出されたコードセル (.ipynb)", file_content, height=150, key="disp_ipynb_code") # 表示用ウィジェットにも固有キー推奨
                except (json.JSONDecodeError, UnicodeDecodeError) as e_ipynb_parse:
                    st.warning(f".ipynbファイルの解析またはUTF-8デコードに失敗しました ({e_ipynb_parse})。ファイル全体をテキストとして扱います。")
                    try:
                        uploaded_file.seek(0)
                        try:
                           file_content = uploaded_file.getvalue().decode("utf-8")
                           encoding_used = "utf-8 (ipynb raw)"
                        except UnicodeDecodeError:
                           uploaded_file.seek(0)
                           file_content = uploaded_file.getvalue().decode("shift-jis")
                           encoding_used = "shift-jis (ipynb raw)"
                           st.info(".ipynbファイルをShift-JISとして読み込みました(RAW)。")
                        st.text_area("ファイルの内容 (.ipynb - RAW)", file_content, height=150, key="disp_ipynb_raw")
                    except UnicodeDecodeError:
                         st.error(f".ipynbファイル(RAW)はUTF-8またはShift-JISとしてデコードできませんでした。")
                         file_info += " (RAWデコード失敗)"
                         file_content = None; process_file = False
                    except Exception as e_ipynb_raw:
                         st.error(f".ipynbファイル(RAW)の処理中にエラー: {e_ipynb_raw}")
                         file_info += " (RAW処理エラー)"
                         file_content = None; process_file = False
                except Exception as e_ipynb_other:
                    st.error(f".ipynb ファイルの処理中に予期せぬエラーが発生しました: {e_ipynb_other}")
                    file_info += " (処理エラー)"
                    file_content = None; process_file = False
            else:
                # ... (その他のテキストファイル処理、変更なし) ...
                uploaded_file.seek(0)
                file_bytes = uploaded_file.getvalue()
                try:
                    file_content = file_bytes.decode("utf-8")
                    encoding_used = "utf-8"
                except UnicodeDecodeError:
                    try:
                        file_content = file_bytes.decode("shift-jis")
                        encoding_used = "shift-jis"
                        st.info(f"ファイル '{file_name}' はShift-JISとして読み込まれました。")
                    except UnicodeDecodeError:
                        st.error(f"ファイル '{file_name}' はUTF-8またはShift-JISとしてデコードできませんでした。")
                        file_info += " (テキスト変換不可)"
                        file_content = None; process_file = False
                    except Exception as e_sjis:
                         st.error(f"Shift-JISデコード中に予期せぬエラー: {e_sjis}")
                         file_info += " (Shift-JISデコードエラー)"
                         file_content = None; process_file = False
        except Exception as e_outer:
             st.error(f"ファイル処理中に予期せぬエラーが発生しました: {e_outer}")
             file_info += " (不明なエラー)"
             file_content = None; process_file = False

        if process_file and file_content is not None:
            # ... (文字数制限チェック、変更なし) ...
            max_chars = 500000
            if len(file_content) > max_chars:
                st.error(f"ファイル '{file_name}' の文字数 ({len(file_content)}文字) が制限 ({max_chars}文字) を超えています。")
                file_info += f" (文字数超過)"
                file_content = None; process_file = False
            else:
                 file_info += f" ({len(file_content)}文字, encoding: {encoding_used})"

    # --- プロンプト生成とGemini呼び出し ---
    st.subheader("Geminiへの依頼内容")

    # サイドバーのフォームから入力値を取得
    user_name = st.session_state.get("user_name", "").strip()
    selected_language = st.session_state.get("selected_language")
    selected_goal = st.session_state.get("selected_goal")
    selected_level = st.session_state.get("selected_level")
    problem_details = st.session_state.get("problem_details", "").strip()

    # プロンプトの組み立て (順序変更、ユーザー名追加)
    prompt_parts = []

    # ユーザー名に応じた挨拶
    if user_name:
        prompt_parts.append(f"{user_name}さん、こんにちは！プログラミング学習AIです。")
    else:
        prompt_parts.append("プログラミング学習AIです。")

    prompt_parts.append(f"あなたの現在の状況と言語、目的に合わせてサポートします。")
    prompt_parts.append(f"対象言語: {selected_language}")
    prompt_parts.append(f"目的: {selected_goal}")
    prompt_parts.append(f"技術レベル: {selected_level}")

    if problem_details:
        prompt_parts.append(f"\n# {user_name}さんからの質問や困りごと:\n{problem_details}")
    else:
        # デフォルト指示 (変更なし)
        if selected_goal == "困りごとの解決":
             prompt_parts.append(f"\n# {user_name}さんからの具体的な質問:")
             prompt_parts.append("具体的な困りごとが入力されていません。アップロードされたファイル情報（もしあれば）や選択された言語、レベルから想定される一般的な問題や、その言語の基本的な使い方について解説してください。")
        elif selected_goal == "プログラミング学習":
             prompt_parts.append(f"\n# {user_name}さんからの具体的な質問:")
             prompt_parts.append(f"具体的な質問が入力されていません。{selected_language}の基本的な概念や、{selected_level}レベルのあなたが学び始めると良いトピックについて解説してください。")

    # --- 目的別の指示 (ファイル情報より前に移動) ---
    prompt_parts.append("\n# 回答生成のための指示:")
    if selected_goal == "困りごとの解決":
        prompt_parts.append("- ユーザーの質問や困りごと、提供されたファイル情報（もしあれば）に基づいて、具体的な解決策やコード例を提示してください。")
        prompt_parts.append("- **重要:** 回答の最後に、参考文献として役立つ可能性のあるWebサイトのURLを必ず3つから5つ提示してください。リスト形式などが望ましいです。")
        prompt_parts.append("- 回答はマークダウン形式で、{user_name}さんが読みやすいように記述してください。".format(user_name=user_name if user_name else "ユーザー"))
    elif selected_goal == "プログラミング学習":
        prompt_parts.append(f"- {selected_language}の{selected_level}レベルの{user_name}さん向けに、質問やファイル情報（もしあれば）に関連する基本的な概念や書き方を解説してください。".format(user_name=user_name if user_name else "ユーザー"))
        prompt_parts.append("- **重要:** 解説の最後に、内容の理解度を確認するための簡単なクイズを1つ作成してください。")
        prompt_parts.append("- **クイズの形式:** 必ず応答の最後に、改行を挟んでから `Q: [質問文]` の形式で質問文のみを提示してください。")
        prompt_parts.append("- **絶対に、絶対に、絶対にクイズの解答や正解を示唆するヒントをユーザー向けの出力に含めないでください。**")
        prompt_parts.append("- 回答はマークダウン形式で、{user_name}さんが読みやすいように記述してください。".format(user_name=user_name if user_name else "ユーザー"))

    prompt_parts.append("\n以下の追加情報も考慮してください。")

    # ファイル情報と内容をプロンプトに追加 (指示の後)
    if file_info:
        prompt_parts.append(f"\n--- {user_name}さんが提供したファイル情報 ---")
        prompt_parts.append(file_info)
        if process_file and file_content is not None:
             prompt_parts.append("\n--- ファイル内容 ---")
             prompt_parts.append(file_content)
             prompt_parts.append("--- ファイル内容ここまで ---")
        prompt_parts.append("--- ファイル情報ここまで ---")


    final_prompt = "\n".join(prompt_parts)

    with st.expander("Geminiに送信するプロンプト（確認用）"):
        st.text(final_prompt)

    # --- 2. Gemini API呼び出し ---
    st.subheader("Geminiからの回答")
    try:
        with st.spinner("Geminiが回答を生成中です..."):
            response = model.generate_content(final_prompt)
            gemini_response_text = response.text
            explanation_text, quiz_question = extract_quiz(gemini_response_text)
            # 結果をセッション状態に保存
            st.session_state.gemini_response = gemini_response_text
            st.session_state.explanation = explanation_text
            st.session_state.quiz_question = quiz_question
            st.session_state.quiz_active = (selected_goal == "プログラミング学習" and quiz_question is not None)
            st.session_state.quiz_evaluated = False
    except Exception as e:
        st.error(f"Gemini APIの呼び出し中にエラーが発生しました: {e}")
        st.session_state.gemini_response = None
        st.session_state.explanation = None
        st.session_state.quiz_question = None
        st.session_state.quiz_active = False


# --- 3. 回答表示とインタラクション ---
# 解説表示
if 'explanation' in st.session_state and st.session_state.explanation:
    st.markdown(st.session_state.explanation)

# --- クイズ表示・採点 (フォーム化) ---
if 'quiz_active' in st.session_state and st.session_state.quiz_active:
    if 'quiz_question' in st.session_state and st.session_state.quiz_question:
        st.markdown("---")
        st.subheader("クイズに挑戦！")
        st.markdown(st.session_state.quiz_question)

        # --- クイズ回答フォーム ---
        with st.form(key="quiz_form"):
            user_answer = st.text_input("クイズの答えを入力してください:", key="quiz_answer_input")
            submit_quiz_button = st.form_submit_button("採点する")

            if submit_quiz_button: # フォーム送信時に処理
                if user_answer:
                    # 採点プロンプト生成 (元の応答全体を使用)
                    evaluation_prompt = f"""
                    あなたはプログラミングクイズの採点者です。
                    以下の「元の解説とクイズ」と「ユーザー ({st.session_state.get('user_name', '不明')}) の解答」を比較し、ユーザーの解答がクイズの意図に合っているか、正解と言えるかを判断してください。
                    判断結果と、簡単な解説（なぜ正解/不正解なのか、正解の考え方など）をユーザーにフィードバックしてください。

                    **重要:** 元の解説に仮に正解が記載されていたとしても、その正解自体を直接ユーザーへのフィードバックに記述しないでください。あくまでユーザーの解答に対する評価と、正解に至る考え方を説明するに留めてください。

                    # 元の解説とクイズ:
                    {st.session_state.get('gemini_response', '（元の応答がありません）')}

                    # ユーザー ({st.session_state.get('user_name', '不明')}) の解答:
                    {user_answer}

                    # フィードバック形式（例）:
                    - **採点結果:** 正解です！ / 惜しい！もう少しです / 不正解です
                    - **解説:** [なぜその評価なのか、正解の考え方などを簡潔に記述]
                    """
                    try:
                        with st.spinner("採点中です..."):
                            evaluation_response = model.generate_content(evaluation_prompt)
                            st.markdown("---")
                            st.subheader("採点結果")
                            st.markdown(evaluation_response.text)
                            st.session_state.quiz_evaluated = True
                    except Exception as e:
                        st.error(f"採点中にエラーが発生しました: {e}")
                else:
                    st.warning("クイズの答えを入力してください。") # フォーム送信時に未入力の場合

# クイズがない場合のメッセージ表示
elif 'gemini_response' in st.session_state and st.session_state.get("selected_goal") == "プログラミング学習":
     if not ('quiz_question' in st.session_state and st.session_state.quiz_question):
         if 'explanation' in st.session_state and st.session_state.explanation:
              st.info("今回の回答にはクイズ形式の問題が含まれていないようです。")