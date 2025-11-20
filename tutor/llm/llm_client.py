import time
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

LMSTUDIO_URL = "http://127.0.0.1:12345/v1/chat/completions"
LMSTUDIO_MODEL = "qwen2.5-1.5b-instruct"

def generate_test_from_text(material_text: str, max_retries: int = 2, max_tokens: int = 3000):

    prompt = f"""
Ты — генератор образовательных тестов.
Создай 5–7 тестовых вопросов по материалу ниже.

Требования к тестам:
- Каждый вопрос должен быть САМОСТОЯТЕЛЬНЫМ.
- У каждого вопроса должно быть 4 варианта ответа (A, B, C, D).
- Только один вариант ответа должен быть правильным.
- Вопрос не должен ссылаться на материалы или внешний контекст.
- Если для решения требуется правило, формула или алгоритм — вставь краткое описание прямо в текст вопроса.
- Не используй символы вроде "#", "*". Только кириллица и цифры.

Шаги:
1) Проанализируй материал и выдели ключевые понятия.
2) Определи потенциально непонятные элементы и включи их описание в вопрос.
3) Проверь, что каждый вопрос содержит всё, что нужно ученику.
4) Оставь итоговые вопросы, строго соблюдая формат.

Материал для анализа:
{material_text}

Формат вывода:
1. [Вопрос]
   A) ...
   B) ...
   C) ...
   D) ...
   Правильный ответ: X

2. ...
""".strip()

    payload = {
        "model": LMSTUDIO_MODEL,
        "messages": [
            {"role": "system", "content": "Ты — генератор тестов. Ты создаешь вопросы строго по требованиям пользователя."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(LMSTUDIO_URL, json=payload, timeout=240)

            if response.status_code == 503:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return "❌ LM Studio ответил 503 (модель не готова или перегружена)."

            if response.status_code == 404:
                return "❌ Модель не найдена. Проверь название модели в LM Studio."

            if response.status_code == 500:
                return "❌ Внутренняя ошибка LM Studio (500). Перезапусти модель."

            response.raise_for_status()

            data = response.json()
            choices = data.get("choices")
            if not choices or not isinstance(choices, list):
                return "❌ Ошибка: пустой ответ от модели."

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return "❌ Ошибка: модель вернула пустой текст."

            return content.strip()

        except (ConnectionError, Timeout):
            if attempt < max_retries:
                time.sleep(1)
                continue
            return "❌ Ошибка подключения или таймаут: LM Studio не отвечает."

        except RequestException as e:
            return f"❌ Ошибка HTTP: {str(e)}"

        except Exception as e:
            return f"❌ Неожиданная ошибка: {str(e)}"

    return "❌ Ошибка: не удалось получить ответ от модели."
