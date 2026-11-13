
import os
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Blueprint, render_template, request, jsonify
from groq import Groq
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()

smart_form_bp = Blueprint(
    "smart_form",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/smart-form-static"
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "openai/gpt-oss-120b"

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

SUPPORTED_LANGUAGES = {
    "en": "English",
    "english": "English",
    "kn": "Kannada",
    "kannada": "Kannada",
    "hi": "Hindi",
    "hindi": "Hindi"
}

PROTECTED_TYPES = {
    "email", "tel", "number", "range", "date",
    "time", "datetime-local", "month", "week",
    "url", "password", "file"
}


# --------------------------------------------------
# COMMON HELPERS
# --------------------------------------------------

def normalize_language(language):
    key = str(language or "en").strip().lower()
    return SUPPORTED_LANGUAGES.get(key, "English")


def language_code(language):
    name = normalize_language(language)

    return {
        "English": "en",
        "Kannada": "kn",
        "Hindi": "hi"
    }[name]


def valid_http_url(url):
    if not isinstance(url, str):
        return False

    url = url.strip()

    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def ask_groq(prompt):
    if not groq_client:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to your .env file."
        )

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful multilingual assistant. "
                    "Follow the user's instructions carefully. "
                    "Return only the requested text."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
        max_tokens=300
    )

    return response.choices[0].message.content.strip()


def get_json():
    return request.get_json(silent=True) or {}


def api_error(message, status=400):
    return jsonify({
        "success": False,
        "error": message
    }), status


# --------------------------------------------------
# FORM FIELD EXTRACTION
# --------------------------------------------------

def extract_fields(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    fields = []

    elements = soup.select("input, textarea, select")

    for index, element in enumerate(elements):

        field_type = (
            element.get("type", "text").lower()
            if element.name == "input"
            else element.name.lower()
        )

        if field_type in {
            "hidden", "submit", "button", "reset",
            "image", "file"
        }:
            continue

        field_id = element.get("id", "")
        field_name = element.get("name", "")

        label = ""

        if field_id:
            label_element = soup.find(
                "label",
                attrs={"for": field_id}
            )

            if label_element:
                label = label_element.get_text(" ", strip=True)

        if not label:
            parent_label = element.find_parent("label")

            if parent_label:
                label = parent_label.get_text(" ", strip=True)

        if not label:
            label = (
                element.get("aria-label")
                or element.get("placeholder")
                or field_name
                or field_id
                or f"Field {index + 1}"
            )

        options = []

        if element.name == "select":
            for option in element.find_all("option"):
                value = option.get("value", "")
                text = option.get_text(" ", strip=True)

                if text:
                    options.append({
                        "value": value if value else text,
                        "text": text
                    })

        fields.append({
            "id": field_id,
            "name": field_name,
            "label": label,
            "type": field_type,
            "required": element.has_attr("required"),
            "placeholder": element.get("placeholder", ""),
            "options": options
        })

    return fields


# --------------------------------------------------
# MAIN PAGE
# --------------------------------------------------

@smart_form_bp.route("/smart-form-assistant", methods=["GET"])
def smart_form_home():
    return render_template("smart_form_assistant_fresh.html")


# --------------------------------------------------
# ANALYZE FORM
# --------------------------------------------------

@smart_form_bp.route(
    "/smart-form-assistant/analyze",
    methods=["POST"]
)
def analyze_form():

    data = get_json()
    url = str(data.get("url", "")).strip()

    if not valid_http_url(url):
        return api_error("Please enter a valid HTTP or HTTPS form URL.")

    try:
        fields = extract_fields(url)

        if not fields:
            return api_error(
                "No supported form fields were found on this webpage.",
                422
            )

        return jsonify({
            "success": True,
            "url": url,
            "fields": fields,
            "count": len(fields)
        })

    except requests.RequestException as error:
        return api_error(
            f"Unable to open the form URL: {str(error)}",
            502
        )

    except Exception as error:
        return api_error(
            f"Unable to analyze the form: {str(error)}",
            500
        )


# --------------------------------------------------
# TRANSLATE QUESTION OR ANSWER
# --------------------------------------------------

@smart_form_bp.route(
    "/smart-form-assistant/translate",
    methods=["POST"]
)
def translate_text():

    data = get_json()

    text = str(data.get("text", "")).strip()
    language = normalize_language(data.get("language", "en"))
    mode = str(data.get("mode", "question")).lower()
    field_type = str(data.get("fieldType", "text")).lower()
    field_label = str(data.get("fieldLabel", "")).strip()

    if not text:
        return api_error("Text is required.")

    # Do not translate protected values such as email,
    # phone numbers, dates, passwords or URLs.
    if field_type in PROTECTED_TYPES:
        return jsonify({
            "success": True,
            "translated": text
        })

    if language == "English":
        return jsonify({
            "success": True,
            "translated": text
        })

    try:
        if mode == "question":

            prompt = f"""
Translate the following form question into {language}.

Form question: {text}

Instructions:
- Keep the meaning accurate.
- Use simple, natural language.
- Make it easy to understand when spoken aloud.
- Do not add explanations.
- Return only the translated question.
"""

        elif mode == "answer":

            prompt = f"""
The user entered this answer for a form field.

Field label: {field_label}
User answer: {text}

Convert the answer into clear English only if translation is needed.

Instructions:
- Preserve the original meaning.
- Do not add information.
- Do not change numbers, dates, email addresses or phone numbers.
- For a person's name, preserve the name and use English letters.
- Return only the final answer.
"""

        else:
            return api_error("Invalid translation mode.")

        translated = ask_groq(prompt)

        return jsonify({
            "success": True,
            "translated": translated
        })

    except Exception as error:
        return api_error(
            f"Translation failed: {str(error)}",
            502
        )


# --------------------------------------------------
# VALIDATE ANSWER
# --------------------------------------------------

@smart_form_bp.route(
    "/smart-form-assistant/validate",
    methods=["POST"]
)
def validate_answer():

    data = get_json()

    value = str(data.get("value", "")).strip()
    label = str(data.get("label", "Field")).strip()
    field_type = str(data.get("type", "text")).lower()
    required = bool(data.get("required", False))
    language = normalize_language(data.get("language", "en"))

    messages = {
        "English": {
            "required": f"Please enter {label}.",
            "name": "Please enter a valid name, not a phone number or email address.",
            "email": "Please enter a valid email address.",
            "phone": "Please enter a valid phone number.",
            "number": "Please enter a valid number.",
            "valid": "Your answer looks valid."
        },
        "Kannada": {
            "required": f"ದಯವಿಟ್ಟು {label} ನಮೂದಿಸಿ.",
            "name": "ದಯವಿಟ್ಟು ಸರಿಯಾದ ಹೆಸರನ್ನು ನಮೂದಿಸಿ. ಫೋನ್ ಸಂಖ್ಯೆ ಅಥವಾ ಇಮೇಲ್ ನಮೂದಿಸಬೇಡಿ.",
            "email": "ದಯವಿಟ್ಟು ಸರಿಯಾದ ಇಮೇಲ್ ವಿಳಾಸವನ್ನು ನಮೂದಿಸಿ.",
            "phone": "ದಯವಿಟ್ಟು ಸರಿಯಾದ ಫೋನ್ ಸಂಖ್ಯೆಯನ್ನು ನಮೂದಿಸಿ.",
            "number": "ದಯವಿಟ್ಟು ಸರಿಯಾದ ಸಂಖ್ಯೆಯನ್ನು ನಮೂದಿಸಿ.",
            "valid": "ನಿಮ್ಮ ಉತ್ತರ ಸರಿಯಾಗಿದೆ."
        },
        "Hindi": {
            "required": f"कृपया {label} दर्ज करें।",
            "name": "कृपया सही नाम दर्ज करें, फोन नंबर या ईमेल नहीं।",
            "email": "कृपया सही ईमेल पता दर्ज करें।",
            "phone": "कृपया सही फोन नंबर दर्ज करें।",
            "number": "कृपया सही संख्या दर्ज करें।",
            "valid": "आपका उत्तर सही लग रहा है।"
        }
    }

    msg = messages[language]
    error_message = None

    if required and not value:
        error_message = msg["required"]

    elif value and field_type in ("text", "textarea"):

        label_lower = label.lower()

        is_name_field = any(
            word in label_lower
            for word in (
                "name", "first name", "last name",
                "full name", "applicant"
            )
        )

        if is_name_field:
            contains_email = bool(
                re.search(r"[^@\s]+@[^@\s]+\.[^@\s]+", value)
            )

            contains_phone = bool(
                re.fullmatch(r"[\d\s()+-]{7,}", value)
            )

            if contains_email or contains_phone:
                error_message = msg["name"]

    elif value and field_type == "email":

        email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

        if not re.fullmatch(email_pattern, value):
            error_message = msg["email"]

    elif value and field_type == "tel":

        digits = re.sub(r"\D", "", value)

        if len(digits) < 7 or len(digits) > 15:
            error_message = msg["phone"]

    elif value and field_type == "number":

        try:
            float(value)
        except ValueError:
            error_message = msg["number"]

    return jsonify({
        "success": True,
        "valid": error_message is None,
        "message": error_message or msg["valid"],
        "value": value
    })


# --------------------------------------------------
# SUBMIT FORM USING PLAYWRIGHT
# --------------------------------------------------

@smart_form_bp.route(
    "/smart-form-assistant/submit",
    methods=["POST"]
)
def submit_form():

    data = get_json()

    url = str(data.get("url", "")).strip()
    fields = data.get("fields", [])
    answers = data.get("answers", [])

    if not valid_http_url(url):
        return api_error("Invalid form URL.")

    if not isinstance(fields, list) or not isinstance(answers, list):
        return api_error("Invalid form submission data.")

    if len(fields) != len(answers):
        return api_error("The number of answers does not match the fields.")

    try:
        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(headless=True)

            page = browser.new_page()

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            for field, answer in zip(fields, answers):

                field_id = str(field.get("id", "")).strip()
                field_name = str(field.get("name", "")).strip()
                field_type = str(field.get("type", "text")).lower()

                value = "" if answer is None else str(answer)

                locator = None

                if field_id:
                    candidate = page.locator(
                        f"#{field_id}"
                    ).first

                    if candidate.count() > 0:
                        locator = candidate

                if locator is None and field_name:
                    candidate = page.locator(
                        f'[name="{field_name}"]'
                    ).first

                    if candidate.count() > 0:
                        locator = candidate

                if locator is None:
                    continue

                try:
                    if field_type == "select":
                        locator.select_option(value)

                    elif field_type == "checkbox":
                        if value.lower() in ("true", "1", "yes", "on"):
                            locator.check()
                        else:
                            locator.uncheck()

                    elif field_type == "radio":
                        if value.lower() in ("true", "1", "yes", "on"):
                            locator.check()

                    elif field_type not in ("button", "submit", "reset"):
                        locator.fill(value)

                except Exception:
                    # Skip fields that cannot be filled by this
                    # basic HTML form automation.
                    continue

            submit_button = page.locator(
                'button[type="submit"], input[type="submit"]'
            ).first

            if submit_button.count() > 0:
                submit_button.click(timeout=10000)
            else:
                browser.close()
                return api_error(
                    "Could not find a standard submit button on this form.",
                    422
                )

            page.wait_for_timeout(1500)

            final_url = page.url
            browser.close()

        return jsonify({
            "success": True,
            "message": "Form submission process completed.",
            "final_url": final_url
        })

    except PlaywrightTimeoutError:
        return api_error(
            "The form took too long to load or submit.",
            504
        )

    except Exception as error:
        return api_error(
            f"Form submission failed: {str(error)}",
            500
        )
