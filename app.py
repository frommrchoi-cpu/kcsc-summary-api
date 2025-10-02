from flask import Flask, jsonify, request
import requests, os, json, math
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
app = Flask(__name__)
client = OpenAI()

# -----------------------------
# 모델별 context window 정의
# -----------------------------
MODEL_CONTEXT_WINDOWS = {
    "gpt-4o": 128000,        # 128k tokens
    "gpt-4o-mini": 128000,
    "gpt-4.1": 200000,       # 200k tokens
    "gpt-3.5-turbo": 16000
}

# 문자 단위 chunking 유틸
def safe_chunk_text(text, model="gpt-4o"):
    max_tokens = MODEL_CONTEXT_WINDOWS.get(model, 16000)
    max_chars = max_tokens * 3  # conservative (token≈3 chars)
    if len(text) <= max_chars:
        return [text]

    chunks = []
    num_chunks = math.ceil(len(text) / max_chars)
    for i in range(num_chunks):
        start = i * max_chars
        end = start + max_chars
        chunks.append(text[start:end])
    return chunks


# GPT 요약 유틸
def summarize_text(text, model="gpt-4o", prompt="Summarize this for practical design application."):
    chunks = safe_chunk_text(text, model=model)
    partial_summaries = []

    for chunk in chunks:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": chunk}
            ],
            temperature=0
        )
        partial_summaries.append(resp.choices[0].message.content)

    # 여러 chunk면 최종 압축 요약
    if len(partial_summaries) > 1:
        combined = "\n".join(partial_summaries)
        final_resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Combine and compress the following partial summaries into a single coherent summary for design application."},
                {"role": "user", "content": combined}
            ],
            temperature=0
        )
        return final_resp.choices[0].message.content
    else:
        return partial_summaries[0]


@app.route('/')
def home():
    return "✅ KCSC 요약 중간 서버 정상 작동"


# -----------------------------
# CodeList 전체 요약
# -----------------------------
@app.route('/kcsc_summary', methods=['GET'])
def kcsc_summary():
    try:
        kcsc_api_key = os.getenv("KCSC_API_KEY")
        model = "gpt-4o"

        kcsc_url = f"https://kcsc.re.kr/OpenApi/CodeList?key={kcsc_api_key}"
        kcsc_resp = requests.get(kcsc_url)
        if kcsc_resp.status_code != 200:
            return jsonify({'error': 'KCSC CodeList API 요청 실패'}), 500

        kcsc_data = kcsc_resp.text
        summary = summarize_text(
            kcsc_data,
            model=model,
            prompt="Summarize the following construction code list for practical design application."
        )
        return jsonify({'summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# -----------------------------
# CodeViewer 상세 요약 + 체크리스트
# -----------------------------
@app.route('/kcsc_detail_summary', methods=['GET'])
def kcsc_detail_summary():
    try:
        kcsc_api_key = os.getenv("KCSC_API_KEY")
        code_id = request.args.get("code")
        model = "gpt-4o"

        if not code_id:
            return jsonify({'error': 'code 파라미터가 필요합니다'}), 400

        kcsc_url = f"https://kcsc.re.kr/OpenApi/CodeViewer?key={kcsc_api_key}&code={code_id}"
        kcsc_resp = requests.get(kcsc_url)
        if kcsc_resp.status_code != 200:
            return jsonify({'error': 'KCSC CodeViewer API 요청 실패'}), 500

        kcsc_data = kcsc_resp.text

        detail_output = summarize_text(
            kcsc_data,
            model=model,
            prompt=(
                "You are an assistant for civil/structural engineers. "
                "Summarize the following construction code detail in two parts: "
                "1) summary: concise explanation, "
                "2) checklist: practical on-site items engineers should verify or follow. "
                "Respond strictly in JSON with fields: summary, checklist (array)."
            )
        )

        try:
            detail_result = json.loads(detail_output)
        except:
            detail_result = {"summary": detail_output, "checklist": []}

        return jsonify({
            "code": code_id,
            "summary": detail_result.get("summary", ""),
            "checklist": detail_result.get("checklist", [])
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# -----------------------------
# CodeList + 중요 코드 3개 선택 → 상세 요약+체크리스트
# -----------------------------
@app.route('/kcsc_full_summary', methods=['GET'])
def kcsc_full_summary():
    try:
        kcsc_api_key = os.getenv("KCSC_API_KEY")
        model = "gpt-4o"

        # 1) CodeList 가져오기
        list_url = f"https://kcsc.re.kr/OpenApi/CodeList?key={kcsc_api_key}"
        list_resp = requests.get(list_url)
        if list_resp.status_code != 200:
            return jsonify({'error': 'KCSC CodeList API 요청 실패'}), 500

        list_json = list_resp.json()
        simplified_list = []
        for item in list_json.get("items", []):
            code = item.get("code")
            title = item.get("title")
            if code and title:
                simplified_list.append({"code": code, "title": title})

        gpt_input = "\n".join([f"{x['code']}: {x['title']}" for x in simplified_list])

        # 2) GPT: 요약 + 중요 코드 3개 뽑기
        list_summary_resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant for civil/structural engineers. "
                        "From the following KCSC CodeList (code: title pairs), "
                        "1) Provide a concise overall summary, "
                        "2) Select the 3 most important 'code' IDs for practical design application. "
                        "Respond strictly in JSON with fields: list_summary, important_codes (array of 3 codes)."
                    )
                },
                {"role": "user", "content": gpt_input}
            ],
            temperature=0
        )
        gpt_output = list_summary_resp.choices[0].message.content

        try:
            gpt_result = json.loads(gpt_output)
            list_summary = gpt_result.get("list_summary", "")
            important_codes = gpt_result.get("important_codes", [])
        except:
            list_summary = gpt_output
            important_codes = [x["code"] for x in simplified_list[:3]]

        # 3) CodeViewer 상세 요약 + 체크리스트
        detail_summaries = []
        for code_id in important_codes:
            detail_url = f"https://kcsc.re.kr/OpenApi/CodeViewer?key={kcsc_api_key}&code={code_id}"
            detail_resp = requests.get(detail_url)
            if detail_resp.status_code != 200:
                continue

            kcsc_detail_raw = detail_resp.text
            detail_output = summarize_text(
                kcsc_detail_raw,
                model=model,
                prompt=(
                    "You are an assistant for civil/structural engineers. "
                    "Summarize the following construction code detail in two parts: "
                    "1) summary: concise explanation, "
                    "2) checklist: practical on-site items engineers should verify or follow. "
                    "Respond strictly in JSON with fields: summary, checklist (array)."
                )
            )

            try:
                detail_result = json.loads(detail_output)
                detail_summaries.append({
                    "code": code_id,
                    "summary": detail_result.get("summary", ""),
                    "checklist": detail_result.get("checklist", [])
                })
            except:
                detail_summaries.append({
                    "code": code_id,
                    "summary": detail_output,
                    "checklist": []
                })

        return jsonify({
            "list_summary": list_summary,
            "important_codes": important_codes,
            "detail_summaries": detail_summaries
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
