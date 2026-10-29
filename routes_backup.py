from flask import Blueprint, render_template, request, jsonify
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
import re

smart_form_bp = Blueprint(
    "smart_form",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/smart-form-static",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
}

def extract_fields(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a valid URL beginning with http:// or https://.")

    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.find("form")
    scope = form if form else soup
    fields = []

    for el in scope.select("input, textarea, select"):
        tag = el.name.lower()
        kind = (el.get("type") or tag).lower()
        if kind in {"hidden", "submit", "button", "reset", "image", "file"}:
            continue

        field_id = el.get("id", "")
        label_el = soup.find("label", attrs={"for": field_id}) if field_id else None
        parent_label = el.find_parent("label")
        label = (
            label_el.get_text(" ", strip=True) if label_el else
            parent_label.get_text(" ", strip=True) if parent_label else
            el.get("aria-label") or el.get("placeholder") or el.get("name") or field_id
        )
        if not label:
            label = f"Field {len(fields) + 1}"

        options = []
        if tag == "select":
            options = [
                {
                    "value": option.get("value", option.get_text(" ", strip=True)),
                    "text": option.get_text(" ", strip=True)
                }
                for option in el.find_all("option")
            ]

        fields.append({
            "id": field_id or el.get("name") or f"field_{len(fields) + 1}",
            "name": el.get("name", field_id),
            "label": label,
            "type": "textarea" if tag == "textarea" else ("select" if tag == "select" else kind),
            "required": el.has_attr("required"),
            "placeholder": el.get("placeholder", ""),
            "options": options,
        })

    if not fields:
        raise ValueError(
            "No standard HTML fields were found. Some JavaScript-only, login-protected, "
            "or anti-bot-protected forms need browser automation."
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
        return jsonify(success=True, url=url, fields=fields, count=len(fields))
    except requests.exceptions.Timeout:
        return jsonify(success=False, error="The website took too long to respond. Try again."), 400
    except requests.exceptions.RequestException as exc:
        return jsonify(success=False, error=f"Could not open the link: {exc}"), 400
    except Exception as exc:
        return jsonify(success=False, error=str(exc)), 400

@smart_form_bp.post("/smart-form-assistant/validate")
def smart_form_validate():
    data = request.get_json(silent=True) or {}
    label = str(data.get("label", "Field"))
    value = str(data.get("value", "")).strip()
    kind = str(data.get("type", "text")).lower()
    required = bool(data.get("required"))

    if required and not value:
        return jsonify(valid=False, message=f"{label} is required.")
    if kind == "email" and value and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        return jsonify(valid=False, message="Please enter a valid email address.")
    if kind == "number" and value:
        try:
            float(value)
        except ValueError:
            return jsonify(valid=False, message="Please enter a valid number.")
    return jsonify(valid=True, message=f"{label} looks okay.")
