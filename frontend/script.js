/* =========================================================
   IP-SAKTI SAHAYAK
   Frontend Controller
   ========================================================= */

const API_URL = "http://127.0.0.1:8000";

/* =========================
   ELEMENTS
   ========================= */

const queryInput = document.getElementById("queryInput");
const sendBtn = document.getElementById("sendBtn");
const chatMessages = document.getElementById("chatMessages");
const chatSection = document.getElementById("chatSection");
const hero = document.getElementById("hero");
const features = document.getElementById("features");
const loadingMessage = document.getElementById("loadingMessage");

const jurisdictionSelect = document.getElementById("jurisdiction");
const languageSelect = document.getElementById("language");

const classifierBtn = document.getElementById("classifierBtn");
const absBtn = document.getElementById("absBtn");

const themeBtn = document.getElementById("themeBtn");

const clearChatBtn = document.getElementById("clearChat");
const disclaimerBtn = document.getElementById("disclaimerBtn");

const disclaimerModal = document.getElementById("disclaimerModal");
const closeModal = document.getElementById("closeModal");
const modalOk = document.getElementById("modalOk");


/* =========================================================
   SEND QUESTION
   ========================================================= */

async function askQuestion(question = null) {

    const query = question || queryInput.value.trim();

    if (!query) {
        queryInput.focus();
        return;
    }

    const jurisdiction = jurisdictionSelect.value;
    const language = languageSelect.value;

    /* Show chat area */

    hero.style.paddingBottom = "20px";

    if (features) {
        features.style.display = "none";
    }

    /* Add user message */

    addUserMessage(query);

    queryInput.value = "";

    autoResize();

    /* Show loading */

    loadingMessage.classList.remove("hidden");

    chatSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });


    try {

        console.log("Sending request to:", API_URL);

        const response = await fetch(`${API_URL}/api/chat`, {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({

                query: query,

                jurisdiction: jurisdiction,

                language: language

            })

        });


        /* HTTP error */

        if (!response.ok) {

            const errorText = await response.text();

            throw new Error(
                `Server error ${response.status}: ${errorText}`
            );
        }


        const data = await response.json();

        console.log("API response:", data);


        /* Hide loading */

        loadingMessage.classList.add("hidden");


        /* Add AI answer */

        addAIMessage(data);


    } catch (error) {

        console.error("IP-SAKTI Error:", error);

        loadingMessage.classList.add("hidden");

        addErrorMessage(error);

    }

}


/* =========================================================
   USER MESSAGE
   ========================================================= */

function addUserMessage(text) {

    const message = document.createElement("div");

    message.className = "message user-message";

    message.innerHTML = `
        <div class="user-bubble">
            ${escapeHTML(text)}
        </div>
    `;

    chatMessages.appendChild(message);

}


/* =========================================================
   AI MESSAGE
   ========================================================= */

function addAIMessage(data) {

    const message = document.createElement("div");

    message.className = "message ai-message";


    const answer = data.answer ||
                   data.message ||
                   "I could not generate an answer.";


    let sourcesHTML = "";


    /* =========================
       SOURCES
       ========================= */

    if (data.sources && data.sources.length > 0) {

        sourcesHTML = `

            <div class="sources-box">

                <div class="sources-title">
                    📚 Sources used
                </div>

                ${data.sources.map((source, index) => `

                    <div class="source-item">

                        <div>

                            <div class="source-name">
                                ${escapeHTML(
                                    source.document_name ||
                                    "Legal Document"
                                )}
                            </div>

                            <div class="source-meta">

                                ${source.section
                                    ? escapeHTML(source.section)
                                    : "Relevant section"}

                            </div>

                        </div>

                        <div class="source-meta">

                            ${source.page_number
                                ? `Page ${source.page_number}`
                                : ""}

                        </div>

                    </div>

                `).join("")}


                <div class="confidence">

                    ✓ Source-grounded answer

                </div>

            </div>

        `;

    }


    message.innerHTML = `

        <div class="ai-avatar">
            ✦
        </div>

        <div class="ai-content">

            <div class="answer-label">
                IP-SAKTI
            </div>

            <p>
                ${formatAnswer(answer)}
            </p>

            ${sourcesHTML}

            <div class="answer-actions">

                <button
                    class="copy-btn"
                    onclick="copyAnswer(this)"
                >
                    Copy
                </button>

            </div>

        </div>

    `;


    chatMessages.appendChild(message);


    /* Scroll to answer */

    setTimeout(() => {

        message.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });

    }, 100);

}


/* =========================================================
   ERROR MESSAGE
   ========================================================= */

function addErrorMessage(error) {

    const message = document.createElement("div");

    message.className = "message ai-message";

    message.innerHTML = `

        <div class="ai-avatar">
            !
        </div>

        <div class="ai-content">

            <div class="answer-label">
                IP-SAKTI
            </div>

            <p>
                Sorry, I couldn't connect to the AI service right now.
                Please make sure the FastAPI server is running.
            </p>

            <div class="sources-box">

                <div class="sources-title">
                    Technical information
                </div>

                <div class="source-item">

                    <span>
                        ${escapeHTML(error.message)}
                    </span>

                </div>

            </div>

        </div>

    `;

    chatMessages.appendChild(message);

}


/* =========================================================
   FORMAT ANSWER
   ========================================================= */

function formatAnswer(text) {

    let safe = escapeHTML(String(text));

    /* Bold */

    safe = safe.replace(
        /\*\*(.*?)\*\*/g,
        "<strong>$1</strong>"
    );

    /* Line breaks */

    safe = safe.replace(/\n/g, "<br>");

    return safe;

}


/* =========================================================
   ESCAPE HTML
   ========================================================= */

function escapeHTML(text) {

    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}


/* =========================================================
   COPY ANSWER
   ========================================================= */

function copyAnswer(button) {

    const content =
        button
            .closest(".ai-content")
            .querySelector("p")
            .innerText;


    navigator.clipboard.writeText(content)
        .then(() => {

            button.innerText = "Copied ✓";

            setTimeout(() => {

                button.innerText = "Copy";

            }, 1500);

        });

}


/* =========================================================
   ENTER TO SEND
   ========================================================= */

queryInput.addEventListener("keydown", function(event) {

    if (event.key === "Enter" && !event.shiftKey) {

        event.preventDefault();

        askQuestion();

    }

});


/* =========================================================
   SEND BUTTON
   ========================================================= */

sendBtn.addEventListener("click", () => {

    askQuestion();

});


/* =========================================================
   AUTO RESIZE TEXTAREA
   ========================================================= */

queryInput.addEventListener("input", autoResize);


function autoResize() {

    queryInput.style.height = "auto";

    queryInput.style.height =
        Math.min(queryInput.scrollHeight, 180) + "px";

}


/* =========================================================
   SUGGESTION BUTTONS
   ========================================================= */

document.querySelectorAll(".suggestion").forEach(button => {

    button.addEventListener("click", () => {

        const question =
            button.dataset.question;

        askQuestion(question);

    });

});


/* =========================================================
   FEATURE CARDS
   ========================================================= */

document.querySelectorAll(".feature-card").forEach(card => {

    card.addEventListener("click", () => {

        const question =
            card.dataset.question;

        askQuestion(question);

    });

});


/* =========================================================
   FORMULATION CLASSIFIER
   ========================================================= */

classifierBtn.addEventListener("click", () => {

    queryInput.value =
        "Classify this Ayurvedic formulation and explain its regulatory category and IP pathway: ";

    queryInput.focus();

    autoResize();

});


/* =========================================================
   ABS / TK HELPER
   ========================================================= */

absBtn.addEventListener("click", () => {

    queryInput.value =
        "Does this use of an Indian biological resource or traditional knowledge require ABS compliance? Explain the relevant requirements: ";

    queryInput.focus();

    autoResize();

});


/* =========================================================
   CLEAR CHAT
   ========================================================= */

clearChatBtn.addEventListener("click", () => {

    chatMessages.innerHTML = "";

    features.style.display = "";

    queryInput.value = "";

    hero.scrollIntoView({
        behavior: "smooth"
    });

});


/* =========================================================
   DISCLAIMER
   ========================================================= */

disclaimerBtn.addEventListener("click", () => {

    disclaimerModal.classList.remove("hidden");

});


closeModal.addEventListener("click", () => {

    disclaimerModal.classList.add("hidden");

});


modalOk.addEventListener("click", () => {

    disclaimerModal.classList.add("hidden");

});


disclaimerModal.addEventListener("click", (event) => {

    if (event.target === disclaimerModal) {

        disclaimerModal.classList.add("hidden");

    }

});


/* =========================================================
   DARK / LIGHT MODE
   ========================================================= */

themeBtn.addEventListener("click", () => {

    document.body.classList.toggle("dark");

    const dark =
        document.body.classList.contains("dark");

    localStorage.setItem(
        "ipSaktiTheme",
        dark ? "dark" : "light"
    );

});


/* Load saved theme */

if (localStorage.getItem("ipSaktiTheme") === "dark") {

    document.body.classList.add("dark");

}


/* =========================================================
   INITIAL STATE
   ========================================================= */

loadingMessage.classList.add("hidden");

console.log("IP-SAKTI Sahayak frontend loaded.");
console.log("Backend:", API_URL);