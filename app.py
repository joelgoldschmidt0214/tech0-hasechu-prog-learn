import streamlit as st
import google.generativeai as genai
import os
import json
import re
from dotenv import load_dotenv
# from supabase import create_client, Client

# --- 初期設定 (変更なし) ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("エラー: GOOGLE_API_KEYが設定されていません。.envファイルを確認してください。")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)
# Supabase設定 (コメントアウトのまま)
# ...
try:
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    st.error(f"Geminiモデルの読み込みに失敗しました: {e}")
    st.stop()

# --- Streamlit UI ---
st.set_page_config(page_title="プログラミング学習サポート", layout="wide")
st.title("プログラミング学習サポート")
st.caption("Gemini API と Supabase を活用した学習アプリ")

# --- サイドバー: ユーザー入力 ---
with st.sidebar:
    if st.button("結果をクリア"):
        keys_to_delete = ['gemini_response', 'explanation', 'quiz_question', 'quiz_active', 'quiz_evaluated']
        for key in keys_to_delete:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun() # 画面を再描画してクリアを反映
    st.header("設定")
    languages = ["Python", "HTML", "CSS", "JavaScript", "SQL"]
    selected_language = st.selectbox("学習したい言語を選択してください:", languages)
    goals = ["困りごとの解決", "プログラミング学習"]
    selected_goal = st.selectbox("目的を選択してください:", goals)
    levels = ["初学者", "何となくコードを読める", "自分でコーディングできる", "自力でバグ解消できる"]
    selected_level = st.selectbox("現在の技術レベルを選択してください:", levels)
    problem_details = st.text_area("困りごとや質問の詳細を具体的に記入してください:", height=150)

    # ファイルアップロード（許可タイプは前回同様）
    allowed_text_extensions = [
        "py", "html", "css", "js", "sql", "txt", "md", "log",
        "json", "yaml", "toml", "ini", "xml", "csv",
        "xhtml", "htm", "mjs", "cjs", "ipynb"
        ]
    uploaded_file = st.file_uploader(
        f"関連するテキストファイルをアップロード (任意、許可タイプ: .{', .'.join(allowed_text_extensions)}):",
        type=allowed_text_extensions
    )

    submit_button = st.button("実行する")

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

# --- 依頼ボタン処理 ---
if submit_button:
    # --- ファイル処理ロジック ---
    file_content = None # 成功した場合にテキストが入る
    file_info = ""      # ファイルに関する情報を格納
    encoding_used = None # 成功したエンコーディング
    process_file = True # ファイル処理を続けるかどうかのフラグ

    if uploaded_file is not None:
        file_name = uploaded_file.name
        file_size = uploaded_file.size
        st.write(f"アップロードされたファイル: `{file_name}` ({file_size / 1024:.1f} KB)")
        file_info = f"ファイル名: {file_name}" # まずファイル名を記録

        try:
            # 1. ipynbファイルかどうか判定
            if file_name.endswith(".ipynb"):
                file_info += " (.ipynb)"
                try:
                    uploaded_file.seek(0) # ポインタをリセット
                    notebook_content = uploaded_file.getvalue().decode("utf-8") # ipynbは通常utf-8
                    notebook = json.loads(notebook_content)
                    code_cells = [cell['source'] for cell in notebook.get('cells', []) if cell.get('cell_type') == 'code']
                    file_content = "\n\n".join(["".join(cell) for cell in code_cells])
                    encoding_used = "utf-8 (ipynb code cells)"
                    st.text_area("抽出されたコードセル (.ipynb)", file_content, height=150)
                except (json.JSONDecodeError, UnicodeDecodeError) as e_ipynb_parse:
                    st.warning(f".ipynbファイルの解析またはUTF-8デコードに失敗しました ({e_ipynb_parse})。ファイル全体をテキストとして扱います。")
                    # 解析失敗時はファイル全体をテキストとして再試行
                    try:
                        uploaded_file.seek(0)
                        # UTF-8 -> Shift_JIS の順で試す
                        try:
                           file_content = uploaded_file.getvalue().decode("utf-8")
                           encoding_used = "utf-8 (ipynb raw)"
                        except UnicodeDecodeError:
                           uploaded_file.seek(0)
                           file_content = uploaded_file.getvalue().decode("shift-jis")
                           encoding_used = "shift-jis (ipynb raw)"
                           st.info(".ipynbファイルをShift-JISとして読み込みました(RAW)。")
                        st.text_area("ファイルの内容 (.ipynb - RAW)", file_content, height=150)
                    except UnicodeDecodeError:
                         st.error(f".ipynbファイル(RAW)はUTF-8またはShift-JISとしてデコードできませんでした。")
                         file_info += " (RAWデコード失敗)"
                         file_content = None
                         process_file = False
                    except Exception as e_ipynb_raw:
                         st.error(f".ipynbファイル(RAW)の処理中にエラー: {e_ipynb_raw}")
                         file_info += " (RAW処理エラー)"
                         file_content = None
                         process_file = False
                except Exception as e_ipynb_other:
                    st.error(f".ipynb ファイルの処理中に予期せぬエラーが発生しました: {e_ipynb_other}")
                    file_info += " (処理エラー)"
                    file_content = None
                    process_file = False
            # ipynbでない他の許可されたファイル
            else:
                uploaded_file.seek(0)
                file_bytes = uploaded_file.getvalue()

                # 2. utf-8でテキスト変換試行
                try:
                    file_content = file_bytes.decode("utf-8")
                    encoding_used = "utf-8"
                except UnicodeDecodeError:
                    # 3. shift-jisでテキスト変換試行
                    try:
                        file_content = file_bytes.decode("shift-jis")
                        encoding_used = "shift-jis"
                        st.info(f"ファイル '{file_name}' はShift-JISとして読み込まれました。")
                    except UnicodeDecodeError:
                        # 4. デコード失敗 -> 警告出して終了
                        st.error(f"ファイル '{file_name}' はUTF-8またはShift-JISとしてデコードできませんでした。テキストファイルでないか、未対応の文字コードの可能性があります。")
                        file_info += " (テキスト変換不可)"
                        file_content = None
                        process_file = False
                    except Exception as e_sjis:
                         st.error(f"Shift-JISデコード中に予期せぬエラー: {e_sjis}")
                         file_info += " (Shift-JISデコードエラー)"
                         file_content = None
                         process_file = False

        except Exception as e_outer:
             st.error(f"ファイル処理中に予期せぬエラーが発生しました: {e_outer}")
             file_info += " (不明なエラー)"
             file_content = None
             process_file = False

        # 5. 文字数制限のチェック (デコード成功した場合のみ)
        if process_file and file_content is not None:
            max_chars = 15000 # 文字数制限 (Geminiの入力制限も考慮)
            if len(file_content) > max_chars:
                st.error(f"ファイル '{file_name}' の文字数 ({len(file_content)}文字) が制限 ({max_chars}文字) を超えています。このファイルは処理されません。")
                file_info += f" (文字数超過: {len(file_content)} > {max_chars})"
                file_content = None # 処理を中断するためNoneにする
                process_file = False # このファイルは使わない
            else:
                 # 成功した場合のみエンコーディング情報を追加
                 file_info += f" ({len(file_content)}文字, encoding: {encoding_used})"

    # --- プロンプト生成とGemini呼び出し ---
    st.subheader("Geminiへの依頼内容")

    # プロンプトの組み立て
    prompt_parts = [
        f"あなたはプログラミング学習をサポートする親切なAIアシスタントです。",
        f"対象言語: {selected_language}",
        f"ユーザーの目的: {selected_goal}",
        f"ユーザーの技術レベル: {selected_level}",
    ]

    if problem_details:
        prompt_parts.append(f"\n# ユーザーからの質問や困りごと:\n{problem_details}")
    else:
        # デフォルト指示 (変更なし)
        if selected_goal == "困りごとの解決":
             prompt_parts.append("\n# ユーザーからの具体的な質問:")
             prompt_parts.append("ユーザーは具体的な困りごとを入力していません。アップロードされたファイル情報（もしあれば）や選択された言語、レベルから想定される一般的な問題や、その言語の基本的な使い方について解説してください。")
        elif selected_goal == "プログラミング学習":
             prompt_parts.append("\n# ユーザーからの具体的な質問:")
             prompt_parts.append(f"ユーザーは具体的な質問を入力していません。{selected_language}の基本的な概念や、{selected_level}のユーザーが学び始めると良いトピックについて解説してください。")


    prompt_parts.append("\n以下の情報に基づいて、ユーザーのリクエストに応じた回答を生成してください。")

    # ファイル情報と内容をプロンプトに追加
    if file_info: # ファイルがアップロードされた場合
        prompt_parts.append(f"\n--- ユーザーが提供したファイル情報 ---")
        prompt_parts.append(file_info) # ファイル名、状態、文字数、エンコーディングなど
        # process_fileがTrueでfile_contentが存在する場合のみ内容を追加
        if process_file and file_content is not None:
             prompt_parts.append("\n--- ファイル内容 ---")
             prompt_parts.append(file_content) # 文字数制限チェック済み
             prompt_parts.append("--- ファイル内容ここまで ---")
        # else: # 内容がない、または処理しない場合は情報はfile_infoに含まれている
        #     prompt_parts.append("(ファイル内容は処理されませんでした)")
        prompt_parts.append("--- ファイル情報ここまで ---")


    # 目的別の指示を追加 (変更なし)
    if selected_goal == "困りごとの解決":
        prompt_parts.append("\n# 指示:")
        prompt_parts.append("- ユーザーの質問や困りごと、提供されたファイル情報（内容含む、もし処理されていれば）に基づいて、具体的な解決策やコード例を提示してください。")
        prompt_parts.append("- **重要:** 回答の最後に、参考文献として役立つ可能性のあるWebサイトのURLを必ず3つから5つ提示してください。形式は問いませんが、リスト形式などが望ましいです。")
        prompt_parts.append("- 回答はマークダウン形式で、読みやすく記述してください。")
    elif selected_goal == "プログラミング学習":
        prompt_parts.append("\n# 指示:")
        prompt_parts.append(f"- {selected_language}の{selected_level}レベルのユーザー向けに、ユーザーからの質問や提供されたファイル情報（内容含む、もし処理されていれば）に関連する基本的な概念や書き方を解説してください。")
        prompt_parts.append("- **重要:** 解説の最後に、内容の理解度を確認するための簡単なクイズを1つ作成してください。")
        prompt_parts.append("- **クイズの形式:** 必ず応答の最後に、改行を挟んでから `Q: [質問文]` の形式で質問文のみを提示してください。")
        prompt_parts.append("- **絶対に、絶対に、絶対にクイズの解答や正解を示唆するヒントをユーザー向けの出力に含めないでください。** 解答はAI内部で保持するだけに留め、ユーザーには一切見せないようにしてください。")
        prompt_parts.append("- 回答はマークダウン形式で、読みやすく記述してください。")

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


# --- 3. 回答表示とインタラクション (変更なし) ---
# 解説表示
if 'explanation' in st.session_state and st.session_state.explanation:
    st.markdown(st.session_state.explanation)

# クイズ表示・採点
if 'quiz_active' in st.session_state and st.session_state.quiz_active:
    if 'quiz_question' in st.session_state and st.session_state.quiz_question:
        st.markdown("---")
        st.subheader("クイズに挑戦！")
        st.markdown(st.session_state.quiz_question)
        user_answer = st.text_input("クイズの答えを入力してください:", key="quiz_answer_input")
        submit_quiz_button = st.button("採点する", key="submit_quiz")
        if submit_quiz_button and user_answer:
            # 採点プロンプト生成 (変更なし)
            evaluation_prompt = f"""
            あなたはプログラミングクイズの採点者です。
            以下の「元の解説とクイズ」と「ユーザーの解答」を比較し、ユーザーの解答がクイズの意図に合っているか、正解と言えるかを判断してください。
            判断結果と、簡単な解説（なぜ正解/不正解なのか、正解の考え方など）をユーザーにフィードバックしてください。

            **重要:** 元の解説に仮に正解が記載されていたとしても、その正解自体を直接ユーザーへのフィードバックに記述しないでください。あくまでユーザーの解答に対する評価と、正解に至る考え方を説明するに留めてください。

            # 元の解説とクイズ:
            {st.session_state.gemini_response}

            # ユーザーの解答:
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
        elif submit_quiz_button and not user_answer:
            st.warning("クイズの答えを入力してください。")

elif 'gemini_response' in st.session_state and selected_goal == "プログラミング学習":
     if not ('quiz_question' in st.session_state and st.session_state.quiz_question):
         if 'explanation' in st.session_state and st.session_state.explanation:
              st.info("今回の回答にはクイズ形式の問題が含まれていないようです。")