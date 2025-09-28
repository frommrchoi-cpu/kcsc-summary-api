from flask import Flask, jsonify
import requests
from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
client = OpenAI()

@app.route('/')
def home():
    return "✅ KCSC 요약 중간 서버가 정상 작동 중입니다."

@app.route('/kcsc_summary', methods=['GET'])
def kcsc_summary():
    try:
        kcsc_api_key = os.getenv("KCSC_API_KEY")
        kcsc_url = f"https://kcsc.re.kr/OpenApi/CodeList?key={kcsc_api_key}"
        kcsc_resp = requests.get(kcsc_url)

        if kcsc_resp.status_code != 200:
            return jsonify({'error': 'KCSC API 요청 실패'}), 500

        kcsc_data = kcsc_resp.text[:15000]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Summarize the following construction code for practical design application."},
                {"role": "user", "content": kcsc_data}
            ]
        )

        summary_text = response.choices[0].message.content
        return jsonify({'summary': summary_text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
