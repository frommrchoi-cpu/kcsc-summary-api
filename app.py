from flask import Flask, request, jsonify
import requests
import openai
from dotenv import load_dotenv
import os

# .env 환경변수 로드
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
kcsc_api_key = os.getenv("KCSC_API_KEY")

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ KCSC 요약 중간 서버가 정상 작동 중입니다."

@app.route('/kcsc_summary', methods=['GET'])
def kcsc_summary():
    try:
        kcsc_url = f"https://kcsc.re.kr/OpenApi/CodeList?key={kcsc_api_key}"
        kcsc_resp = requests.get(kcsc_url)

        if kcsc_resp.status_code != 200:
            return jsonify({'error': 'KCSC API 요청 실패'}), 500

        kcsc_data = kcsc_resp.text[:15000]  # 너무 긴 경우 자르기

        summary_resp = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Summarize the following construction code for practical design application."},
                {"role": "user", "content": kcsc_data}
            ]
        )

        return jsonify({'summary': summary_resp['choices'][0]['message']['content']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Render 배포용 포트 지정
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
