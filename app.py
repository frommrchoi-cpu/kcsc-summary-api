from flask import Flask, jsonify, request
import requests, os
from dotenv import load_dotenv
from openai import OpenAI
import math

load_dotenv()
app = Flask(__name__)
client = OpenAI()

@app.route('/')
def home():
    return "✅ KCSC 요약 중간 서버 정상 작동"

@app.route('/kcsc_summary', methods=['GET'])
def kcsc_summary():
    try:
        # Query parameters
        query = request.args.get("query", default=None, type=str)
        limit = request.args.get("limit", default=5, type=int)
        batch = request.args.get("batch", default=1, type=int)

        # API 호출
        kcsc_api_key = os.getenv("KCSC_API_KEY")
        kcsc_url = f"https://kcsc.re.kr/OpenApi/CodeList?key={kcsc_api_key}"
        kcsc_resp = requests.get(kcsc_url)

        if kcsc_resp.status_code != 200:
            return jsonify({'error': 'KCSC API 요청 실패'}), 500

        # 대용량 데이터 가져오기
        kcsc_data = kcsc_resp.text

        # 🔹 필터링 (query가 지정된 경우)
        if query:
            filtered_lines = [line for line in kcsc_data.splitlines() if query in line]
            kcsc_data = "\n".join(filtered_lines) if filtered_lines else kcsc_data

        # 🔹 GPT 요약 요청 (대용량 데이터 → GPT 입력 크기 제한 적용)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 건설·토목 설계자가 활용하는 KCSC 코드 요약 도우미다. "
                        "아래 데이터를 분석해서 코드 번호, 코드명칭, 설계 적용 포인트를 구조화하여 5~10개 단위로 요약해라. "
                        "출력은 JSON 형식: [{code, title, note}]."
                    )
                },
                {"role": "user", "content": kcsc_data[:15000]}  # 너무 길면 15,000자로 제한
            ]
        )

        # GPT 응답 파싱
        gpt_content = response.choices[0].message.content

        # ⚠️ 단순 파싱 예시 (실제로는 json.loads 등 추가 가공 필요)
        # 여기서는 GPT 응답이 JSON 배열 형태라고 가정
        import json
        try:
            all_results = json.loads(gpt_content)
        except Exception:
            # GPT가 JSON이 아닌 텍스트로 반환 시 fallback
            all_results = [{"code": "-", "title": "-", "note": gpt_content}]

        # 🔹 Pagination 처리
        total_items = len(all_results)
        start_idx = (batch - 1) * limit
        end_idx = start_idx + limit
        batch_results = all_results[start_idx:end_idx]

        next_batch_available = end_idx < total_items

        return jsonify({
            "summary": batch_results,
            "next_batch_available": next_batch_available
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
