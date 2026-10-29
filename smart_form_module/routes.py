
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    )
}

GROQ_MODEL = "llama-3.3-70b-versatile"


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "Groq API key is missing. Check GROQ_API_KEY in your .env file."
        )

    return Groq(api_key=api_key)


def ask_groq(instructions, text):
    client = get_groq_client()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": instructions,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        temperature=0.1,
    )

    return response.choices[0].message.content.strip()


def extract_fields(url):
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            "Enter a valid URL beginning with http:// or https://."
        )

    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.find("form")
    scope = form if form else soup
    fields = []

    for el in scope.select("input, textarea, select"):
        tag = el.name.lower()
        kind = (el.get("type") or tag).lower()

        if kind in {
            "hidden", "submit", "button", "reset", "image", "file"
        }:
            continue

        field_id = el.get("id", "")
        label_el = (
            soup.find("label", attrs={"for": field_id})
            if field_id
            else None
        )
        parent_label = el.find_parent("label")

        label = (
            label_el.get_text(" ", strip=True)
            if label_el
            else parent_label.get_text(" ", strip=True)
            if parent_label
            else el.get("aria-label")
            or el.get("placeholder")
            or el.get("name")
            or field_id
        )

        if not label:
            label = f"Field {len(fields) + 1}"

        options = []

        if tag == "select":
            options = [
                {
                    "value": option.get(
                        "value", option.get_text(" ", strip=True)
                    ),
                    "text": option.get_text(" ", strip=True),
                }
                for option in el.find_all("option")
            ]

        fields.append(
            {
                "id": field_id or el.get("name") or f"field_{len(fields) + 1}",
                "name": el.get("name", field_id),
                "label": label,
                "type": (
                    "textarea"
                    if tag == "textarea"
                    else "select"
                    if tag == "select"
                    else kind
                ),
                "required": el.has_attr("required"),
                "placeholder": el.get("placeholder", ""),
                "options": options,
            }
        )

    if not fields:
        raise ValueError(
            "No standard HTML fields were found. Some JavaScript-only, "
            "login-protected, or anti-bot-protected forms need browser automation."
        )

    return fields


@smart_form_bp.get("/smart-form-assistant")
def smart_form_home():
    return render_template("smart_form_assistant_fresh.html")


@smart_form_bp.post("/smart-form-assistant/analyze")
def smart_form_analyze():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    try:
        fields = extract_fields(url)
        return jsonify(
            success=True,
            url=url,
            fields=fields,
            count=len(fields),
        )

    except requests.exceptions.Timeout:
        return jsonify(
            success=False,
            error="The website took too long to respond. Try again.",
        ), 400

    except requests.exceptions.RequestException:
        return jsonify(
            success=False,
            error="Could not open the link. Check the URL and try again.",
        ), 400

    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 400

    except Exception:
        return jsonify(
            success=False,
            error="Could not analyze this form. Please check the URL and try again.",
        ), 500


@smart_form_bp.post("/smart-form-assistant/translate")
def smart_form_translate():
    data = request.get_json(silent=True) or {}

    text = str(data.get("text", "")).strip()
    language = str(data.get("language", "English")).strip()
    mode = str(data.get("mode", "question")).strip()

    if not text:
        return jsonify(success=False, error="Text is required."), 400

    if len(text) > 4000:
        return jsonify(
            success=False,
            error="Please translate shorter text.",
        ), 400

    if language.lower() in {"english", "en", "en-in"} and mode == "question":
        return jsonify(success=True, translated=text)

    if mode == "answer":
        instructions = (
            "You are a careful multilingual form-filling assistant. "
            "Translate the user's answer into clear, natural English. "
            "Preserve names, numbers, dates, addresses, and the original meaning. "
            "Do not invent missing information. "
            "Return only the translated answer, without explanations. "
            "If the text is already English, return it unchanged."
        )
        prompt = (
            f"Selected spoken language: {language}\n"
            f"Translate this answer into English:\n{text}"
        )
    else:
        instructions = (
            "You translate form labels and instructions for users. "
            "Translate the provided text into the requested language. "
            "Keep it short, natural, and easy to understand. "
            "Preserve important meaning and do not add new instructions. "
            "Return only the translation."
        )
        prompt = (
            f"Translate this form label or instruction into {language}:\n{text}"
        )

    try:
        translated = ask_groq(instructions, prompt)

        if not translated:
            raise RuntimeError("The translation was empty.")

        return jsonify(success=True, translated=translated)

    except Exception:
        return jsonify(
            success=False,
            error=(
                "Translation failed. Check your Groq API key, internet "
                "connection, and Groq API limits."
            ),
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
        return jsonify(valid=True, message="Optional field left empty.")

    if kind == "email":
        if not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            value,
        ):
            return jsonify(
                valid=False,
                message="Please enter a valid email address.",
            )

    if kind in {"number", "range"}:
        try:
            float(value)
        except ValueError:
            return jsonify(
                valid=False,
                message="Please enter a valid number.",
            )

    if kind == "tel":
        digits = re.sub(r"\D", "", value)

        if len(digits) < 7 or len(digits) > 15:
            return jsonify(
                valid=False,
                message="Please enter a valid phone number.",
            )

    label_lower = label.lower()

    if any(word in label_lower for word in ["email", "e-mail"]):
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            return jsonify(
                valid=False,
                message="Please provide an email address.",
            )

    if any(word in label_lower for word in ["phone", "mobile", "telephone"]):
        digits = re.sub(r"\D", "", value)

        if not 7 <= len(digits) <= 15:
            return jsonify(
                valid=False,
                message="Please provide a valid phone number.",
            )

    return jsonify(valid=True, message=f"{label} looks okay.")
