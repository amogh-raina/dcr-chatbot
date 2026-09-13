// API-marked FAQ graphs use explicit confirmation and API-provided navigation.
let faqMode = false;
let faqBusy = false;
let faqRevision = 0;

function faqBubble(text, user = false, html = false) {
  const wrapper = document.createElement('div');
  wrapper.className = user ? 'message-container-user' : 'message-container-bot';
  const bubble = document.createElement('div');
  bubble.className = user ? 'message-user' : 'message-bot';
  bubble.style.whiteSpace = 'pre-wrap';
  if (html) {
    // Render DCR prose/links without permitting executable HTML or attributes.
    const parsed = new DOMParser().parseFromString(text, 'text/html');
    function copy(node, target) {
      if (node.nodeType === Node.TEXT_NODE) {
        target.appendChild(document.createTextNode(node.textContent));
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        if (['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT'].includes(node.tagName)) return;
        const allowed = ['P', 'BR', 'STRONG', 'EM', 'B', 'I', 'UL', 'OL', 'LI', 'A'];
        const element = document.createElement(allowed.includes(node.tagName) ? node.tagName : 'span');
        if (node.tagName === 'A') {
          const href = node.getAttribute('href') || '';
          if (/^(https?:\/\/|mailto:)/i.test(href)) {
            element.href = href;
            element.target = '_blank';
            element.rel = 'noopener noreferrer';
          }
        }
        node.childNodes.forEach(child => copy(child, element));
        target.appendChild(element);
      }
    }
    parsed.body.childNodes.forEach(node => copy(node, bubble));
  } else bubble.textContent = text;
  wrapper.appendChild(bubble);
  chatBox.insertBefore(wrapper, chatBox.firstChild);
  return bubble;
}

function renderFAQ(data) {
  faqMode = true;
  faqRevision += 1;
  const revision = faqRevision;
  chatBox.querySelectorAll('[data-faq-control]').forEach(button => button.disabled = true);
  hideLoader();
  enableChatInput();
  if (data.error) {
    faqBubble(data.error);
    return;
  }
  faqBubble(data.response || '', false, data.status === 'answer');
  if (data.follow_up) faqBubble(data.follow_up);
  const controls = faqBubble('');
  controls.style.display = 'flex';
  controls.style.flexWrap = 'wrap';
  controls.style.gap = '8px';
  function button(label, request) {
    const control = document.createElement('button');
    control.type = 'button';
    control.className = 'option-button';
    control.dataset.faqControl = 'true';
    control.textContent = label;
    control.addEventListener('click', () => {
      if (revision === faqRevision && !faqBusy) sendFAQ(request, label);
    });
    controls.appendChild(control);
  }
  for (const choice of data.feedback || []) {
    button(choice.label, {action: 'feedback', feedback_id: data.feedback_id, value: choice.value});
  }
  for (const candidate of data.candidates || []) {
    if (data.status === 'confirm_match') {
      const question = document.createElement('strong');
      question.textContent = candidate.question;
      question.style.flexBasis = '100%';
      controls.appendChild(question);
    }
    button(data.status === 'confirm_match' ? 'Yes, show the answer' : candidate.question,
      {action: 'confirm', match_id: data.match_id, candidate_key: candidate.candidate_key});
  }
  if (data.match_id) button('No — let me rephrase', {action: 'reject', match_id: data.match_id});
  for (const action of data.actions || []) {
    if (action.action !== 'topics') button(action.label, {action: action.action});
  }
  if (data.navigation) {
    renderFAQNavigation(data.navigation);
    const current = data.navigation.find(menu => menu.event_id === data.event_id)
      || data.navigation.find(menu => !menu.is_home)
      || data.navigation.find(menu => menu.is_home);
    const suggestions = (data.suppress_suggestions ? [] : (current?.options || [])).filter(choice => !isFAQUtility(choice));
    if (data.status === 'answer' && !data.topic_explored && !current?.is_home && suggestions.length) {
      const heading = document.createElement('span');
      heading.className = 'faq-suggestion-heading';
      heading.textContent = data.topic_name
        ? `More questions about ${data.topic_name.toLowerCase()}`
        : 'More questions about this topic';
      heading.style.cssText = 'flex-basis:100%;font-size:0.85em;color:#526072;';
      controls.appendChild(heading);
    }
    for (const choice of suggestions) {
      button(choice.question, {event_id: choice.event_id, value: choice.value});
    }
  }
  if (!controls.childNodes.length) controls.parentElement.remove();
  chatInput.focus();
}

// These labels affect placement only. Execution always uses the API choice.
function isFAQUtility(choice) {
  return ['back to topics', 'proceed to application'].includes(choice.question.trim().toLowerCase());
}

function renderFAQNavigation(menus) {
  const bar = document.getElementById('faq-navigation');
  bar.replaceChildren();
  bar.hidden = !menus.length;
  if (!menus.length) return;
  const allChoices = menus.flatMap(menu => menu.options);
  const back = allChoices.find(choice => choice.question.trim().toLowerCase() === 'back to topics');
  const application = allChoices.find(choice => choice.question.trim().toLowerCase() === 'proceed to application');
  function add(label, choice, fallback) {
    const control = document.createElement('button');
    control.type = 'button';
    control.className = 'option-button';
    control.textContent = label;
    control.addEventListener('click', () => {
      if (!faqBusy) sendFAQ(choice
        ? {event_id: choice.event_id, value: choice.value} : fallback, label);
    });
    bar.appendChild(control);
  }
  add('Back to topics', back, {action: 'topics'});
  if (application) add(application.question, application);
}

async function sendFAQ(payload, label) {
  if (faqBusy) return;
  faqBusy = true;
  document.querySelectorAll('#faq-navigation button').forEach(button => button.disabled = true);
  faqBubble(label, true);
  chatInput.value = '';
  disableChatInput();
  showLoader();
  try {
    const response = await fetch('/chat', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-Session-ID': sessionId},
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    renderFAQ(data);
  } catch (error) {
    faqBubble('The connection was interrupted. Please try again.');
  } finally {
    faqBusy = false;
    document.querySelectorAll('#faq-navigation button').forEach(button => button.disabled = false);
    hideLoader();
    enableChatInput();
  }
}

const chatHeader = document.getElementById("chat-header");
const chatInfo = document.getElementById("chat-info");
const chatInput = document.getElementById("chat-input");
const chatBox = document.getElementById("chat-box");
const chatInputContainer = document.getElementById("chat-input-container");
const sendButton = document.getElementById("send-button");

/** @type {string | null} */
let simulationId = null;
/** @type {string | null} */
let event_id = null;
/** @type {string} */
let sessionId = generateSessionId(); // Always generate new session
sessionStorage.setItem("sessionId", sessionId);
//let sessionId = null; // Add session ID for this tab
let graphLanguage = "da"; // Default to Danish

// Generate unique session ID for this tab
function generateSessionId() {
  return (
    "session_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9)
  );
}

// Translation dictionary
const i18n = {
  da: {
    welcome: "Velkommen!",
    sendMessage: "Skriv en besked...",
    loadFirst: "Indlæs en graf først for at starte med at chatte...",
    loading: "Indlæser...",
    invalidGraph: "Indtast venligst et gyldigt Graf ID",
    graphNotFound: "Graf ikke fundet",
    interpreted: "Fortolket besked ",
    suggestion: "Forslag:",
    clickButton: "Du kan også klikke på en af knapperne nedenfor",
    conclusion: "Konklusion:",
    continue: "Fortsæt",
    continuing: "Fortsætter...",
    error: "Fejl",
    LoadButton: "Indlæs",
    graphIdLabel: "Graf ID:",
    noQuestions: "Ingen spørgsmål fundet i grafen.",
    couldNotCreateSimulation: "Kunne ikke oprette simulation.",
  },
  en: {
    welcome: "Welcome!",
    sendMessage: "Type a reply and press Enter...",
    loadFirst: "Load a graph first to start chatting...",
    loading: "Loading...",
    invalidGraph: "Please enter a valid Graph ID",
    graphNotFound: "Graph not found",
    interpreted: "Interpreted message ",
    suggestion: "Suggestion:",
    clickButton: "You can also click one of the buttons below",
    conclusion: "Conclusion:",
    continue: "Continue",
    continuing: "Continuing...",
    error: "Error",
    LoadButton: "Load",
    graphIdLabel: "Graph ID:",
    noQuestions: "No questions found in the graph.",
    couldNotCreateSimulation: "Could not create simulation.",
  },
  es: {
    welcome: "¡Bienvenido!",
    sendMessage: "Escribe una respuesta y presiona Enter...",
    loadFirst: "Carga un gráfico primero para comenzar a chatear...",
    loading: "Cargando...",
    invalidGraph: "Por favor, introduce un ID de gráfico válido",
    graphNotFound: "Gráfico no encontrado",
    interpreted: "Mensaje interpretado ",
    suggestion: "Sugerencia:",
    clickButton: "También puedes hacer clic en uno de los botones abajo",
    conclusion: "Conclusión:",
    continue: "Continuar",
    continuing: "Continuando...",
    error: "Error",
    LoadButton: "Cargar",
    graphIdLabel: "ID de gráfico:",
    noQuestions: "No se encontraron preguntas en el gráfico.",
    couldNotCreateSimulation: "No se pudo crear la simulación.",
  },
};

function t(key) {
  return (
    (i18n[graphLanguage] && i18n[graphLanguage][key]) || i18n["en"][key] || key
  );
}

function getGraphIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("graphid") || window.FIXED_GRAPH_ID || null;
}

/** @typedef {{
 *    welcome: string,
 *    response: string,
 *    datatype: unknown,
 *    enum: unknown,
 *    simulation_id: string,
 *    event_id: string,
 *  }} InitResponse */

function setTextIfPresent(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function resetChatState() {
  const navigation = document.getElementById('faq-navigation');
  navigation.replaceChildren();
  navigation.hidden = true;
  faqMode = false;
  faqRevision += 1;
  chatBox.innerHTML = "";
  simulationId = null;
  event_id = null;
  disableChatInput();
}

window.addEventListener("DOMContentLoaded", () => {
  // Populate the graph-id input from URL if present, but do NOT auto-init.
  // Auto-init here + the loadBtn click handler was creating two simulations.
  const urlGraphId = getGraphIdFromUrl();
  const graphIdInput = document.getElementById("graph-id-input");
  if (urlGraphId && graphIdInput) {
    graphIdInput.value = urlGraphId;
  }
  disableChatInput();
  chatInput.placeholder = t("loadFirst");

  // Pages with no manual graph-id UI (e.g. the /demo widget) declare a
  // fixed graph id and expect the chat to initialize itself silently.
  if (window.FIXED_GRAPH_ID && !graphIdInput) {
    InitializeChat();
  }
});

window.addEventListener("popstate", async () => {
  const graphId = getGraphIdFromUrl();
  if (graphId) {
    await InitializeChat();
  }
});

// Wait for user to click Load button (id="load-graph-btn")
const loadBtn = document.getElementById("load-graph-btn");
if (loadBtn) {
  loadBtn.addEventListener("click", async () => {
    const graphIdInput = document.getElementById("graph-id-input");
    const graphId = graphIdInput ? graphIdInput.value : "";
    if (graphId) {
      // Update the URL without reloading the page
      window.history.pushState({}, "", `?graphid=${graphId}`);
      // Now call InitializeChat, which will pick up the new graphid from the URL
      await InitializeChat();
    }
  });
}

async function InitializeChat() {
  // Force new session for every graph load
  sessionId = generateSessionId();
  sessionStorage.setItem("sessionId", sessionId);
  // Clear the chat box and reset state
  chatBox.innerHTML = "";
  simulationId = null;
  event_id = null;

  showLoader();
  // Get graph ID from input field (id="graph-id-input")
  let graphId = getGraphIdFromUrl();
  if (!graphId) {
    displayError("Invalid Graph ID");
    hideLoader();
    return;
  }

  try {
    const response = await fetch("/init", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionId, // Send session ID in header
      },
      body: JSON.stringify({ graph_id: graphId }),
    });
    hideLoader(); // Hide loader on success

    const data = await response.json();

    // Set the language from backend
    if (data.graph_language) {
      if (data.graph_language.toLowerCase().startsWith("es")) {
        graphLanguage = "es";
      } else if (data.graph_language.toLowerCase().startsWith("da")) {
        graphLanguage = "da";
      } else {
        graphLanguage = "en";
      }

      const welcomeText = document.getElementById("welcome-text");
      if (welcomeText) {
        if (data.welcome) {
          welcomeText.textContent = `${data.welcome}`;
        } else {
          welcomeText.textContent = "";
        }
      }
    }

    if (!response.ok) {
      // Update all UI elements to the correct language
      setTextIfPresent("load-btn-label", t("LoadButton"));
      setTextIfPresent("graph-id-label", t("graphIdLabel"));
      chatInput.placeholder = t("sendMessage");

      if (data.error && data.error.toLowerCase().includes("no questions")) {
        displayError(t("noQuestions"));
        return;
      } else if (
        data.error &&
        data.error.toLowerCase().includes("graph not found")
      ) {
        displayError("Graph not found");
        return;
      } else if (
        data.error &&
        data.error.toLowerCase().includes("could not create simulation")
      ) {
        displayError(t("couldNotCreateSimulation"));
        return;
      }
    }

    setTextIfPresent("load-btn-label", t("LoadButton"));
    setTextIfPresent("graph-id-label", t("graphIdLabel"));

    // Store simulationId
    simulationId = data.simulation_id;
    event_id = data.event_id;

    if (data.faq) {
      renderFAQ(data);
    } else if (data.information) {
      AddInformation(data);
    } else {
      AddQuestion(data, false);
    }
    chatInput.focus();
  } catch (error) {
    hideLoader(); // Hide loader on error
    console.error("Error fetching initial question:", error);
    displayError(`Error: ${error.message}`);
  }
}

// Function to generate the loader dynamically
function createLoader() {
  const loaderDiv = document.createElement("div");
  loaderDiv.className = "dot-loader";
  const dot1 = document.createElement("span");
  dot1.className = "dot";
  const dot2 = document.createElement("span");
  dot2.className = "dot";
  const dot3 = document.createElement("span");
  dot3.className = "dot";

  loaderDiv.appendChild(dot1);
  loaderDiv.appendChild(dot2);
  loaderDiv.appendChild(dot3);

  return loaderDiv;
}

// Function to show loader in the chat box
function showLoader() {
  const loader = createLoader();
  loader.setAttribute("id", "loader"); // Set ID for future reference if needed
  chatBox.insertBefore(loader, chatBox.firstChild);
  disableChatInput();
  chatBox.scrollTop = chatBox.scrollHeight; // Scroll to the bottom
}

// Function to hide and remove the loader
function hideLoader() {
  const loader = document.getElementById("loader");
  if (loader) {
    loader.remove(); // Remove the loader element from the DOM
  }
}

/**
 * @param {{
 *    welcome?: string;
 *    response: any;
 *    datatype: any;
 *    enum: any;
 *    simulation_id?: string;
 *    event_id?: string;
 *    comment?: any;
 *    qvalue?: any;
 *    value?: any;
 * }} data
 * @param {boolean} confirm
 */
async function AddQuestion(data, confirm) {
  showLoader();
  // Hide the input prompt if it's a confirm question
  if (confirm) disableChatInput();
  else enableChatInput();

  // Construct the bot response message
  let question = data.response;
  let comment = data.comment;

  // Create the bot message container
  const botMessageContainer = document.createElement("div");
  botMessageContainer.className = "message-container-bot";
  const botMessageDiv = document.createElement("div");
  botMessageDiv.className = "message-bot";

  const questionDiv = document.createElement("div");
  questionDiv.textContent = question;
  questionDiv.innerHTML = questionDiv.textContent.replace(/\n/g, "<br>");

  const commentDiv = document.createElement("div");
  commentDiv.className = "comment-text";
  commentDiv.textContent = comment;
  commentDiv.innerHTML = commentDiv.textContent.replace(/\n/g, "<br>");

  // Append both textDiv and msgDiv to the wrapper
  botMessageDiv.appendChild(commentDiv);
  botMessageDiv.appendChild(questionDiv);

  // Add the bot message to the chat box
  botMessageContainer.appendChild(botMessageDiv);
  chatBox.insertBefore(botMessageContainer, chatBox.firstChild);
  chatBox.scrollTop = chatBox.scrollHeight; // Scroll to the bottom

  if ((data.datatype === "date" || data.enum) && !confirm) {
    printOptionalMessage(data);
  }

  chatInput.focus();

  if (confirm) {
    console.log("confirm");
    const userMessageDiv = document.createElement("div");
    userMessageDiv.className = "message-container-user instruction";

    // Create and append the instruction text span
    const instructionText = document.createElement("span");
    instructionText.className = "instruction-text-bot";
    instructionText.textContent = t("suggestion");
    userMessageDiv.appendChild(instructionText);

    // Create the message wrapper div
    const messageWrapper = document.createElement("div");
    messageWrapper.className = "message-wrapper";

    // Positive and negative confirmation button
    const confirmButtonPositive = document.createElement("button");
    confirmButtonPositive.className = "confirm-button-positive";
    confirmButtonPositive.innerHTML = `<i class="fa-solid fa-check"></i>`;
    confirmButtonPositive.value = data.value;
    confirmButtonPositive.setAttribute("data-message", data.qvalue);
    confirmButtonPositive.addEventListener("click", () =>
      handleButtonClickConfirm(confirmButtonPositive)
    );
    messageWrapper.appendChild(confirmButtonPositive);

    const confirmButtonNegative = document.createElement("span");
    confirmButtonNegative.className = "confirm-button-negative";
    confirmButtonNegative.innerHTML = `<i class="fa-solid fa-x"></i>`;
    confirmButtonNegative.addEventListener("click", () =>
      handleButtonClickReject(confirmButtonNegative, data)
    );
    messageWrapper.appendChild(confirmButtonNegative);

    // The suggested message
    const interpretedMessage = document.createElement("div");
    interpretedMessage.classList.add("message-user", "confirm-message");
    interpretedMessage.textContent = data.qvalue;
    messageWrapper.appendChild(interpretedMessage);
    userMessageDiv.appendChild(messageWrapper);
    chatBox.insertBefore(userMessageDiv, chatBox.firstChild);
  }

  chatBox.scrollTop = chatBox.scrollHeight; // Scroll to the bottom
  hideLoader(); // Hide loader after adding question
}

function renderInformationConclusion(data) {
  disableChatInput();
  const container = document.createElement("div");
  container.className = "message-container-bot";

  const conclusionLabel = document.createElement("span");
  conclusionLabel.className = "instruction-text-bot";
  conclusionLabel.textContent = t("conclusion");
  const conclusion = document.createElement("div");
  conclusion.className = "message-bot";
  conclusion.textContent = data.conclusion || "";
  conclusion.style.whiteSpace = "pre-line";
  container.appendChild(conclusionLabel);
  container.appendChild(conclusion);

  chatBox.insertBefore(container, chatBox.firstChild);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function AddInformation(data) {
  disableChatInput();
  hideOptionalContainers();

  const container = document.createElement("div");
  container.className = "message-container-bot";
  const message = document.createElement("div");
  message.className = "message-bot";
  message.textContent = data.response || "";
  message.style.whiteSpace = "pre-line";
  container.appendChild(message);

  const continueButton = document.createElement("button");
  continueButton.className = "instruction-button mt-2";
  continueButton.type = "button";
  continueButton.textContent = t("continue");
  continueButton.addEventListener("click", () =>
    continueInformation(data.event_id, continueButton)
  );
  container.appendChild(continueButton);

  chatBox.insertBefore(container, chatBox.firstChild);
  chatBox.scrollTop = chatBox.scrollHeight;
  hideLoader();
}

async function continueInformation(eventId, button) {
  button.disabled = true;
  button.textContent = t("continuing");
  showLoader();

  try {
    const response = await fetch("/continue", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionId,
      },
      body: JSON.stringify({ event_id: eventId }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `Error ${response.status}`);
    }

    event_id = data.event_id || null;
    if (data.conclusion) {
      renderInformationConclusion(data);
    } else if (data.information) {
      AddInformation(data);
    } else {
      AddQuestion(data, data.confirm);
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = t("continue");
    displayError(`Could not continue: ${error.message}`);
  } finally {
    hideLoader();
  }
}

function printOptionalMessage(data) {
  const instructionContainer = document.createElement("div");
  instructionContainer.className = "instruction-container";
  const buttonWrapper = document.createElement("div");
  buttonWrapper.className = "instruction-button-wrapper";

  // Handle different types of expected responses
  if (data.datatype === "date") {
    const datePicker = document.createElement("input");
    datePicker.type = "date";
    datePicker.className = "datepicker";
    buttonWrapper.appendChild(datePicker);
    datePicker.addEventListener("input", () => {
      const selectedDate = datePicker.value; // Date in yyyy-mm-dd format
      if (selectedDate) {
        datePicker.style.display = "none";
        const [year, month, day] = selectedDate.split("-"); // Split the date string
        const formattedDate = `${day}-${month}-${year}`; // Reformat it to dd-mm-yyyy
        DoReply(formattedDate, selectedDate);
      }
    });
  } else if (data.enum && data.enum !== "") {
    const enumItems = data.enum
      .split(")")
      .map((item) => {
        if (item.trim() === "") return null;
        const parts = item.trim().split("(");
        let label = parts[0].trim();
        // Remove starting ", " if present
        if (label.startsWith(", ")) {
          label = label.slice(2).trim();
        }
        const value = parts[1] ? parts[1].trim() : null;
        return { label, value };
      })
      .filter((item) => item !== null);

    enumItems.forEach((enumItem) => {
      const button = document.createElement("button");
      button.textContent = enumItem.label;
      button.value = enumItem.value;
      button.className = "instruction-button";
      button.setAttribute("data-message", enumItem.label);
      button.addEventListener("click", () => handleButtonClickConfirm(button));
      buttonWrapper.appendChild(button);
    });
    const instructionText = document.createElement("p");
    instructionText.className = "instruction-text";
    instructionText.textContent = t("clickButton");
    instructionContainer.appendChild(instructionText);
  }
  instructionContainer.appendChild(buttonWrapper);
  chatBox.insertBefore(instructionContainer, chatBox.firstChild);
}

async function handleButtonClickConfirm(button) {
  const instructionContainers = document.querySelectorAll(".instruction");
  instructionContainers.forEach((container) => {
    container.remove();
  });
  DoReply(button.getAttribute("data-message"), button.value);
}

async function handleButtonClickReject(button, data) {
  enableChatInput();
  const messageContainer = button.closest(".message-container-user");
  messageContainer.style.display = "none";
  printOptionalMessage(data);
}

async function hideOptionalContainers() {
  const instructionContainers = document.querySelectorAll(
    ".instruction-container"
  );
  instructionContainers.forEach((container) => {
    container.remove();
  });
}

async function DoReply(message, value) {
  if (faqMode) return sendFAQ({message}, message);
  hideOptionalContainers();
  // Add user message to chat box
  const userMessageDiv = document.createElement("div");
  userMessageDiv.classList.add("message-container-user");
  const userMessageWrapper = document.createElement("div");
  userMessageWrapper.className = "message-wrapper";

  const userMessage = document.createElement("div");
  userMessage.classList.add("message-user");
  userMessage.textContent = message;

  const editDiv = addEditLink(userMessage, event_id);
  if (editDiv) {
    userMessageWrapper.appendChild(editDiv);
  }
  userMessageWrapper.appendChild(userMessage);
  userMessageDiv.appendChild(userMessageWrapper);

  chatBox.insertBefore(userMessageDiv, chatBox.firstChild);
  chatBox.scrollTop = chatBox.scrollHeight; // Scroll to the bottom

  chatInput.value = "";

  // Show loader after the user sends a message
  showLoader();
  try {
    // Send message to server with session ID
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionId, // Include session ID
      },
      body: JSON.stringify({
        message,
        value,
        simulation_id: simulationId,
      }),
    });

    // Check if the response is not OK (status code outside 200-299)
    if (!response.ok) {
      const errorData = await response.json();
      console.error(
        "Error during chat response:",
        response.statusText,
        "response:",
        errorData
      );
      throw new Error(
        `Error ${response.status}: ${
          errorData.message || errorData.error || "Unknown error"
        }`
      );
    }
    const data = await response.json();
    // Hide loader when response is received
    hideLoader();
    console.log(data);
    if (data.interpreted_reply) {
      const lastUserMessage = chatBox.querySelector(
        ".message-container-user:first-child"
      );
      const interpretedValueDiv = document.createElement("div");
      interpretedValueDiv.className = "text-xs";
      interpretedValueDiv.innerHTML =
        '<span class="font-light">' +
        t("interpreted") +
        ": </span>" +
        data.interpreted_reply;
      // Insert the new element at the end of the last user message
      lastUserMessage.insertAdjacentElement("beforeend", interpretedValueDiv);
    }
    if (data.conclusion) {
      console.log("No response");
      // Hide the chat input container and show the conclusion
      disableChatInput();
      const botMessageContainer = document.createElement("div");
      botMessageContainer.className = "message-container-bot";
      const instructionText = document.createElement("span");
      instructionText.className = "instruction-text-bot";
      instructionText.textContent = t("conclusion");
      const botMessageDiv = document.createElement("div");
      botMessageDiv.className = "message-bot";
      botMessageDiv.innerHTML = data.conclusion;

      botMessageContainer.appendChild(instructionText);
      botMessageContainer.appendChild(botMessageDiv);

      chatBox.insertBefore(botMessageContainer, chatBox.firstChild);
      chatBox.scrollTop = chatBox.scrollHeight; // Scroll to the bottom
    } else {
      // Add the interpreted value to the previous user message
      event_id = data.event_id;
      if (data.information) {
        AddInformation(data);
      } else {
        AddQuestion(data, data.confirm);
      }
    }
  } catch (error) {
    console.error("Error during chat response:", error);
    displayError(`Error: ${error.message}`);
    hideLoader(); // Hide loader on error
  }
}

chatInput.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault(); // Prevent newline on Enter key
    const message = chatInput.value.trim();
    if (message) {
      DoReply(message, null);
    }
  }
});

sendButton.addEventListener("click", async () => {
  const message = chatInput.value.trim();
  if (message) {
    showLoader();
    await DoReply(message, null);
    hideLoader();
  }
});

/**
 * @param {HTMLElement} messageElement
 * @param {string|null} eventId
 * @returns {HTMLSpanElement|null}
 */
function addEditLink(messageElement, eventId) {
  // Check if the messageElement has a class of user-message
  if (
    messageElement.classList.contains("message-user") &&
    !messageElement.nextElementSibling?.classList.contains("edit-button")
  ) {
    const editText = document.createElement("span");
    editText.className = "edit-button";
    editText.innerHTML = '<i class="fa-solid fa-pen edit-icon"></i>';
    // Set the click event to call the editMessage function
    editText.onclick = function () {
      editMessage(eventId); // Pass the correct event_id to editMessage function
    };

    // Remove all other edit texts
    const allEditTexts = document.querySelectorAll(".edit-button");
    allEditTexts.forEach((text) => {
      if (text !== editText) {
        text.remove();
      }
    });
    return editText;
  }
  return null;
}

async function editMessage(eventId, confirm) {
  hideOptionalContainers();

  console.log("want to edit", eventId);
  try {
    const response = await fetch("/edit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionId, // Include session ID
      },
      body: JSON.stringify({ event_id: eventId, confirm: confirm }),
    });
    if (!response.ok) {
      const errorData = await response.json();
      console.error(
        "Error during chat response:",
        response.statusText,
        "response:",
        errorData
      );
      throw new Error(
        `Error ${response.status}: ${
          errorData.message || errorData.error || "Unknown error"
        }`
      );
    } else {
      // Select the last .message-container-user in the chatBox
      const lastUserMessage = chatBox.querySelector(
        ".message-container-user:first-of-type"
      );

      // Check if the last user message contains an element with .instruction-text-bot
      if (
        lastUserMessage &&
        lastUserMessage.querySelector(".instruction-text-bot")
      ) {
        // Add the 'outline' class to the last user message if it contains .instruction-text-bot
        lastUserMessage.remove();
      }

      const lastBotMessage = chatBox.querySelector(
        ".message-container-bot:first-of-type"
      );
      lastBotMessage.classList.add("disabled-message");

      if ((chatInputContainer.style.display = "none")) {
        chatInputContainer.style.display = "block";
      }

      const data = await response.json();

      console.log(data);
      event_id = data.event_id;
      AddQuestion(data, data.confirm);
    }
  } catch (error) {
    console.error("Error editing message:", error);
    displayError(`Error: ${error.message}`);
  }
}

function disableChatInput() {
  chatInput.disabled = true;
  sendButton.disabled = true;
}

function enableChatInput() {
  chatInput.disabled = false;
  sendButton.disabled = false;
  chatInput.placeholder = t("sendMessage");
}

function displayError(message) {
  // Create the error message container, in the bot message style
  // Create the bot message container
  const botMessageContainer = document.createElement("div");
  botMessageContainer.className = "message-container-bot";
  const botMessageDiv = document.createElement("div");
  botMessageDiv.className = "message-bot message-bot-error";
  botMessageDiv.innerHTML = message;
  botMessageContainer.appendChild(botMessageDiv);
  chatBox.appendChild(botMessageContainer);

  // Remove all  edits
  const allEditTexts = document.querySelectorAll(".edit-button");
  allEditTexts.forEach((text) => {
    text.remove();
  });
  disableChatInput();
}
