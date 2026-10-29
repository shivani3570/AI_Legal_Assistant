"use strict";

const sf = id => document.getElementById("sf" + id);

const LANGUAGES = {
    en: { name: "English", locale: "en-IN" },
    kn: { name: "Kannada", locale: "kn-IN" },
    hi: { name: "Hindi", locale: "hi-IN" },
    ta: { name: "Tamil", locale: "ta-IN" },
    te: { name: "Telugu", locale: "te-IN" }
};

let fields = [];
let answers = [];
let current = 0;
let formUrl = "";
let recognition = null;
let sessionNumber = 0;
let busy = false;

function selectedLanguage() {
    const value = sf("Language")?.value || "en";
    return LANGUAGES[value] ? value : "en";
}

function langInfo() {
    return LANGUAGES[selectedLanguage()];
}

function stopListening() {
    sessionNumber++;
    if (recognition) {
        try { recognition.abort(); } catch (_) {}
        recognition = null;
    }
}

function speak(text) {
    return new Promise(resolve => {
        if (!window.speechSynthesis) {
            console.error("Speech output is unavailable.");
            resolve();
            return;
        }

        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = langInfo().locale;
        utterance.rate = 0.82;

        const voices = window.speechSynthesis.getVoices();
        const prefix = selectedLanguage() === "kn" ? "kn" :
            selectedLanguage() === "hi" ? "hi" :
            selectedLanguage() === "ta" ? "ta" :
            selectedLanguage() === "te" ? "te" : "en";

        const voice = voices.find(v =>
            v.lang.toLowerCase() === langInfo().locale.toLowerCase()
        ) || voices.find(v =>
            v.lang.toLowerCase().startsWith(prefix)
        );

        if (voice) utterance.voice = voice;

        utterance.onend = resolve;
        utterance.onerror = event => {
            console.error("Speech error:", event.error);
            resolve();
        };

        window.speechSynthesis.speak(utterance);
    });
}

async function translate(text, mode, field = {}) {
    const response = await fetch("/smart-form-assistant/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            text,
            language: langInfo().name,
            targetLanguage: "English",
            mode,
            fieldType: field.type || "text",
            fieldLabel: field.label || ""
        })
    });

    const data = await response.json();
    if (!response.ok || !data.success) {
        throw new Error(data.error || "Translation failed.");
    }

    return String(data.translated || "").trim();
}

function isEmail(field) {
    return field.type === "email" ||
        /email|e-mail/i.test(field.label || "");
}

function isPhone(field) {
    return field.type === "tel" ||
        /phone|mobile|telephone/i.test(field.label || "");
}

function isName(field) {
    return /name|ಹೆಸರು|नाम|பெயர்|పేరు/i.test(
        `${field.label || ""} ${field.name || ""}`
    );
}

function isProtected(field) {
    return [
        "email", "tel", "number", "range", "date",
        "time", "datetime-local", "month", "week", "url", "password"
    ].includes((field.type || "").toLowerCase()) ||
        isEmail(field) || isPhone(field);
}

function showMessage(text, success = false) {
    const element = sf("FieldMessage");
    if (!element) return;

    element.textContent = text;
    element.className = success
        ? "sf-message sf-success"
        : "sf-message sf-error";
    element.classList.remove("sf-hidden");
}

function localError(field, value) {
    if (field.required && !value) return "This field is required.";

    if (isEmail(field) && value &&
        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        return "Please enter a valid email address.";
    }

    if (isPhone(field) && value) {
        const digits = value.replace(/\D/g, "");
        if (digits.length < 7 || digits.length > 15) {
            return "Please enter a valid phone number.";
        }
    }

    if (["number", "range"].includes(field.type) &&
        value && !Number.isFinite(Number(value))) {
        return "Please enter a valid number.";
    }

    return "";
}

// Recognition runs only after the assistant has finished speaking.
function listenOnce() {
    return new Promise((resolve, reject) => {
        const SpeechRecognition =
            window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            reject(new Error(
                "Speech recognition is unavailable in this browser. " +
                "Try Chrome and allow microphone access."
            ));
            return;
        }

        stopListening();

        const mySession = sessionNumber;
        const instance = new SpeechRecognition();
        recognition = instance;

        instance.lang = langInfo().locale;
        instance.continuous = false;
        instance.interimResults = false;
        instance.maxAlternatives = 3;

        let finished = false;

        const finish = (callback, value) => {
            if (finished) return;
            finished = true;
            if (recognition === instance) recognition = null;
            callback(value);
        };

        instance.onresult = event => {
            const result = event.results[0][0];
            finish(resolve, result.transcript.trim());
        };

        instance.onerror = event => {
            finish(reject, new Error(
                "Speech recognition error: " + event.error
            ));
        };

        instance.onend = () => {
            if (!finished && mySession === sessionNumber) {
                finish(reject, new Error("No speech detected. Please try again."));
            }
        };

        try {
            instance.start();
        } catch (error) {
            finish(reject, error);
        }
    });
}

async function askForQuestion(field) {
    const prefix = {
        en: "Please answer: ",
        kn: "ದಯವಿಟ್ಟು ಉತ್ತರಿಸಿ: ",
        hi: "कृपया उत्तर दें: ",
        ta: "தயவுசெய்து பதிலளிக்கவும்: ",
        te: "దయచేసి సమాధానం చెప్పండి: "
    }[selectedLanguage()];

    return translate(prefix + field.label, "question", field);
}

async function listenWithPrompt(prompt) {
    await speak(prompt);
    return listenOnce();
}
async function renderQuestion() {
    stopListening();
    window.speechSynthesis?.cancel();

    const field = fields[current];
    if (!field) return;

    sf("QuestionCard").classList.remove("sf-hidden");
    sf("Review").classList.add("sf-hidden");
    sf("ConfirmBox").classList.add("sf-hidden");

    // Original field label stays in its original language.
    sf("QuestionLabel").textContent =
        field.label + (field.required ? " *" : "");

    sf("ProgressText").textContent =
        `Field ${current + 1} of ${fields.length}`;

    const percent = Math.round((current + 1) / fields.length * 100);
    sf("ProgressPercent").textContent = percent + "%";
    sf("ProgressBar").style.width = percent + "%";

    const area = sf("AnswerArea");
    area.innerHTML = "";

    let input;

    if (field.type === "select") {
        input = document.createElement("select");
        input.add(new Option("Select an option", ""));
        (field.options || []).forEach(option => {
            input.add(new Option(option.text, option.value));
        });
    } else if (field.type === "textarea") {
        input = document.createElement("textarea");
    } else {
        input = document.createElement("input");
        input.type = [
            "email", "number", "date", "tel", "url", "password"
        ].includes(field.type) ? field.type : "text";
    }

    input.id = "sfAnswer";
    input.value = answers[current] || "";
    input.placeholder = field.placeholder || "Your answer";
    input.required = Boolean(field.required);
    area.appendChild(input);

    await runConversationForField(field);
}

async function runConversationForField(field) {
    if (busy) return;
    busy = true;

    try {
        let question = await askForQuestion(field);
        await speak(question);

        let spokenAnswer;

        while (true) {
            const listenPrompt = {
                en: "Please speak your answer now.",
                kn: "ದಯವಿಟ್ಟು ಈಗ ನಿಮ್ಮ ಉತ್ತರವನ್ನು ಹೇಳಿ.",
                hi: "कृपया अब अपना उत्तर बताइए।",
                ta: "இப்போது உங்கள் பதிலைச் சொல்லுங்கள்.",
                te: "దయచేసి ఇప్పుడు మీ సమాధానం చెప్పండి."
            }[selectedLanguage()];

            try {
                spokenAnswer = await listenWithPrompt(listenPrompt);
            } catch (error) {
                showMessage(error.message);
                await speak(error.message);
                return;
            }

            let value = spokenAnswer;

            // Preserve email addresses, phone numbers, dates and similar values.
            if (selectedLanguage() !== "en" &&
                !isProtected(field) &&
                field.type !== "select") {
                value = await translate(value, "answer", field);
            }

            value = value.replace(/^["'“”]+|["'“”]+$/g, "").trim();

            const error = localError(field, value);
            if (error) {
                await speak(error);
                continue;
            }

            answers[current] = value;
            sf("Answer").value = value;
            sf("ConfirmText").textContent = `${field.label}: ${value || "—"}`;
            sf("ConfirmBox").classList.remove("sf-hidden");

            const confirmation = {
                en: `I understood ${value}. Say yes to confirm or no to try again.`,
                kn: `ನಿಮ್ಮ ಉತ್ತರ ${value}. ಸರಿಯಾಗಿದ್ದರೆ ಹೌದು ಎಂದು ಹೇಳಿ. ಮತ್ತೆ ಹೇಳಲು ಇಲ್ಲ ಎಂದು ಹೇಳಿ.`,
                hi: `आपका उत्तर ${value} है। सही है तो हाँ कहें। दोबारा बोलने के लिए नहीं कहें।`,
                ta: `உங்கள் பதில் ${value}. சரி என்றால் ஆம் சொல்லுங்கள். மீண்டும் சொல்ல இல்லை என்று கூறுங்கள்.`,
                te: `మీ సమాధానం ${value}. సరైతే అవును అని చెప్పండి. మళ్లీ చెప్పాలంటే కాదు అని చెప్పండి.`
            }[selectedLanguage()];

            await speak(confirmation);

            let decision;
            try {
                decision = await listenOnce();
            } catch (error) {
                showMessage(error.message);
                return;
            }

            const normalized = decision.toLowerCase();

            const yes = {
                en: /\byes\b|correct|right/i,
                kn: /ಹೌದು|ಸರಿಯಾಗಿದೆ|ಸರಿ/,
                hi: /हाँ|हां|सही|ठीक/,
                ta: /ஆம்|சரி|ஆமாம்/,
                te: /అవును|సరి|సరైనది/
            }[selectedLanguage()];

            const no = {
                en: /\bno\b|wrong|again/i,
                kn: /ಇಲ್ಲ|ತಪ್ಪು|ಮತ್ತೆ/,
                hi: /नहीं|गलत|दोबारा/,
                ta: /இல்லை|தவறு|மீண்டும்/,
                te: /కాదు|తప్పు|మళ్లీ/
            }[selectedLanguage()];

            if (yes.test(normalized)) break;

            if (no.test(normalized)) {
                sf("ConfirmBox").classList.add("sf-hidden");
                await speak({
                    en: "Please say your answer again.",
                    kn: "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಉತ್ತರವನ್ನು ಮತ್ತೆ ಹೇಳಿ.",
                    hi: "कृपया अपना उत्तर फिर से बताइए।",
                    ta: "உங்கள் பதிலை மீண்டும் சொல்லுங்கள்.",
                    te: "దయచేసి మీ సమాధానాన్ని మళ్లీ చెప్పండి."
                }[selectedLanguage()]);
                continue;
            }

            await speak({
                en: "Please say yes or no.",
                kn: "ದಯವಿಟ್ಟು ಹೌದು ಅಥವಾ ಇಲ್ಲ ಎಂದು ಹೇಳಿ.",
                hi: "कृपया हाँ या नहीं कहें।",
                ta: "ஆம் அல்லது இல்லை என்று சொல்லுங்கள்.",
                te: "అవును లేదా కాదు అని చెప్పండి."
            }[selectedLanguage()]);
        }

        sf("ConfirmBox").classList.add("sf-hidden");

        if (current < fields.length - 1) {
            current++;
            await renderQuestion();
        } else {
            showReview();
            await speak({
                en: "All questions are complete. Please review your answers.",
                kn: "ಎಲ್ಲಾ ಪ್ರಶ್ನೆಗಳು ಮುಗಿದಿವೆ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಉತ್ತರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.",
                hi: "सभी प्रश्न पूरे हो गए हैं। कृपया अपने उत्तर जाँचें।",
                ta: "அனைத்து கேள்விகளும் முடிந்தன. உங்கள் பதில்களைச் சரிபார்க்கவும்.",
                te: "అన్ని ప్రశ్నలు పూర్తయ్యాయి. దయచేసి సమాధానాలను తనిఖీ చేయండి."
            }[selectedLanguage()]);
        }
    } catch (error) {
        console.error(error);
        showMessage(error.message || "Voice interaction failed.");
    } finally {
        busy = false;
    }
}

function showReview() {
    stopListening();
    window.speechSynthesis?.cancel();

    sf("QuestionCard").classList.add("sf-hidden");
    sf("Review").classList.remove("sf-hidden");

    const list = sf("ReviewList");
    list.innerHTML = "";

    fields.forEach((field, index) => {
        const row = document.createElement("div");
        row.className = "sf-review-row";

        const label = document.createElement("strong");
        label.textContent = field.label;

        const value = document.createElement("p");
        value.textContent = answers[index] || "—";

        const edit = document.createElement("button");
        edit.type = "button";
        edit.textContent = "Edit answer";
        edit.onclick = async () => {
            current = index;
            await renderQuestion();
        };

        row.append(label, value, edit);
        list.appendChild(row);
    });

    sf("FinishMessage").textContent =
        "Answers collected. Check them before submitting.";
}

async function loadForm(event) {
    event.preventDefault();

    const button = sf("LoadButton");
    button.disabled = true;

    try {
        formUrl = sf("FormUrl").value.trim();

        const response = await fetch("/smart-form-assistant/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: formUrl })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || "Could not load form.");
        }

        fields = data.fields;
        answers = fields.map(() => "");
        current = 0;

        sf("Summary").textContent =
            `${fields.length} fields detected from ${data.url}`;
        sf("Assistant").classList.remove("sf-hidden");

        // The Load Form click starts the voice conversation.
        await renderQuestion();
    } catch (error) {
        sf("LoadError").textContent = error.message;
        sf("LoadError").classList.remove("sf-hidden");
    } finally {
        button.disabled = false;
    }
}

if (sf("LoadForm")) sf("LoadForm").addEventListener("submit", loadForm);

if (sf("DemoButton")) {
    sf("DemoButton").addEventListener("click", () => {
        sf("FormUrl").value = "http://127.0.0.1:8000/demo_test_form.html";
    });
}

if (sf("ReadQuestion")) {
    sf("ReadQuestion").addEventListener("click", async () => {
        if (fields[current]) await speak(await askForQuestion(fields[current]));
    });
}

if (sf("SpeakAnswer")) {
    sf("SpeakAnswer").addEventListener("click", async () => {
        try {
            const value = await listenOnce();
            sf("Answer").value = value;
        } catch (error) {
            showMessage(error.message);
        }
    });
}

if (sf("Check")) {
    sf("Check").addEventListener("click", async () => {
        if (!fields[current]) return;
        answers[current] = sf("Answer").value.trim();
        await runConversationForField(fields[current]);
    });
}

if (sf("Confirm")) {
    sf("Confirm").addEventListener("click", async () => {
        sf("ConfirmBox").classList.add("sf-hidden");
        if (current < fields.length - 1) {
            current++;
            await renderQuestion();
        } else {
            showReview();
        }
    });
}

if (sf("Edit")) {
    sf("Edit").addEventListener("click", () => {
        sf("ConfirmBox").classList.add("sf-hidden");
        sf("Answer").focus();
    });
}

if (sf("Back")) {
    sf("Back").addEventListener("click", async () => {
        if (current > 0) {
            current--;
            await renderQuestion();
        }
    });
}

if (sf("ReviewBack")) {
    sf("ReviewBack").addEventListener("click", async () => {
        current = fields.length - 1;
        await renderQuestion();
    });
}

if (sf("ChangeForm")) {
    sf("ChangeForm").addEventListener("click", () => {
        stopListening();
        window.speechSynthesis?.cancel();
        sf("Assistant").classList.add("sf-hidden");
    });
}

if (sf("Language")) {
    sf("Language").addEventListener("change", async () => {
        stopListening();
        window.speechSynthesis?.cancel();

        if (fields.length && current < fields.length) {
            await renderQuestion();
        }
    });
}