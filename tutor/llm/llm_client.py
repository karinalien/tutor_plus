import json
import time
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

# Обновленный URL для соответствия стандарту OpenAI
LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "google/gemma-2-9b"


def generate_test_from_text(material_text: str, max_retries: int = 2, max_tokens: int = 4096):
    system_prompt = (
        "Ты — ассистент для создания тестов. Сгенерируй JSON-объект с тестовыми заданиями на основе предоставленного текста. "
        "Каждое задание включает: id, material, question, options (A,B,C,D), correct. "
        "Очень важно: не копируй численные значения из исходного материала. Вместо этого генерируй новые, правдоподобные числа (например, другие длины, суммы, проценты, количества), сохраняя логику темы. "
        "Числа в заданиях должны отличаться от исходных, но быть реалистичными и непротиворечивыми, и оставаться в той же единице измерения. "
        "Качество вариантов ответов: каждый вариант должен быть осмысленной русскоязычной строкой (не пустой), без одиночных символов, скобок, кавычек или наборов знаков. Не допускаются варианты вроде '}', '{', '[]', '---'. Длина 3–120 символов. "
        "Поле correct должно быть одной из букв 'A', 'B', 'C', 'D'. "
        "Ответ строго в формате JSON."
    )

    user_prompt = (
        "Сгенерируй 5–7 заданий по теме текста. Для каждого задания: уникальный `material`, отдельный `question`, 4 варианта `options`, поле `correct`. "
        "ВНИМАНИЕ: используй новые числа, не беря их из исходного текста. Меняй параметры (размеры, количества, проценты, суммы) так, чтобы они соответствовали теме, но не совпадали с материалом. "
        "Не включай формулировку вопроса в `material` — она должна быть только в `question`. "
        "Убедись, что варианты ответов — нормальные фразы на русском, без бессмысленных символов.\n\n"
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
        "temperature": 0.65,
        "max_tokens": max_tokens
    }

    def _options_text_quality_ok(json_text: str) -> bool:
        try:
            obj = json.loads(json_text)
        except Exception:
            return False
        tasks = obj if isinstance(obj, list) else obj.get("tasks") or obj.get("questions") or []
        if not isinstance(tasks, list) or not tasks:
            return False
        def bad(s: str) -> bool:
            if not isinstance(s, str):
                return True
            t = s.strip()
            if len(t) < 3 or len(t) > 120:
                return True
            # фильтры по бессмысленным вариантам
            letters = sum(1 for ch in t if ch.isalpha())
            if letters < max(1, len(t) // 6):
                return True

            if t in {"{", "}", "[]", "[ ]", "()", "( )", "''", '""', "---", "--", "-"}:
                return True
            return False
        for q in tasks:
            opts = q.get("options") if isinstance(q, dict) else None
            if not isinstance(opts, dict):
                return False
            for k in ["A", "B", "C", "D"]:
                if k not in opts or bad(opts[k]):
                    return False
            corr = q.get("correct")
            if corr not in {"A", "B", "C", "D"}:
                return False
        return True

    for attempt in range(max_retries + 1):
        try:
            print("🤖 Отправка запроса в LM Studio...")
            response = requests.post(LMSTUDIO_URL, json=payload, timeout=300)
            response.raise_for_status()

            data = response.json()
            # Стандартный парсинг ответа для chat/completions
            content = data["choices"][0]["message"]["content"]
            
            text = content.strip()
            if _options_text_quality_ok(text):
                return text
            else:
                print("⚠️ Низкое качество вариантов ответов. Повторная генерация с уточняющей инструкцией...")
                payload_retry = {
                    "model": LMSTUDIO_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                        {"role": "user", "content": (
                            "Пересоздай варианты ответов так, чтобы каждый был осмысленной русскоязычной фразой, "
                            "без одиночных символов, скобок и мусора. Сохрани структуру JSON и букву в `correct`."
                        )}
                    ],
                    "response_format": {"type": "text"},
                    "temperature": 0.7,
                    "max_tokens": max_tokens
                }
                response2 = requests.post(LMSTUDIO_URL, json=payload_retry, timeout=300)
                response2.raise_for_status()
                data2 = response2.json()
                content2 = data2["choices"][0]["message"]["content"].strip()
                if _options_text_quality_ok(content2):
                    return content2
                # если снова плохо — вернем исходный текст, чтобы не ломать поток
                return text

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

