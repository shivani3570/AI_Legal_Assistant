// ============================================
// SMART FORM ASSISTANT - PART 1
// ============================================

const sf = id => document.getElementById("sf" + id);

const sfWords = {
    en: {
        required: "This field is required.",
        read: "Please answer: ",
        correct: "Is this correct?",
        finish: "Your answers have been reviewed. This version does not submit data to the original website.",
        unsupported: "Speech recognition is unavailable. Please type your answer.",
        listening: "Listening. Please speak now.",
        nameError: "Please enter a valid name, not a phone number.",
        emailError: "Please enter a valid email address.",
        phoneError: "Please enter a valid phone number.",
        numberError: "Please enter a valid number.",
        answerCaptured: "Answer captured. Click Check answer.",
        optional: "Optional field",
        select: "Select an option",
        translateError: "Translation failed. Check your Groq connection and try again.",
        addressError: "Please enter a valid address, not just a phone number.",
        translating: "Translating your answer..."
    },

    kn: {
        required: "ಈ ಮಾಹಿತಿ ಅಗತ್ಯವಿದೆ.",
        read: "ದಯವಿಟ್ಟು ಉತ್ತರಿಸಿ: ",
        correct: "ನೀವು ನೀಡಿದ ಉತ್ತರ ಸರಿಯಾಗಿದೆಯೇ?",
        finish: "ನಿಮ್ಮ ಉತ್ತರಗಳನ್ನು ಪರಿಶೀಲಿಸಲಾಗಿದೆ. ಈ ಆವೃತ್ತಿಯು ಮೂಲ ವೆಬ್‌ಸೈಟ್‌ಗೆ ಮಾಹಿತಿಯನ್ನು ಸಲ್ಲಿಸುವುದಿಲ್ಲ.",
        unsupported: "ಧ್ವನಿ ಗುರುತಿಸುವಿಕೆ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಉತ್ತರವನ್ನು ಟೈಪ್ ಮಾಡಿ.",
        listening: "ಕೇಳುತ್ತಿದ್ದೇನೆ. ಈಗ ಮಾತನಾಡಿ.",
        nameError: "ದಯವಿಟ್ಟು ಸರಿಯಾದ ಹೆಸರನ್ನು ನಮೂದಿಸಿ.",
        emailError: "ದಯವಿಟ್ಟು ಸರಿಯಾದ ಇಮೇಲ್ ವಿಳಾಸವನ್ನು ನಮೂದಿಸಿ.",
        phoneError: "ದಯವಿಟ್ಟು ಸರಿಯಾದ ಫೋನ್ ಸಂಖ್ಯೆಯನ್ನು ನಮೂದಿಸಿ.",
        numberError: "ದಯವಿಟ್ಟು ಸರಿಯಾದ ಸಂಖ್ಯೆಯನ್ನು ನಮೂದಿಸಿ.",
        answerCaptured: "ಉತ್ತರವನ್ನು ದಾಖಲಿಸಲಾಗಿದೆ. ಉತ್ತರ ಪರಿಶೀಲಿಸಿ ಬಟನ್ ಒತ್ತಿ.",
        optional: "ಐಚ್ಛಿಕ ಮಾಹಿತಿ",
        select: "ಒಂದು ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿ",
        translateError: "ಅನುವಾದಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. Groq ಸಂಪರ್ಕವನ್ನು ಪರಿಶೀಲಿಸಿ.",
        addressError: "ದಯವಿಟ್ಟು ಫೋನ್ ಸಂಖ್ಯೆಯ ಬದಲು ಸರಿಯಾದ ವಿಳಾಸವನ್ನು ನಮೂದಿಸಿ.",
        translating: "ನಿಮ್ಮ ಉತ್ತರವನ್ನು ಅನುವಾದಿಸಲಾಗುತ್ತಿದೆ..."
    },

    hi: {
        required: "यह जानकारी आवश्यक है।",
        read: "कृपया उत्तर दें: ",
        correct: "क्या आपका उत्तर सही है?",
        finish: "आपके उत्तर जाँच लिए गए हैं। यह संस्करण मूल वेबसाइट पर जानकारी जमा नहीं करता।",
        unsupported: "आवाज़ पहचान उपलब्ध नहीं है। कृपया उत्तर टाइप करें।",
        listening: "सुन रहा है। अब बोलें।",
        nameError: "कृपया सही नाम दर्ज करें।",
        emailError: "कृपया सही ईमेल पता दर्ज करें।",
        phoneError: "कृपया सही फोन नंबर दर्ज करें।",
        numberError: "कृपया सही संख्या दर्ज करें।",
        answerCaptured: "उत्तर दर्ज हो गया। उत्तर जाँचें बटन दबाएँ।",
        optional: "वैकल्पिक जानकारी",
        select: "एक विकल्प चुनें",
        translateError: "अनुवाद नहीं हो सका। Groq कनेक्शन जाँचें।",
        addressError: "कृपया फोन नंबर की जगह सही पता दर्ज करें।",
        translating: "आपके उत्तर का अनुवाद हो रहा है..."
    }
};

const sfLang = () => sf("Language")?.value || "en";

const sfText = key =>
    (sfWords[sfLang()] || sfWords.en)[key] || sfWords.en[key] || key;

const sfLocale = () => ({
    en: "en-IN",
    kn: "kn-IN",
    hi: "hi-IN"
}[sfLang()] || "en-IN");

let sfFields = [];
let sfAnswers = [];
let sfIndex = 0;
let sfRecognition = null;
let sfDisplayLabels = [];
let sfTranslationCache = new Map();

// Call the Groq translation route in routes.py.
async function sfTranslate(text, mode = "question") {
    if (!text) return text;

    if (sfLang() === "en") return text;

    const cacheKey = `${sfLang()}|${mode}|${text}`;

    if (sfTranslationCache.has(cacheKey)) {
        return sfTranslationCache.get(cacheKey);
    }

    const response = await fetch(
        "/smart-form-assistant/translate",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                text: text,
                language: ({
                    en: "English",
                    kn: "Kannada",
                    hi: "Hindi"
                }[sfLang()] || "English"),
                mode: mode
            })
        }
    );

    const data = await response.json();

    if (!response.ok || !data.success || !data.translated) {
        throw new Error(data.error || sfText("translateError"));
    }

    sfTranslationCache.set(cacheKey, data.translated);

    return data.translated;
}

// Correct common spoken email phrases.
function sfNormalizeSpokenAnswer(text, field) {
    let value = String(text || "").trim();

    const fieldInfo =
        `${field.label || ""} ${field.name || ""} ${field.type || ""}`
        .toLowerCase();

    const emailField =
        field.type === "email" ||
        /email|e-mail|ಇಮೇಲ್|ईमेल/.test(fieldInfo);

    if (emailField) {
        value = value
            .replace(/\s+at the rate\s+/gi, "@")
            .replace(/\s+at\s+/gi, "@")
            .replace(/\s+dot\s+/gi, ".")
            .replace(/\s+underscore\s+/gi, "_")
            .replace(/\s+dash\s+/gi, "-")
            .replace(/\s+hyphen\s+/gi, "-")
            .replace(/\s+plus\s+/gi, "+")
            .replace(/\s+/g, "");
    }

    return value;
}

function sfSpeak(text) {
    if (!("speechSynthesis" in window)) return;

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(String(text));
    utterance.lang = sfLocale();
    utterance.rate = 0.9;

    const voices = window.speechSynthesis.getVoices();

    const voice = voices.find(item =>
        item.lang.toLowerCase() === sfLocale().toLowerCase()
    ) || voices.find(item =>
        item.lang.toLowerCase().startsWith(sfLang())
    );

    if (voice) utterance.voice = voice;

    window.speechSynthesis.speak(utterance);
}

function sfMessage(text, ok = false) {
    sf("FieldMessage").textContent = text;

    sf("FieldMessage").className =
        "sf-message " + (ok ? "sf-success" : "sf-error");

    sf("FieldMessage").classList.remove("sf-hidden");
}

function sfStopListening() {
    if (sfRecognition) {
        try {
            sfRecognition.stop();
        } catch (error) {
            // Speech recognition may already have stopped.
        }

        sfRecognition = null;
    }
}

sf("DemoButton").onclick = () => {
    sf("FormUrl").value =
        "http://127.0.0.1:8000/demo_test_form.html";
};

sf("LoadForm").onsubmit = async event => {
    event.preventDefault();

    sf("LoadError").classList.add("sf-hidden");
    sf("LoadButton").disabled = true;
    sf("LoadButton").textContent = "Loading...";

    try {
        const response = await fetch(
            "/smart-form-assistant/analyze",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    url: sf("FormUrl").value.trim()
                })
            }
        );

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(
                data.error || "Could not detect form fields."
            );
        }

        sfFields = data.fields;
        sfAnswers = sfFields.map(() => "");
        sfDisplayLabels = sfFields.map(field => field.label);
        sfTranslationCache.clear();
        sfIndex = 0;

        if (!sfFields.length) {
            throw new Error("No form fields were detected.");
        }

        sf("Assistant").classList.remove("sf-hidden");

        sf("Summary").textContent =
            `${data.count} fields detected from ${data.url}`;

        await sfRender();

        sf("Assistant").scrollIntoView({
            behavior: "smooth"
        });

    } catch (error) {
        sf("LoadError").textContent = error.message;
        sf("LoadError").classList.remove("sf-hidden");

    } finally {
        sf("LoadButton").disabled = false;
        sf("LoadButton").textContent = "Load Form";
    }
};

sf("ChangeForm").onclick = () => {
    sfStopListening();
    sf("Assistant").classList.add("sf-hidden");

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
};
// ============================================
// FIELD DISPLAY, TRANSLATION AND VOICE INPUT
// ============================================

async function sfRender() {
    const field = sfFields[sfIndex];
    if (!field) return;

    sfStopListening();

    sf("QuestionCard").classList.remove("sf-hidden");
    sf("Review").classList.add("sf-hidden");
    sf("ConfirmBox").classList.add("sf-hidden");
    sf("FieldMessage").classList.add("sf-hidden");

    const questionLabel = sf("QuestionLabel");
    const originalLabel = field.label || "Field";

    questionLabel.textContent =
        originalLabel + (field.required ? " *" : "");

    sf("QuestionHelp").textContent =
        field.required ? sfText("required") : sfText("optional");

    if (sfLang() !== "en") {
        questionLabel.textContent = "ಅನುವಾದಿಸಲಾಗುತ್ತಿದೆ...";

        try {
            const translatedLabel =
                await sfTranslate(originalLabel, "question");

            sfDisplayLabels[sfIndex] = translatedLabel;

            questionLabel.textContent =
                translatedLabel + (field.required ? " *" : "");

        } catch (error) {
            sfDisplayLabels[sfIndex] = originalLabel;

            questionLabel.textContent =
                originalLabel + (field.required ? " *" : "");

            sfMessage(sfText("translateError"));
        }
    } else {
        sfDisplayLabels[sfIndex] = originalLabel;
    }

    sf("ProgressText").textContent =
        `Field ${sfIndex + 1} of ${sfFields.length}`;

    const progress = Math.round(
        ((sfIndex + 1) / sfFields.length) * 100
    );

    sf("ProgressPercent").textContent = progress + "%";
    sf("ProgressBar").style.width = progress + "%";
    sf("Back").disabled = sfIndex === 0;
    sf("VoiceStatus").textContent = "";

    const area = sf("AnswerArea");
    area.innerHTML = "";

    let element;

    if (field.type === "select" && field.options?.length) {
        element = document.createElement("select");
        element.add(new Option(sfText("select"), ""));

        field.options.forEach(option => {
            element.add(new Option(option.text, option.value));
        });

    } else if (field.type === "textarea") {
        element = document.createElement("textarea");
        element.rows = 3;

    } else {
        element = document.createElement("input");

        const allowedTypes = [
            "email", "number", "date", "tel", "url"
        ];

        element.type = allowedTypes.includes(field.type)
            ? field.type
            : "text";
    }

    element.id = "sfAnswer";
    element.value = sfAnswers[sfIndex] || "";
    element.placeholder = field.placeholder || "Enter your answer";
    element.required = field.required;

    area.appendChild(element);
}

sf("ReadQuestion").onclick = async () => {
    const field = sfFields[sfIndex];
    if (!field) return;

    try {
        let label = field.label || "Field";

        if (sfLang() !== "en") {
            label = await sfTranslate(label, "question");
        }

        sfDisplayLabels[sfIndex] = label;
        sfSpeak(sfText("read") + label);

    } catch (error) {
        sfMessage(sfText("translateError"));
    }
};

sf("SpeakAnswer").onclick = () => {
    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        sf("VoiceStatus").textContent = sfText("unsupported");
        return;
    }

    sfStopListening();

    const recognition = new SpeechRecognition();
    sfRecognition = recognition;

    recognition.lang = sfLocale();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
        sf("VoiceStatus").textContent = sfText("listening");
    };

    recognition.onresult = event => {
        const field = sfFields[sfIndex];

        const spokenAnswer = sfNormalizeSpokenAnswer(
            event.results[0][0].transcript,
            field
        );

        sf("Answer").value = spokenAnswer;
        sfAnswers[sfIndex] = spokenAnswer;

        sf("VoiceStatus").textContent = sfText("answerCaptured");

        // Read back the captured answer.
        sfSpeak(spokenAnswer);
    };

    recognition.onerror = () => {
        sf("VoiceStatus").textContent = sfText("unsupported");
    };

    recognition.onend = () => {
        sfRecognition = null;
    };

    try {
        recognition.start();
    } catch (error) {
        sf("VoiceStatus").textContent = sfText("unsupported");
    }
};


// ============================================
// ANSWER VALIDATION
// ============================================

function sfValidateAnswer(field, value) {
    if (!value && field.required) {
        return sfText("required");
    }

    if (!value) return "";

    const label =
        `${field.label || ""} ${field.name || ""} ${field.type || ""}`
        .toLowerCase();

    const type = (field.type || "text").toLowerCase();

    const isNameField =
        /name|ಹೆಸರು|नाम/.test(label);

    const isPhoneField =
        type === "tel" ||
        /phone|mobile|telephone|ಫೋನ್|ಮೊಬೈಲ್|फोन|मोबाइल/.test(label);

    const isEmailField =
        type === "email" ||
        /email|e-mail|ಇಮೇಲ್|ईमेल/.test(label);

    const isNumberField =
        type === "number" ||
        /age|ವಯಸ್ಸು|आयु/.test(label);

    const isAddressField =
        /address|ವಿಳಾಸ|पता/.test(label);

    // Reject phone-number-only answers in name fields.
    if (isNameField && /^[\d\s+\-().]+$/.test(value)) {
        return sfText("nameError");
    }

    // Validate email addresses.
    if (
        isEmailField &&
        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
    ) {
        return sfText("emailError");
    }

    // Validate phone numbers.
    if (isPhoneField) {
        const digits = value.replace(/\D/g, "");

        if (digits.length < 7 || digits.length > 15) {
            return sfText("phoneError");
        }
    }

    // Reject a phone number entered as an address.
    if (isAddressField) {
        const digits = value.replace(/\D/g, "");
        const hasLetters =
            /[A-Za-z\u0C80-\u0CFF\u0900-\u097F]/.test(value);

        const onlyPhoneCharacters =
            /^[\d\s+\-().]+$/.test(value);

        if (
            !hasLetters ||
            (
                digits.length >= 7 &&
                digits.length <= 15 &&
                onlyPhoneCharacters
            )
        ) {
            return sfText("addressError");
        }
    }

    // Validate number fields.
    if (isNumberField && !Number.isFinite(Number(value))) {
        return sfText("numberError");
    }

    return "";
}
// ============================================
// CHECK ANSWER, TRANSLATE AND CONFIRM
// ============================================

sf("Check").onclick = async () => {
    const field = sfFields[sfIndex];

    let value = sf("Answer").value.trim();

    if (!value && field.required) {
        sfMessage(sfText("required"));
        sfSpeak(sfText("required"));
        return;
    }

    // Correct common spoken email phrases again before validation.
    value = sfNormalizeSpokenAnswer(value, field);

    const label =
        `${field.label || ""} ${field.name || ""} ${field.type || ""}`
        .toLowerCase();

    const isEmailField =
        field.type === "email" ||
        /email|e-mail|ಇಮೇಲ್|ईमेल/.test(label);

    const isPhoneField =
        field.type === "tel" ||
        /phone|mobile|telephone|ಫೋನ್|ಮೊಬೈಲ್|फोन|मोबाइल/.test(label);

    const isNumericField =
        ["number", "date", "url"].includes(field.type);

    const isSelectField = field.type === "select";

    // Translate ordinary Kannada/Hindi answers into English.
    // Do not translate emails, phone numbers, dates, or select values.
    if (
        value &&
        sfLang() !== "en" &&
        !isEmailField &&
        !isPhoneField &&
        !isNumericField &&
        !isSelectField
    ) {
        sf("Check").disabled = true;
        sfMessage(sfText("translating"), true);

        try {
            value = await sfTranslate(value, "answer");
            sf("Answer").value = value;

        } catch (error) {
            sfMessage(sfText("translateError"));
            sfSpeak(sfText("translateError"));
            sf("Check").disabled = false;
            return;

        } finally {
            sf("Check").disabled = false;
        }
    }

    // Validate the resulting answer.
    const validationMessage = sfValidateAnswer(field, value);

    if (validationMessage) {
        sfMessage(validationMessage);
        sfSpeak(validationMessage);
        return;
    }

    try {
        const response = await fetch(
            "/smart-form-assistant/validate",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    label: field.label,
                    value: value,
                    required: field.required,
                    type: field.type
                })
            }
        );

        const data = await response.json();

        if (!response.ok || !data.valid) {
            const message =
                data.message || "Please check your answer.";

            sfMessage(message);
            sfSpeak(message);
            return;
        }

        sfAnswers[sfIndex] = value;

        const displayLabel =
            sfDisplayLabels[sfIndex] || field.label;

        sf("ConfirmText").textContent =
            `${displayLabel}: ${value || "—"}. ${sfText("correct")}`;

        sf("ConfirmBox").classList.remove("sf-hidden");

        sfMessage(
            sfLang() === "kn"
                ? "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಉತ್ತರವನ್ನು ಖಚಿತಪಡಿಸಿ."
                : sfLang() === "hi"
                    ? "कृपया अपने उत्तर की पुष्टि करें।"
                    : "Please confirm your answer.",
            true
        );

        sfSpeak(sf("ConfirmText").textContent);

    } catch (error) {
        sfMessage(
            "Could not validate your answer. Please try again."
        );
    }
};


// ============================================
// NAVIGATION AND REVIEW
// ============================================

sf("Edit").onclick = () => {
    sf("ConfirmBox").classList.add("sf-hidden");
    sf("Answer").focus();
};

sf("Confirm").onclick = async () => {
    sf("ConfirmBox").classList.add("sf-hidden");

    if (sfIndex < sfFields.length - 1) {
        sfIndex++;
        await sfRender();
    } else {
        sfReview();
    }
};

sf("Back").onclick = () => {
    sfAnswers[sfIndex] = sf("Answer").value;

    if (sfIndex > 0) {
        sfIndex--;
        sfRender();
    }
};

function sfReview() {
    sfStopListening();

    sf("QuestionCard").classList.add("sf-hidden");
    sf("Review").classList.remove("sf-hidden");

    sf("ProgressText").textContent = "Review";
    sf("ProgressPercent").textContent = "100%";
    sf("ProgressBar").style.width = "100%";

    sf("ReviewList").innerHTML = "";

    sfFields.forEach((field, index) => {
        const row = document.createElement("div");
        row.className = "sf-review-row";

        const label = document.createElement("strong");
        label.textContent =
            sfDisplayLabels[index] || field.label;

        const value = document.createElement("div");
        value.textContent = sfAnswers[index] || "—";

        const button = document.createElement("button");
        button.type = "button";
        button.className = "sf-secondary";
        button.textContent = "Edit";

        button.onclick = async () => {
            sfIndex = index;
            await sfRender();
        };

        row.append(label, value, button);
        sf("ReviewList").appendChild(row);
    });
}

sf("ReviewBack").onclick = () => {
    sfIndex = sfFields.length - 1;
    sfRender();
};

sf("Finish").onclick = () => {
    sf("FinishMessage").textContent = sfText("finish");

    sf("FinishMessage").className =
        "sf-message sf-success";

    sfSpeak(sfText("finish"));
};


// ============================================
// BROWSER VOICES AND LANGUAGE CHANGES
// ============================================

if ("speechSynthesis" in window) {
    window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.getVoices();
    };
}

if (sf("Language")) {
    sf("Language").addEventListener("change", () => {
        sfTranslationCache.clear();

        if (sfFields.length) {
            sfRender();
        }
    });
}