import os
import re
import threading
from urllib.parse import urlparse

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory
)

from PyPDF2 import PdfReader
from dotenv import load_dotenv

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError
)


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

app = Flask(__name__)
from smart_form_module.routes import smart_form_bp
app.register_blueprint(smart_form_bp)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# GLOBAL BROWSER STATE
# ============================================================

PW = None
BROWSER = None
CONTEXT = None
FORM_PAGE = None

BROWSER_LOCK = threading.RLock()

CURRENT_FORM = {
    "url": "",
    "fields": [],
    "html": "",
    "submitted": False
}


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def readable_name(value):

    value = clean_text(value)

    if not value:
        return ""

    value = re.sub(
        r"[_\-]+",
        " ",
        value
    )

    value = re.sub(
        r"([a-z])([A-Z])",
        r"\1 \2",
        value
    )

    return clean_text(value).title()


# ============================================================
# NAME DETECTION
# ============================================================

def is_name_field(label):

    label = clean_text(label).lower()

    name_words = [
        "name",
        "full name",
        "first name",
        "last name",
        "middle name",
        "surname",
        "applicant name",
        "father name",
        "mother name",
        "guardian name",
        "student name",
        "employee name",
        "candidate name",
        "person name"
    ]

    return any(
        word in label
        for word in name_words
    )


# ============================================================
# QUESTIONS
# ============================================================

def make_question(
    label,
    field_type,
    options=None
):

    label = clean_text(label)

    if not label:
        label = "this field"

    field_type = (
        field_type or "text"
    ).lower()

    if field_type == "email":

        return (
            f"Please enter your {label}."
        )

    if field_type in [
        "number",
        "spinbutton"
    ]:

        return (
            f"Please enter your {label} as a number."
        )

    if field_type in [
        "tel",
        "phone"
    ]:

        return (
            f"Please enter your {label}."
        )

    if field_type == "date":

        return (
            f"Please enter your {label}."
        )

    if field_type == "textarea":

        return (
            f"Please provide your {label}."
        )

    if field_type in [
        "select",
        "radio",
        "checkbox",
        "combobox"
    ]:

        if options:

            names = []

            for option in options:

                text = clean_text(
                    option.get("text", "")
                )

                if text:
                    names.append(text)

            if names:

                return (
                    f"Please select your {label}. "
                    f"Available options are "
                    f"{', '.join(names)}."
                )

        return (
            f"Please select your {label}."
        )

    return (
        f"Please enter your {label}."
    )


# ============================================================
# REQUIREMENT
# ============================================================

def make_requirement(
    label,
    field_type,
    required,
    options=None
):

    label = clean_text(label)

    result = f"Field: {label}"

    if required:
        result += " | Required field."

    field_type = (
        field_type or "text"
    ).lower()

    if field_type == "email":

        result += (
            " | Enter a valid email address."
        )

    elif field_type in [
        "number",
        "spinbutton"
    ]:

        result += (
            " | Enter a numeric value."
        )

    elif field_type in [
        "tel",
        "phone"
    ]:

        result += (
            " | Enter a valid phone number."
        )

    elif field_type == "date":

        result += (
            " | Enter a valid date."
        )

    elif field_type == "url":

        result += (
            " | Enter a valid URL."
        )

    if field_type in [
        "select",
        "radio",
        "checkbox",
        "combobox"
    ]:

        if options:

            names = []

            for option in options:

                text = clean_text(
                    option.get("text", "")
                )

                if text:
                    names.append(text)

            if names:

                result += (
                    " | Options: "
                    + ", ".join(names)
                )

    if is_name_field(label):

        result += (
            " | Enter a name using letters. "
            "Numbers are not accepted."
        )

    return result


# ============================================================
# START BROWSER
# ============================================================

def start_browser():

    global PW
    global BROWSER
    global CONTEXT

    with BROWSER_LOCK:

        if (
            BROWSER is not None
            and CONTEXT is not None
        ):

            try:

                if BROWSER.is_connected():
                    return

            except Exception:
                pass

        print()
        print("=" * 70)
        print("STARTING PLAYWRIGHT")
        print("=" * 70)

        if PW is None:

            PW = sync_playwright().start()

        # ----------------------------------------------------
        # Chromium
        # ----------------------------------------------------

        try:

            BROWSER = PW.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox"
                ]
            )

            print(
                "Chromium started successfully."
            )

        except Exception as chromium_error:

            print(
                "Chromium launch failed:"
            )

            print(
                chromium_error
            )

            # ------------------------------------------------
            # Microsoft Edge fallback
            # ------------------------------------------------

            try:

                BROWSER = PW.chromium.launch(
                    channel="msedge",
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled"
                    ]
                )

                print(
                    "Microsoft Edge started successfully."
                )

            except Exception as edge_error:

                print(
                    "Edge launch failed:"
                )

                print(
                    edge_error
                )

                raise RuntimeError(
                    "Playwright browser could not start. "
                    "Run this command in PowerShell:\n"
                    "python -m playwright install chromium"
                )

        CONTEXT = BROWSER.new_context(
            viewport={
                "width": 1440,
                "height": 1000
            },
            locale="en-US",
            ignore_https_errors=True
        )

        print(
            "Playwright browser ready."
        )

        print("=" * 70)
        print()


# ============================================================
# FIELD EXTRACTION
# ============================================================

def extract_form_with_browser(form_url):

    global FORM_PAGE
    global CURRENT_FORM

    with BROWSER_LOCK:

        start_browser()

        # ----------------------------------------------------
        # Close old page
        # ----------------------------------------------------

        if FORM_PAGE is not None:

            try:
                FORM_PAGE.close()
            except Exception:
                pass

            FORM_PAGE = None

        # ----------------------------------------------------
        # Create new page
        # ----------------------------------------------------

        page = CONTEXT.new_page()

        FORM_PAGE = page

        print()
        print("=" * 70)
        print("OPENING FORM")
        print(form_url)
        print("=" * 70)

        # ----------------------------------------------------
        # Navigate
        # ----------------------------------------------------

        try:

            page.goto(
                form_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

        except PlaywrightTimeoutError:

            print(
                "Page load timeout."
            )

            print(
                "Continuing with the loaded page..."
            )

        except Exception as e:

            raise RuntimeError(
                f"Unable to open the URL: {e}"
            )

        # ----------------------------------------------------
        # Wait for dynamic forms
        # ----------------------------------------------------

        try:

            page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )

        except Exception:
            pass

        page.wait_for_timeout(
            3000
        )

        # ----------------------------------------------------
        # Scroll page to trigger lazy-loaded controls
        # ----------------------------------------------------

        try:

            page.evaluate(
                """
                async () => {
                    const sleep = ms =>
                        new Promise(resolve => setTimeout(resolve, ms));

                    for (
                        let y = 0;
                        y < document.body.scrollHeight;
                        y += 700
                    ) {
                        window.scrollTo(0, y);
                        await sleep(150);
                    }

                    window.scrollTo(0, 0);
                }
                """
            )

            page.wait_for_timeout(
                1500
            )

        except Exception:
            pass

        final_url = page.url

        print(
            "Final URL:",
            final_url
        )

        # ====================================================
        # IMPORTANT:
        # Extract rendered controls using JavaScript.
        #
        # This avoids fragile selectors based on:
        # aria-label
        # name
        # id
        # special characters
        # ====================================================

        raw_fields = page.evaluate(
            """
            () => {

                const clean = value => {
                    if (!value) return "";

                    return String(value)
                        .replace(/\\\\s+/g, " ")
                        .trim();
                };

                const fields = [];

                const controls = Array.from(
                    document.querySelectorAll(
                        "input, textarea, select, " +
                        "[role='textbox'], " +
                        "[role='combobox'], " +
                        "[role='spinbutton'], " +
                        "[role='radio'], " +
                        "[role='checkbox']"
                    )
                );

                const ignored = new Set([
                    "hidden",
                    "submit",
                    "button",
                    "reset",
                    "image",
                    "file"
                ]);

                function textFromElement(el) {

                    const aria =
                        clean(
                            el.getAttribute("aria-label")
                        );

                    const placeholder =
                        clean(
                            el.getAttribute("placeholder")
                        );

                    const name =
                        clean(
                            el.getAttribute("name")
                        );

                    const id =
                        clean(
                            el.getAttribute("id")
                        );

                    if (aria)
                        return aria;

                    if (placeholder)
                        return placeholder;

                    if (name)
                        return name;

                    if (id)
                        return id;

                    return "";
                }

                function findLabel(el) {

                    let label = "";

                    const id =
                        el.getAttribute("id");

                    if (id) {

                        const linked =
                            document.querySelector(
                                "label[for='" +
                                CSS.escape(id) +
                                "']"
                            );

                        if (linked) {

                            label =
                                clean(
                                    linked.innerText
                                );

                            if (label)
                                return label;
                        }
                    }

                    const parentLabel =
                        el.closest("label");

                    if (parentLabel) {

                        label =
                            clean(
                                parentLabel.innerText
                            );

                        if (label)
                            return label;
                    }

                    label =
                        textFromElement(el);

                    if (label)
                        return label;

                    // ----------------------------------------
                    // Search nearby parent containers.
                    // ----------------------------------------

                    let parent =
                        el.parentElement;

                    let depth = 0;

                    while (
                        parent &&
                        depth < 7
                    ) {

                        const text =
                            clean(
                                parent.innerText
                            );

                        if (
                            text &&
                            text.length < 300
                        ) {

                            const lines =
                                text
                                    .split("\\n")
                                    .map(x => clean(x))
                                    .filter(Boolean);

                            if (lines.length) {

                                for (
                                    const line of lines
                                ) {

                                    if (
                                        line.length > 1 &&
                                        line.length < 200
                                    ) {

                                        const low =
                                            line.toLowerCase();

                                        if (
                                            low !==
                                            "required" &&
                                            low !==
                                            "optional"
                                        ) {

                                            return line;
                                        }
                                    }
                                }
                            }
                        }

                        parent =
                            parent.parentElement;

                        depth++;
                    }

                    return "";
                }

                function getOptions(el) {

                    const result = [];

                    if (
                        el.tagName &&
                        el.tagName.toLowerCase()
                        === "select"
                    ) {

                        Array.from(
                            el.options
                        ).forEach(option => {

                            const text =
                                clean(
                                    option.textContent
                                );

                            const value =
                                clean(
                                    option.value
                                );

                            if (text) {

                                result.push({
                                    text: text,
                                    value:
                                        value || text
                                });
                            }
                        });
                    }

                    return result;
                }

                // --------------------------------------------
                // First process normal text/select controls.
                // --------------------------------------------

                controls.forEach(
                    (el, index) => {

                        const tag =
                            (
                                el.tagName || ""
                            ).toLowerCase();

                        const role =
                            (
                                el.getAttribute("role")
                                || ""
                            ).toLowerCase();

                        let type =
                            (
                                el.getAttribute("type")
                                || ""
                            ).toLowerCase();

                        if (
                            tag === "textarea"
                        ) {
                            type = "textarea";
                        }

                        if (
                            role === "textbox"
                        ) {
                            type = "text";
                        }

                        if (
                            role === "spinbutton"
                        ) {
                            type = "number";
                        }

                        if (
                            role === "combobox"
                        ) {
                            type = "select";
                        }

                        if (!type) {
                            type = "text";
                        }

                        if (
                            ignored.has(type)
                        ) {
                            return;
                        }

                        if (
                            type === "radio" ||
                            type === "checkbox"
                        ) {
                            return;
                        }

                        let label =
                            findLabel(el);

                        label =
                            clean(label);

                        if (!label) {
                            label =
                                "Field " +
                                (index + 1);
                        }

                        const required =
                            !!(
                                el.required ||
                                el.getAttribute(
                                    "aria-required"
                                ) === "true"
                            );

                        const options =
                            getOptions(el);

                        fields.push({

                            kind: "control",

                            label: label,

                            type: type,

                            required: required,

                            options: options,

                            index: index,

                            tag: tag,

                            role: role,

                            min:
                                el.getAttribute("min"),

                            max:
                                el.getAttribute("max")
                        });
                    }
                );

                // --------------------------------------------
                // Radio / checkbox groups.
                // --------------------------------------------

                const choices =
                    Array.from(
                        document.querySelectorAll(
                            "[role='radio'], " +
                            "[role='checkbox'], " +
                            "input[type='radio'], " +
                            "input[type='checkbox']"
                        )
                    );

                const groups = [];

                choices.forEach(
                    (choice, index) => {

                        let container =
                            choice.closest(
                                "[role='radiogroup'], " +
                                "[role='group'], " +
                                "[role='listitem']"
                            );

                        if (!container) {

                            container =
                                choice.parentElement;
                        }

                        if (!container)
                            return;

                        let label = "";

                        const aria =
                            clean(
                                choice.getAttribute(
                                    "aria-label"
                                )
                            );

                        const containerText =
                            clean(
                                container.innerText
                            );

                        // ------------------------------------
                        // Try aria-labelledby.
                        // ------------------------------------

                        const labelledBy =
                            choice.getAttribute(
                                "aria-labelledby"
                            );

                        if (labelledBy) {

                            const ids =
                                labelledBy
                                    .split(" ")
                                    .filter(Boolean);

                            const pieces = [];

                            ids.forEach(id => {

                                const node =
                                    document.getElementById(
                                        id
                                    );

                                if (node) {

                                    const t =
                                        clean(
                                            node.innerText
                                        );

                                    if (t)
                                        pieces.push(t);
                                }
                            });

                            label =
                                clean(
                                    pieces.join(" ")
                                );
                        }

                        // ------------------------------------
                        // Use first meaningful line.
                        // ------------------------------------

                        if (!label) {

                            const lines =
                                containerText
                                    .split("\\n")
                                    .map(x => clean(x))
                                    .filter(Boolean);

                            if (lines.length) {

                                label =
                                    lines[0];
                            }
                        }

                        if (!label) {

                            label =
                                aria ||
                                "Choice";
                        }

                        let option =
                            aria;

                        if (!option) {

                            option =
                                clean(
                                    choice.innerText
                                );
                        }

                        if (!option) {

                            option =
                                clean(
                                    choice.getAttribute(
                                        "data-value"
                                    )
                                );
                        }

                        const role =
                            (
                                choice.getAttribute(
                                    "role"
                                )
                                || (
                                    choice.type || ""
                                )
                            ).toLowerCase();

                        let existing =
                            groups.find(
                                g =>
                                    g.label.toLowerCase()
                                    ===
                                    label.toLowerCase()
                            );

                        if (!existing) {

                            existing = {

                                kind: "choice",

                                label: label,

                                type:
                                    role.includes("checkbox")
                                    ? "checkbox"
                                    : "radio",

                                required: false,

                                options: [],

                                choice_index:
                                    groups.length
                            };

                            groups.push(
                                existing
                            );
                        }

                        if (
                            option &&
                            !existing.options.some(
                                x =>
                                    x.text.toLowerCase()
                                    ===
                                    option.toLowerCase()
                            )
                        ) {

                            existing.options.push({
                                text: option,
                                value: option
                            });
                        }
                    }
                );

                groups.forEach(
                    group =>
                        fields.push(group)
                );

                // --------------------------------------------
                // Remove duplicate labels intelligently.
                // --------------------------------------------

                const output = [];

                const seen = new Set();

                fields.forEach(field => {

                    let label =
                        clean(field.label);

                    if (!label)
                        return;

                    // Don't remove separate fields if
                    // they have the same label but different
                    // actual control types.
                    const key =
                        label.toLowerCase()
                        + "|"
                        + field.type;

                    if (
                        seen.has(key)
                    ) {
                        return;
                    }

                    seen.add(key);

                    field.label = label;

                    output.push(field);
                });

                return output;
            }
            """
        )

        print(
            "JavaScript detected:",
            len(raw_fields),
            "possible fields"
        )

        # ====================================================
        # NOW CREATE STABLE IDs IN THE ACTUAL PAGE
        # ====================================================

        fields = []

        for index, raw in enumerate(
            raw_fields,
            start=1
        ):

            label = clean_text(
                raw.get("label", "")
            )

            field_type = (
                raw.get("type", "text")
                or "text"
            ).lower()

            if not label:
                continue

            # Remove obvious navigation controls.

            low = label.lower()

            if low in [
                "search",
                "menu",
                "next",
                "back",
                "submit",
                "send",
                "clear",
                "close",
                "login",
                "sign in"
            ]:
                continue

            field_id = (
                f"field_{len(fields) + 1}"
            )

            # ------------------------------------------------
            # Find the matching control again and mark it
            # with a stable data attribute.
            # ------------------------------------------------

            if raw.get("kind") == "control":

                raw_index = raw.get(
                    "index"
                )

                try:

                    page.evaluate(
                        """
                        ({index, fieldId}) => {

                            const controls =
                                Array.from(
                                    document.querySelectorAll(
                                        "input, textarea, select, " +
                                        "[role='textbox'], " +
                                        "[role='combobox'], " +
                                        "[role='spinbutton']"
                                    )
                                );

                            const el =
                                controls[index];

                            if (el) {

                                el.setAttribute(
                                    "data-ai-field-id",
                                    fieldId
                                );

                                return true;
                            }

                            return false;
                        }
                        """,
                        {
                            "index": raw_index,
                            "fieldId": field_id
                        }
                    )

                except Exception as e:

                    print(
                        "Could not mark field:",
                        label,
                        e
                    )

            # ------------------------------------------------
            # Choice group
            # ------------------------------------------------

            if raw.get("kind") == "choice":

                choice_index = raw.get(
                    "choice_index",
                    -1
                )

                try:

                    page.evaluate(
                        """
                        ({groupIndex, fieldId}) => {

                            const groups =
                                Array.from(
                                    document.querySelectorAll(
                                        "[role='radiogroup'], " +
                                        "[role='group'], " +
                                        "[role='listitem']"
                                    )
                                );

                            let count = -1;

                            for (
                                const group of groups
                            ) {

                                const choices =
                                    group.querySelectorAll(
                                        "[role='radio'], " +
                                        "[role='checkbox'], " +
                                        "input[type='radio'], " +
                                        "input[type='checkbox']"
                                    );

                                if (
                                    choices.length > 0
                                ) {

                                    count++;

                                    if (
                                        count ===
                                        groupIndex
                                    ) {

                                        group.setAttribute(
                                            "data-ai-field-id",
                                            fieldId
                                        );

                                        return true;
                                    }
                                }
                            }

                            return false;
                        }
                        """,
                        {
                            "groupIndex":
                                choice_index,
                            "fieldId":
                                field_id
                        }
                    )

                except Exception:
                    pass

            options = raw.get(
                "options",
                []
            )

            field = {

                "field_id":
                    field_id,

                "id":
                    field_id,

                "selector":
                    f'[data-ai-field-id="{field_id}"]',

                "label":
                    label,

                "name":
                    "",

                "type":
                    field_type,

                "required":
                    bool(
                        raw.get(
                            "required",
                            False
                        )
                    ),

                "options":
                    options,

                "min":
                    raw.get("min"),

                "max":
                    raw.get("max"),

                "question":
                    make_question(
                        label,
                        field_type,
                        options
                    ),

                "requirement":
                    make_requirement(
                        label,
                        field_type,
                        bool(
                            raw.get(
                                "required",
                                False
                            )
                        ),
                        options
                    )
            }

            fields.append(
                field
            )

        # ====================================================
        # SECOND PASS:
        # Google Forms often has questions whose label
        # was not detected properly.
        # ====================================================

        if not fields:

            print(
                "No fields from primary extraction."
            )

            # Try generic form controls one more time.

            fallback_count = page.locator(
                "input:not([type='hidden']), "
                "textarea, "
                "select, "
                "[role='textbox'], "
                "[role='combobox'], "
                "[role='spinbutton']"
            ).count()

            print(
                "Fallback controls:",
                fallback_count
            )

            for i in range(
                fallback_count
            ):

                try:

                    control =page.locator(
                            "input:not([type='hidden']), "
                            "textarea, "
                            "select, "
                            "[role='textbox'], "
                            "[role='combobox'], "
                            "[role='spinbutton']"
                        ).nth(i)

                    label = clean_text(
                        control.get_attribute(
                            "aria-label"
                        )
                        or control.get_attribute(
                            "placeholder"
                        )
                        or control.get_attribute(
                            "name"
                        )
                        or ""
                    )

                    if not label:

                        label = (
                            f"Field {i + 1}"
                        )

                    field_id = (
                        f"field_{len(fields) + 1}"
                    )

                    control.evaluate(
                        """
                        (el, fieldId) => {
                            el.setAttribute(
                                "data-ai-field-id",
                                fieldId
                            );
                        }
                        """,
                        field_id
                    )

                    field_type = (
                        control.get_attribute(
                            "type"
                        )
                        or "text"
                    ).lower()

                    if (
                        control.evaluate(
                            "(el) => el.tagName.toLowerCase()"
                        )
                        == "textarea"
                    ):

                        field_type = "textarea"

                    fields.append({

                        "field_id":
                            field_id,

                        "id":
                            field_id,

                        "selector":
                            f'[data-ai-field-id="{field_id}"]',

                        "label":
                            label,

                        "name":
                            "",

                        "type":
                            field_type,

                        "required":
                            control.get_attribute(
                                "required"
                            )
                            is not None,

                        "options":
                            [],

                        "question":
                            make_question(
                                label,
                                field_type
                            ),

                        "requirement":
                            make_requirement(
                                label,
                                field_type,
                                control.get_attribute(
                                    "required"
                                )
                                is not None
                            )
                    })

                except Exception as e:

                    print(
                        "Fallback extraction error:",
                        e
                    )

        # ====================================================
        # FINAL HTML
        # ====================================================

        html = page.content()

        print()
        print("=" * 70)
        print(
            "FINAL DETECTED FIELD COUNT:",
            len(fields)
        )
        print("=" * 70)

        for index, field in enumerate(
            fields,
            start=1
        ):

            print(
                f"{index}. "
                f"{field['label']} "
                f"| type={field['type']} "
                f"| required={field['required']}"
            )

        print("=" * 70)

        if not fields:

            raise ValueError(
                "The page loaded successfully, but no "
                "fillable fields could be detected. "
                "This usually means the website requires "
                "login, CAPTCHA, a special embedded widget, "
                "or blocks automated browsers."
            )

        CURRENT_FORM = {

            "url":
                final_url,

            "fields":
                fields,

            "html":
                html,

            "action":
                final_url,

            "method":
                "POST",

            "submitted":
                False
        }

        return CURRENT_FORM


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# LEGAL
# ============================================================

@app.route("/legal")
def legal():

    language = request.args.get(
        "language",
        "english"
    )

    return render_template(
        "legal.html",
        language=language
    )


# ============================================================
# PDF UPLOAD
# ============================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    file = request.files.get(
        "document"
    )

    language = request.form.get(
        "language",
        "english"
    )

    if not file or not file.filename:

        return (
            "Please select a document."
        )

    file_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    file.save(
        file_path
    )

    text = ""

    try:

        reader = PdfReader(
            file_path
        )

        for page in reader.pages:

            page_text = (
                page.extract_text()
            )

            if page_text:

                text += page_text

    except Exception as e:

        text = (
            "Unable to extract text "
            f"from this document. Error: {e}"
        )

    explanation = (
        "AI explanation will appear here "
        "when the AI service is available."
    )

    return render_template(
        "result.html",
        text=text,
        explanation=explanation,
        language=language
    )


# ============================================================
# EXISTING SMART FORM
# ============================================================

@app.route(
    "/smart-form",
    methods=["GET", "POST"]
)
def smart_form():

    language = request.args.get(
        "language",
        "english"
    )

    if request.method == "POST":

        return render_template(
            "smart_form_result.html",
            name=request.form.get("name"),
            issue=request.form.get("issue"),
            date=request.form.get("date"),
            location=request.form.get("location"),
            description=request.form.get(
                "description"
            ),
            language=request.form.get(
                "language",
                language
            )
        )

    return render_template(
        "smart_form.html",
        language=language
    )


# ============================================================
# SMART FORM UPLOAD
# ============================================================

@app.route(
    "/smart-form-upload",
    methods=["POST"]
)
def smart_form_upload():

    file = request.files.get(
        "form_file"
    )

    language = request.form.get(
        "language",
        "english"
    )

    if not file or not file.filename:

        return (
            "Please select a form to upload."
        )

    file_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    file.save(
        file_path
    )

    return render_template(
        "smart_form_upload.html",
        filename=file.filename,
        language=language
    )


# ============================================================
# MANUAL FORM
# ============================================================

@app.route(
    "/smart-form-manual/<filename>"
)
def smart_form_manual(filename):

    language = request.args.get(
        "language",
        "english"
    )

    return render_template(
        "smart_form_manual.html",
        filename=filename,
        language=language
    )


# ============================================================
# UPLOADED FILE
# ============================================================

@app.route(
    "/uploads/<path:filename>"
)
def uploaded_file(filename):

    return send_from_directory(
        UPLOAD_FOLDER,
        filename
    )


# ============================================================
# OPEN FORM
# ============================================================

@app.route(
    "/open-form",
    methods=["POST"]
)
def open_form():

    form_url = clean_text(
        request.form.get(
            "form_url",
            ""
        )
    )

    language = request.form.get(
        "language",
        "english"
    )

    if not form_url:

        return jsonify(
            success=False,
            error="Please enter a form link."
        ), 400

    parsed = urlparse(
        form_url
    )

    if parsed.scheme not in [
        "http",
        "https"
    ]:

        return jsonify(
            success=False,
            error=(
                "Please enter a valid HTTP or "
                "HTTPS form link."
            )
        ), 400

    try:

        result = extract_form_with_browser(
            form_url
        )

        return render_template(
            "smart_assistant.html",
            form_url=result["url"],
            language=language,
            fields=result["fields"]
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("FORM EXTRACTION ERROR")
        print(str(e))
        print("=" * 70)
        print()

        return jsonify(
            success=False,
            error=str(e)
        ), 400


# ============================================================
# ANALYZE FORM
# ============================================================

@app.route(
    "/analyze-form",
    methods=["POST"]
)
def analyze_form():

    data = request.get_json(
        silent=True
    ) or {}

    form_url = clean_text(
        data.get(
            "form_url",
            data.get(
                "url",
                ""
            )
        )
    )

    if not form_url:

        return jsonify(
            success=False,
            message="Form URL is required."
        ), 400

    parsed = urlparse(
        form_url
    )

    if parsed.scheme not in [
        "http",
        "https"
    ]:

        return jsonify(
            success=False,
            message="Only HTTP and HTTPS URLs are supported."
        ), 400

    try:

        result = extract_form_with_browser(
            form_url
        )

        return jsonify(
            success=True,
            form_url=form_url,
            url=result["url"],
            fields=result["fields"],
            field_count=len(
                result["fields"]
            )
        )

    except Exception as e:

        print(
            "ANALYZE ERROR:",
            str(e)
        )

        return jsonify(
            success=False,
            message=str(e)
        ), 400


# ============================================================
# VALIDATION
# ============================================================

def validate_answer_internal(
    field,
    value
):

    value = clean_text(
        value
    )

    label = clean_text(
        field.get(
            "label",
            ""
        )
    )

    field_type = (
        str(
            field.get(
                "type",
                "text"
            )
        )
        .lower()
    )

    required = bool(
        field.get(
            "required",
            False
        )
    )

    label_lower = label.lower()

    # --------------------------------------------------------
    # EMPTY
    # --------------------------------------------------------

    if not value:

        if required:

            return {
                "valid": False,
                "message": (
                    f"{label} is required. "
                    "Please fill it in."
                )
            }

        return {
            "valid": False,
            "message": (
                f"Please provide your {label}."
            )
        }

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    if is_name_field(label):

        if not re.fullmatch(
            r"[A-Za-zÀ-ÿ.'\- ]+",
            value
        ):

            return {
                "valid": False,
                "message": (
                    f'"{value}" is not a valid {label}. '
                    "Numbers and invalid symbols are not "
                    "accepted for a name. "
                    "Please enter the name using letters only."
                )
            }

        if not re.search(
            r"[A-Za-zÀ-ÿ]",
            value
        ):

            return {
                "valid": False,
                "message": (
                    f'"{value}" is not a valid name. '
                    "Please enter the name using letters."
                )
            }

        return {
            "valid": True,
            "message": (
                f"The {label} is valid."
            )
        }

    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

    if (
        field_type == "email"
        or "email" in label_lower
    ):

        pattern = (
            r"^[A-Za-z0-9._%+-]+@"
            r"[A-Za-z0-9.-]+\."
            r"[A-Za-z]{2,}$"
        )

        if not re.fullmatch(
            pattern,
            value
        ):

            return {
                "valid": False,
                "message": (
                    "That is not a valid email address. "
                    "Please enter the email again."
                )
            }

    # --------------------------------------------------------
    # PHONE
    # --------------------------------------------------------

    if (
        field_type in [
            "tel",
            "phone"
        ]
        or any(
            word in label_lower
            for word in [
                "phone",
                "mobile",
                "telephone",
                "contact number"
            ]
        )
    ):

        digits = re.sub(
            r"\D",
            "",
            value
        )

        if not 7 <= len(digits) <= 15:

            return {
                "valid": False,
                "message": (
                    "That does not look like a valid "
                    "phone number. Please enter it again."
                )
            }

    # --------------------------------------------------------
    # NUMBER
    # --------------------------------------------------------

    if (
        field_type in [
            "number",
            "spinbutton"
        ]
        or "age" in label_lower
        or label_lower in [
            "number",
            "quantity"
        ]
    ):

        try:

            number = float(
                value
            )

        except ValueError:

            return {
                "valid": False,
                "message": (
                    f"The {label} requires a number. "
                    "Please enter numbers only."
                )
            }

        minimum = field.get(
            "min"
        )

        maximum = field.get(
            "max"
        )

        if minimum not in [
            None,
            ""
        ]:

            try:

                if number < float(
                    minimum
                ):

                    return {
                        "valid": False,
                        "message": (
                            f"The value must be "
                            f"at least {minimum}."
                        )
                    }

            except Exception:
                pass

        if maximum not in [
            None,
            ""
        ]:

            try:

                if number > float(
                    maximum
                ):

                    return {
                        "valid": False,
                        "message": (
                            f"The value must not be "
                            f"greater than {maximum}."
                        )
                    }

            except Exception:
                pass

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    if field_type == "url":

        if not re.match(
            r"^https?://",
            value,
            re.IGNORECASE
        ):

            return {
                "valid": False,
                "message": (
                    "Please enter a valid URL beginning "
                    "with http:// or https://."
                )
            }

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if field_type == "date":

        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}",
            value
        ):

            return {
                "valid": False,
                "message": (
                    "Please enter a valid date."
                )
            }

    # --------------------------------------------------------
    # OPTIONS
    # --------------------------------------------------------

    if field_type in [
        "select",
        "radio",
        "checkbox",
        "combobox"
    ]:

        options = field.get(
            "options",
            []
        )

        if options:

            allowed = []

            for option in options:

                allowed.append(
                    clean_text(
                        option.get(
                            "text",
                            ""
                        )
                    ).lower()
                )

                allowed.append(
                    clean_text(
                        option.get(
                            "value",
                            ""
                        )
                    ).lower()
                )

            if value.lower() not in allowed:

                return {
                    "valid": False,
                    "message": (
                        "Please choose one of the "
                        "available options."
                    )
                }

    return {
        "valid": True,
        "message": (
            f"The answer for {label} is valid."
        )
    }


# ============================================================
# VALIDATE ANSWER API
# ============================================================

@app.route(
    "/validate-answer",
    methods=["POST"]
)
def validate_answer():

    data = request.get_json(
        silent=True
    ) or {}

    field = data.get(
        "field",
        {}
    )

    value = clean_text(
        data.get(
            "value",
            ""
        )
    )

    if not field:

        return jsonify(
            valid=False,
            message="Field information is missing."
        ), 400

    result = validate_answer_internal(
        field,
        value
    )

    return jsonify(
        valid=result["valid"],
        message=result["message"]
    )


# ============================================================
# FILL REMOTE FIELD
# ============================================================

def fill_remote_field(
    field,
    value
):

    global FORM_PAGE

    if FORM_PAGE is None:

        raise RuntimeError(
            "No remote form is currently loaded."
        )

    page = FORM_PAGE

    field_id = field.get(
        "field_id",
        ""
    )

    field_type = (
        field.get(
            "type",
            "text"
        )
        .lower()
    )

    label = clean_text(
        field.get(
            "label",
            ""
        )
    )

    # ========================================================
    # STABLE AI FIELD ID
    # ========================================================

    if field_id:

        locator = page.locator(
            f'[data-ai-field-id="{field_id}"]'
        ).first

        if locator.count():

            # -----------------------------------------------
            # Select
            # -----------------------------------------------

            if field_type in [
                "select",
                "combobox"
            ]:

                try:

                    locator.select_option(
                        label=str(value)
                    )

                    return True

                except Exception:

                    try:

                        locator.select_option(
                            str(value)
                        )

                        return True

                    except Exception:
                        pass

            # -----------------------------------------------
            # Radio / checkbox
            # -----------------------------------------------

            if field_type in [
                "radio",
                "checkbox"
            ]:

                options = field.get(
                    "options",
                    []
                )

                wanted = clean_text(
                    value
                ).lower()

                # Search the group.

                choices = locator.locator(
                    "[role='radio'], "
                    "[role='checkbox'], "
                    "input[type='radio'], "
                    "input[type='checkbox']"
                )

                for i in range(
                    choices.count()
                ):

                    choice = choices.nth(i)

                    aria = clean_text(
                        choice.get_attribute(
                            "aria-label"
                        )
                        or ""
                    )

                    text = clean_text(
                        choice.inner_text()
                    )

                    choice_value = clean_text(
                        choice.get_attribute(
                            "value"
                        )
                        or ""
                    )

                    combined = (
                        aria
                        or text
                        or choice_value
                    ).lower()

                    if (
                        combined == wanted
                        or wanted in combined
                    ):

                        choice.click()

                        return True

                # Try visible text.

                for option in options:

                    option_text = clean_text(
                        option.get(
                            "text",
                            ""
                        )
                    )

                    if (
                        option_text.lower()
                        == wanted
                    ):

                        visible = locator.get_by_text(
                            option_text,
                            exact=True
                        )

                        if visible.count():

                            visible.first.click()

                            return True

            # -----------------------------------------------
            # Normal input
            # -----------------------------------------------

            try:

                locator.scroll_into_view_if_needed()

            except Exception:
                pass

            try:

                locator.fill(
                    str(value)
                )

                # Trigger normal browser events.

                locator.dispatch_event(
                    "input"
                )

                locator.dispatch_event(
                    "change"
                )

                return True

            except Exception as e:

                print(
                    "Stable field fill failed:",
                    e
                )

    # ========================================================
    # ARIA LABEL FALLBACK
    # ========================================================

    try:

        if label:

            locator = page.get_by_label(
                label,
                exact=True
            ).first

            if locator.count():

                locator.fill(
                    str(value)
                )

                return True

    except Exception:
        pass

    # ========================================================
    # TEXT MATCH FALLBACK
    # ========================================================

    try:

        candidates = page.locator(
            "input, textarea, select, "
            "[role='textbox'], "
            "[role='combobox'], "
            "[role='spinbutton']"
        )

        for i in range(
            candidates.count()
        ):

            control = candidates.nth(i)

            aria = clean_text(
                control.get_attribute(
                    "aria-label"
                )
                or ""
            )

            placeholder = clean_text(
                control.get_attribute(
                    "placeholder"
                )
                or ""
            )

            name = clean_text(
                control.get_attribute(
                    "name"
                )
                or ""
            )

            combined = (
                f"{aria} "
                f"{placeholder} "
                f"{name}"
            ).lower()

            if (
                label.lower()
                in combined
            ):

                control.fill(
                    str(value)
                )

                return True

    except Exception:
        pass

    raise RuntimeError(
        f"Unable to locate the form field: {label}"
    )


# ============================================================
# FILL ANSWER API
# ============================================================

@app.route(
    "/fill-answer",
    methods=["POST"]
)
def fill_answer():

    data = request.get_json(
        silent=True
    ) or {}

    field = data.get(
        "field",
        {}
    )

    value = clean_text(
        data.get(
            "value",
            ""
        )
    )

    if not field:

        return jsonify(
            success=False,
            valid=False,
            message="Field information is missing."
        ), 400

    # ========================================================
    # VALIDATE BEFORE FILLING
    # ========================================================

    validation = validate_answer_internal(
        field,
        value
    )

    if not validation["valid"]:

        return jsonify(
            success=False,
            valid=False,
            message=validation["message"]
        ), 400

    # ========================================================
    # FILL
    # ========================================================

    try:

        fill_remote_field(
            field,
            value
        )

        return jsonify(
            success=True,
            valid=True,
            message=(
                f"{field.get('label', 'Field')} "
                "has been filled successfully."
            )
        )

    except Exception as e:

        print(
            "FILL ERROR:",
            e
        )

        return jsonify(
            success=False,
            valid=True,
            message=str(e)
        ), 400


# ============================================================
# SUBMIT FORM
# ============================================================

@app.route(
    "/submit-form",
    methods=["POST"]
)
def submit_form():

    global FORM_PAGE
    global CURRENT_FORM

    if FORM_PAGE is None:

        return jsonify(
            success=False,
            message="No form is currently loaded."
        ), 400

    page = FORM_PAGE

    with BROWSER_LOCK:

        try:

            print()
            print("=" * 70)
            print("SUBMITTING FORM")
            print("=" * 70)

            # =================================================
            # GOOGLE / CUSTOM BUTTONS
            # =================================================

            buttons = page.locator(
                "button, "
                "[role='button'], "
                "input[type='submit']"
            )

            for i in range(
                buttons.count()
            ):

                try:

                    button = buttons.nth(i)

                    if not button.is_visible():
                        continue

                    text = clean_text(
                        button.inner_text()
                    )

                    value = clean_text(
                        button.get_attribute(
                            "value"
                        )
                        or ""
                    )

                    aria = clean_text(
                        button.get_attribute(
                            "aria-label"
                        )
                        or ""
                    )

                    combined = (
                        f"{text} "
                        f"{value} "
                        f"{aria}"
                    ).lower()

                    if any(
                        word in combined
                        for word in [
                            "submit",
                            "send",
                            "apply",
                            "register",
                            "finish",
                            "save"
                        ]
                    ):

                        button.scroll_into_view_if_needed()

                        button.click(
                            timeout=10000
                        )

                        page.wait_for_timeout(
                            2500
                        )

                        CURRENT_FORM[
                            "submitted"
                        ] = True

                        print(
                            "Form submitted."
                        )

                        return jsonify(
                            success=True,
                            message=(
                                "The form was submitted successfully."
                            ),
                            url=page.url
                        )

                except Exception as e:

                    print(
                        "Button attempt failed:",
                        e
                    )

            # =================================================
            # NORMAL FORM
            # =================================================

            forms = page.locator(
                "form"
            )

            if forms.count():

                result = page.evaluate(
                    """
                    () => {

                        const forms =
                            Array.from(
                                document.forms
                            );

                        if (!forms.length)
                            return false;

                        const form =
                            forms[0];

                        if (
                            typeof form.requestSubmit
                            === "function"
                        ) {

                            form.requestSubmit();

                        } else {

                            form.submit();
                        }

                        return true;
                    }
                    """
                )

                if result:

                    page.wait_for_timeout(
                        2500
                    )

                    CURRENT_FORM[
                        "submitted"
                    ] = True

                    return jsonify(
                        success=True,
                        message=(
                            "The form was submitted successfully."
                        ),
                        url=page.url
                    )

            return jsonify(
                success=False,
                message=(
                    "The form was filled, but the website "
                    "does not expose a recognizable submit "
                    "button or HTML form."
                )
            ), 400

        except Exception as e:

            print(
                "SUBMIT ERROR:",
                e
            )

            return jsonify(
                success=False,
                message=str(e)
            ), 400


# ============================================================
# DOWNLOAD / FILL ALL
# ============================================================

@app.route(
    "/download-form",
    methods=["POST"]
)
def download_form():

    data = request.get_json(
        silent=True
    ) or {}

    answers = data.get(
        "answers",
        {}
    )

    if not CURRENT_FORM:

        return jsonify(
            success=False,
            message="No form is loaded."
        ), 400

    for field in CURRENT_FORM.get(
        "fields",
        []
    ):

        field_id = field.get(
            "field_id",
            ""
        )

        value = answers.get(
            field_id,
            ""
        )

        if not clean_text(value):
            continue

        validation = validate_answer_internal(
            field,
            str(value)
        )

        if not validation["valid"]:

            return jsonify(
                success=False,
                message=validation["message"]
            ), 400

        try:

            fill_remote_field(
                field,
                str(value)
            )

        except Exception as e:

            return jsonify(
                success=False,
                message=str(e)
            ), 400

    try:

        html = FORM_PAGE.content()

    except Exception:

        html = CURRENT_FORM.get(
            "html",
            ""
        )

    return jsonify(
        success=True,
        html=html,
        message=(
            "All valid answers have been filled."
        )
    )


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/health"
)
def health():

    connected = False

    try:

        connected = (
            BROWSER is not None
            and BROWSER.is_connected()
        )

    except Exception:
        connected = False

    return jsonify(
        status="running",
        browser=connected,
        form_loaded=(
            FORM_PAGE is not None
        ),
        fields=len(
            CURRENT_FORM.get(
                "fields",
                []
            )
        ),
        url=CURRENT_FORM.get(
            "url",
            ""
        )
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("AI LEGAL ASSISTANT")
    print("=" * 70)
    print(
        "Open: http://127.0.0.1:5000"
    )
    print()
    print(
        "SMART FORM:"
    )
    print(
        "URL -> Playwright -> Rendered Form"
    )
    print(
        "-> Detect Fields -> AI Voice"
    )
    print(
        "-> Validate -> Fill -> Submit"
    )
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # Start browser before Flask.
    # --------------------------------------------------------

    try:

        start_browser()

    except Exception as e:

        print()
        print(
            "WARNING: Browser startup failed."
        )

        print(
            str(e)
        )

        print()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )