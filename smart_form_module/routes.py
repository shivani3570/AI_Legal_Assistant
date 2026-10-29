import os
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Blueprint, render_template, request, jsonify
from groq import Groq

load_dotenv()

smart_form_bp = Blueprint(
    "smart_form",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/smart-form-static",
)

GROQ_MODEL = "openai/gpt-oss-120b"

LANGUAGES = {
    "en": "English", "kn": "Kannada", "hi": "Hindi",
    "ta": "Tamil", "te": "Telugu",
    "english": "English", "kannada": "Kannada",
    "hindi": "Hindi", "tamil": "Tamil", "telugu": "Telugu",
}

PROTECTED_TYPES = {
    "email", "tel", "number", "range", "date", "time",
    "datetime-local", "month", "week", "url", "password",
}


def normalize_language(language):
    value = str(language or "English").strip()
    return LANGUAGES.get(value.lower(), value)


def ask_groq(instructions, prompt):
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing from .env")

    client = Groq(api_key=api_key)
    result = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
    )
    return (result.choices[0].message.content or "").strip()


def extract_fields(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a valid HTTP or HTTPS URL.")

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.find("form")
    scope = form if form else soup
    fields = []

    for element in scope.select("input, textarea, select"):
        tag = element.name.lower()
        kind = (element.get("type") or tag).lower()

        if kind in {"hidden", "submit", "button", "reset", "image", "file"}:
            continue

        field_id = element.get("id", "")
        field_name = element.get("name", "")
        label_element = (
            soup.find("label", attrs={"for": field_id})
            if field_id else None
        )
        parent_label = element.find_parent("label")

        label = (
            label_element.get_text(" ", strip=True)
            if label_element else
            parent_label.get_text(" ", strip=True)
            if parent_label else
            element.get("aria-label")
            or element.get("placeholder")
            or field_name
            or field_id
            or f"Field {len(fields) + 1}"
        )

        options = []
        if tag == "select":
            options = [
                {
                    "value": option.get("value", option.get_text(strip=True)),
                    "text": option.get_text(" ", strip=True),
                }
                for option in element.find_all("option")
            ]

        fields.append({
            "id": field_id,
            "name": field_name,
            "label": label,
            "type": "textarea" if tag == "textarea"
                    else "select" if tag == "select"
                    else kind,
            "required": element.has_attr("required"),
            "placeholder": element.get("placeholder", ""),
            "options": options,
        })

    if not fields:
        raise ValueError("No standard HTML fields were found.")

    return fields
@smart_form_bp.get("/smart-form-assistant")
def smart_form_home():
    return render_template("smart_form_assistant_fresh.html")


@smart_form_bp.post("/smart-form-assistant/analyze")
def smart_form_analyze():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()

    try:
        fields = extract_fields(url)
        return jsonify(
            success=True, url=url, fields=fields, count=len(fields)
        )
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 400
    except requests.exceptions.RequestException:
        return jsonify(
            success=False, error="Could not open the form URL."
        ), 400
    except Exception as exc:
        print("Form analysis error:", repr(exc))
        return jsonify(
            success=False, error="Could not analyze this form."
        ), 500


@smart_form_bp.post("/smart-form-assistant/translate")
def smart_form_translate():
    data = request.get_json(silent=True) or {}

    text = str(data.get("text", "")).strip()
    language = normalize_language(data.get("language", "English"))
    target = normalize_language(data.get("targetLanguage", "English"))
    mode = str(data.get("mode", "question")).lower()
    field_type = str(data.get("fieldType", "text")).lower()
    label = str(data.get("fieldLabel", "")).strip()

    if not text:
        return jsonify(success=False, error="Text is required."), 400

    if mode not in {"question", "answer"}:
        return jsonify(success=False, error="Invalid translation mode."), 400

    if mode == "answer" and (
        field_type in PROTECTED_TYPES
        or re.search(r"email|e-mail|phone|mobile", label, re.I)
    ):
        return jsonify(success=True, translated=text)

    if mode == "question":
        instructions = (
            "You are a friendly voice assistant helping a person fill "
            "out a form. Translate the question into natural, simple "
            "spoken language in the requested language. Use the correct "
            "native script. Kannada must use Kannada script; Hindi must "
            "use Devanagari. Return only the question."
        )
        prompt = f"Language: {language}\nQuestion: {text}"

    else:
        is_name = bool(re.search(
            r"name|ಹೆಸರು|नाम|பெயர்|పేరు", label, re.I
        ))

        if is_name:
            instructions = (
                "Convert the person's spoken name into English/Latin "
                "letters by transliteration, not translation. For example, "
                "ಯೋಗಿತಾ becomes Yogitha. Return only the name, without "
                "'my name is'. Do not invent extra information."
            )
        else:
            instructions = (
                "Convert the user's answer into the destination language. "
                "Translate ordinary descriptive answers when English is "
                "the destination. Preserve meaning and do not invent "
                "information. Return only the converted answer."
            )

        prompt = (
            f"Spoken language: {language}\n"
            f"Destination language: {target}\n"
            f"Field label: {label}\n"
            f"Field type: {field_type}\n"
            f"User answer: {text}"
        )

    try:
        converted = ask_groq(instructions, prompt)
        if not converted:
            raise RuntimeError("Empty AI response.")
        return jsonify(success=True, translated=converted)
    except Exception as exc:
        print("Translation error:", repr(exc))
        return jsonify(
            success=False,
            error="Translation failed. Check your Groq API key and model."
        ), 502


@smart_form_bp.post("/smart-form-assistant/validate")
def smart_form_validate():
    data = request.get_json(silent=True) or {}
    label = str(data.get("label", "Field")).strip()
    value = str(data.get("value", "")).strip()
    kind = str(data.get("type", "text")).lower()
    required = bool(data.get("required"))

    if required and not value:
        return jsonify(valid=False, message=f"{label} is required.")

    if not value:
        return jsonify(valid=True, message="Optional field is empty.")

    if (kind == "email" or "email" in label.lower()):
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            return jsonify(
                valid=False,
                message="Please enter a valid email address."
            )

    if kind in {"number", "range"}:
        try:
            float(value)
        except ValueError:
            return jsonify(valid=False, message="Enter a valid number.")

    if kind == "tel" or re.search(r"phone|mobile|telephone", label, re.I):
        digits = re.sub(r"\D", "", value)
        if not 7 <= len(digits) <= 15:
            return jsonify(valid=False, message="Enter a valid phone number.")

    return jsonify(valid=True, message=f"{label} looks okay.")
