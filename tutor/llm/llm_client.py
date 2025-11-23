import time
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

LMSTUDIO_URL = "http://127.0.0.1:12345/v1/responses"
LMSTUDIO_MODEL = "qwen/qwen3-4b"   


def generate_test_from_text(material_text: str, max_retries: int = 2, max_tokens: int = 3000):
    prompt = (
        "Ты — генератор тестов.\n"
        "Создай 5–7 самостоятельных тестовых вопросов.\n"
        "Используй только русский язык.\n"
        "У каждого вопроса должно быть 4 варианта ответа (A, B, C, D) и один правильный.\n"
        "Если в материале есть алгоритмы — кратко объясняй их прямо в вопросе.\n\n"
        "Материал:\n"
        f"{material_text}"
    )

    print(f"DEBUG: material_text = {repr(material_text[:200])}")

    payload = {
        "model": LMSTUDIO_MODEL,
        "input": prompt,  
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": max_tokens
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(LMSTUDIO_URL, json=payload, timeout=240)
            response.raise_for_status()

            data = response.json()
            content = data["output"][0]["content"][0]["text"]
            return content.strip()

        except Exception as e:
            if attempt < max_retries:
                time.sleep(1)
                continue
            return f"❌ Ошибка: {e}"

    return "❌ Ошибка: не удалось получить ответ после повторов."

