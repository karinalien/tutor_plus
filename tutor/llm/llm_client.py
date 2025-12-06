import json
import time
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "google/gemma-2-9b"


def generate_test_from_text(material_text: str, max_retries: int = 2, max_tokens: int = 4096):
    system_prompt = (
        "Ты — ассистент для создания тестов. Твоя задача — сгенерировать JSON-объект с тестовыми заданиями на основе предоставленного текста. "
        "Каждое задание должно включать в себя: "
        "- id: уникальный номер вопроса. "
        "- material: описание алгоритма или контекст, относящийся ТОЛЬКО к этому заданию. "
        "- question: сам вопрос по заданию. "
        "- options: четыре варианта ответа (A, B, C, D). "
        "- correct: правильный вариант ответа. "
        "Ответ должен быть в формате JSON."
    )

    user_prompt = (
        "Сгенерируй 5-7 тестовых заданий на основе следующего текста. "
        "Для каждого задания предоставь уникальное описание алгоритма в поле `material`. "
        "Убери из описания алгоритма последнее предложение с вопросом, так как для этого есть отдельное поле `question`.\n\n"
        f"Текст для анализа:\n{material_text}"
    )

    payload = {
        "model": LMSTUDIO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {
            "type": "text"
        },
        "temperature": 0.5,
        "max_tokens": max_tokens
    }

    for attempt in range(max_retries + 1):
        try:
            print("🤖 Отправка запроса в LM Studio...")
            response = requests.post(LMSTUDIO_URL, json=payload, timeout=300)
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()

        except (ConnectionError, Timeout) as e:
            error_message = f"❌ Ошибка подключения к LM Studio: {e}. Убедитесь, что сервер запущен."
            print(error_message)
            if attempt >= max_retries:
                return json.dumps({"error": error_message})
        except RequestException as e:
            error_message = f"❌ Ошибка запроса: {e}. Ответ сервера: {response.text if 'response' in locals() else 'N/A'}"
            print(error_message)
            if attempt >= max_retries:
                return json.dumps({"error": error_message})
        except (KeyError, IndexError) as e:
            error_message = f"❌ Ошибка парсинга ответа от LM Studio: {e}. Ответ: {data}"
            print(error_message)
            if attempt >= max_retries:
                return json.dumps({"error": error_message})
        except Exception as e:
            error_message = f"❌ Неизвестная ошибка: {e}"
            print(error_message)
            if attempt < max_retries:
                print(f"Попытка {attempt + 1} из {max_retries + 1}. Повтор через 2 секунды...")
                time.sleep(2)
                continue
            return json.dumps({"error": error_message})

    return json.dumps({"error": "Не удалось получить ответ после нескольких попыток."})

