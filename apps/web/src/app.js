import {
  SUGGESTED_QUESTIONS,
  createPatientSession,
  greetingForHour,
  mergePatientPages,
  nextWheelIndex,
  responseState,
} from "/assets/state.js";

const elements = {
  greeting: document.querySelector("#page-title"),
  sessionStatus: document.querySelector("#session-status"),
  search: document.querySelector("#patient-search"),
  wheel: document.querySelector("#patient-wheel"),
  wheelRegion: document.querySelector("#wheel-region"),
  wheelToggle: document.querySelector("#wheel-toggle"),
  liveRegion: document.querySelector("#patient-live-region"),
  loadMore: document.querySelector("#load-more"),
  selectedTitle: document.querySelector("#selected-patient-title"),
  admission: document.querySelector("#admission-select"),
  tabs: document.querySelector("#patient-tabs"),
  stage: document.querySelector("#chat-stage"),
  empty: document.querySelector("#empty-state"),
  conversation: document.querySelector("#conversation"),
  conversationIntro: document.querySelector("#conversation-intro"),
  messages: document.querySelector("#message-list"),
  suggestions: document.querySelector("#suggested-questions"),
  form: document.querySelector("#question-form"),
  question: document.querySelector("#question-input"),
  send: document.querySelector("#send-button"),
  developmentAccess: document.querySelector("#development-access"),
  developmentForm: document.querySelector("#development-access-form"),
  developmentDoctorId: document.querySelector("#development-doctor-id"),
  developmentPatientIds: document.querySelector("#development-patient-ids"),
  developmentSubmit: document.querySelector("#development-access-submit"),
  developmentStatus: document.querySelector("#development-access-status"),
};

let getAccessToken = null;
let unauthorizedCallback = null;
let patients = [];
let recentPatientIds = [];
let nextOffset = null;
let activeWheelIndex = -1;
let selectedPatientId = null;
let searchTimer = null;
let wheelTimer = null;
let directoryRequest = 0;
const sessions = new Map();
const openPatientIds = [];
let developmentAuthUrl = null;
let developmentToken = null;

function setSessionStatus(message, tone = "") {
  elements.sessionStatus.textContent = message;
  elements.sessionStatus.dataset.tone = tone;
}

function clearAllState() {
  patients = [];
  recentPatientIds = [];
  nextOffset = null;
  activeWheelIndex = -1;
  selectedPatientId = null;
  sessions.clear();
  openPatientIds.length = 0;
  elements.search.value = "";
  renderWheel();
  renderWorkspace();
}

function handleUnauthorized() {
  clearAllState();
  elements.search.disabled = true;
  setSessionStatus("Your secure session has ended", "error");
  if (typeof unauthorizedCallback === "function") {
    try {
      unauthorizedCallback();
    } catch {
      // Host callback failures do not expose or change protected page state.
    }
  }
}

function showDevelopmentAccess(message = "") {
  developmentToken = null;
  elements.developmentStatus.textContent = message;
  elements.developmentAccess.hidden = false;
  elements.developmentDoctorId.focus();
}

async function apiFetch(path, options = {}) {
  if (typeof getAccessToken !== "function") {
    throw new Error("SESSION_UNAVAILABLE");
  }
  // A fresh token is requested for every call and is never copied into page state.
  const token = await getAccessToken();
  if (typeof token !== "string" || token.length === 0) {
    handleUnauthorized();
    throw new Error("SESSION_UNAVAILABLE");
  }
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    handleUnauthorized();
    throw new Error("UNAUTHORIZED");
  }
  if (!response.ok) throw new Error(`HTTP_${response.status}`);
  return response;
}

function patientOrder(items) {
  const recentOrder = new Map(recentPatientIds.map((id, index) => [id, index]));
  return [...items].sort((left, right) => {
    const leftRank = recentOrder.get(left.patient_id);
    const rightRank = recentOrder.get(right.patient_id);
    if (leftRank !== undefined || rightRank !== undefined) {
      if (leftRank === undefined) return 1;
      if (rightRank === undefined) return -1;
      return leftRank - rightRank;
    }
    return left.patient_id.localeCompare(right.patient_id);
  });
}

function wheelOption(patient, index, recent) {
  const button = document.createElement("button");
  button.type = "button";
  button.id = `patient-option-${index}`;
  button.className = "wheel-option";
  button.dataset.index = String(index);
  button.dataset.active = String(index === activeWheelIndex);
  button.setAttribute("role", "option");
  button.setAttribute("aria-selected", String(patient.patient_id === selectedPatientId));

  const id = document.createElement("span");
  id.textContent = patient.patient_id;
  button.append(id);
  if (recent) {
    const tag = document.createElement("span");
    tag.className = "recent-tag";
    tag.textContent = "Recent";
    button.append(tag);
  }
  button.addEventListener("click", () => {
    setActiveWheelIndex(index, false);
    selectPatient(patient.patient_id);
  });
  return button;
}

function renderWheel() {
  elements.wheel.replaceChildren();
  const ordered = patientOrder(patients);
  patients = ordered;
  elements.wheel.parentElement.dataset.empty = String(patients.length === 0);
  if (patients.length === 0) {
    const empty = document.createElement("p");
    empty.className = "wheel-empty";
    empty.textContent = elements.search.value
      ? "No authorized patient IDs match this search."
      : "No authorized indexed patients are available.";
    elements.wheel.append(empty);
    elements.wheel.removeAttribute("aria-activedescendant");
    activeWheelIndex = -1;
  } else {
    patients.forEach((patient, index) => {
      elements.wheel.append(
        wheelOption(patient, index, recentPatientIds.includes(patient.patient_id)),
      );
    });
    if (activeWheelIndex < 0 || activeWheelIndex >= patients.length) {
      activeWheelIndex = 0;
    }
    setActiveWheelIndex(activeWheelIndex, false);
  }
  elements.loadMore.hidden = nextOffset === null;
}

function setActiveWheelIndex(index, scroll) {
  if (index < 0 || index >= patients.length) return;
  activeWheelIndex = index;
  const options = elements.wheel.querySelectorAll(".wheel-option");
  options.forEach((option, optionIndex) => {
    option.dataset.active = String(optionIndex === index);
  });
  const active = options[index];
  if (!active) return;
  elements.wheel.setAttribute("aria-activedescendant", active.id);
  elements.liveRegion.textContent = `Patient ${patients[index].patient_id}`;
  if (scroll) active.scrollIntoView({ block: "center", behavior: "smooth" });
}

function nearestWheelIndex() {
  const options = [...elements.wheel.querySelectorAll(".wheel-option")];
  const wheelBox = elements.wheel.getBoundingClientRect();
  const center = wheelBox.top + wheelBox.height / 2;
  let bestIndex = activeWheelIndex;
  let bestDistance = Number.POSITIVE_INFINITY;
  options.forEach((option, index) => {
    const box = option.getBoundingClientRect();
    const distance = Math.abs(box.top + box.height / 2 - center);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });
  return bestIndex;
}

async function loadPatients({ append = false } = {}) {
  const requestNumber = ++directoryRequest;
  setSessionStatus("Loading authorized patients");
  const offset = append ? nextOffset || 0 : 0;
  const params = new URLSearchParams({
    search: elements.search.value.trim(),
    limit: "50",
    offset: String(offset),
  });
  try {
    const response = await apiFetch(`/v1/patients?${params}`);
    const data = await response.json();
    if (requestNumber !== directoryRequest) return;
    patients = append ? mergePatientPages(patients, data.items) : data.items;
    recentPatientIds = data.recent_patient_ids;
    nextOffset = data.next_offset;
    activeWheelIndex = patients.length ? 0 : -1;
    renderWheel();
    setSessionStatus(
      data.total === 1 ? "1 authorized patient" : `${data.total} authorized patients`,
      "ready",
    );
  } catch (error) {
    if (error.message === "UNAUTHORIZED" || error.message === "SESSION_UNAVAILABLE") return;
    setSessionStatus("Patient directory is temporarily unavailable", "error");
    if (!append) {
      patients = [];
      renderWheel();
    }
  }
}

function selectedSession() {
  return selectedPatientId ? sessions.get(selectedPatientId) : null;
}

function addOption(select, value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  select.append(option);
}

function renderAdmission(session) {
  elements.admission.replaceChildren();
  addOption(elements.admission, "", "All admissions");
  for (const admissionId of session.patient.admission_ids) {
    addOption(elements.admission, admissionId, admissionId);
  }
  elements.admission.value = session.admissionId;
  elements.admission.disabled = session.inFlight;
}

function renderTabs() {
  elements.tabs.replaceChildren();
  for (const patientId of openPatientIds) {
    const session = sessions.get(patientId);
    if (!session) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "patient-tab";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(patientId === selectedPatientId));
    button.textContent = patientId;
    button.addEventListener("click", () => selectPatient(patientId));
    if (session.unread) {
      const unread = document.createElement("span");
      unread.className = "unread-mark";
      unread.title = "New response";
      button.append(unread);
    }
    elements.tabs.append(button);
  }
}

function appendCitations(container, citations) {
  if (!citations.length) return;
  const details = document.createElement("details");
  details.className = "citation-details";
  const summary = document.createElement("summary");
  summary.textContent = citations.length === 1 ? "1 source" : `${citations.length} sources`;
  details.append(summary);
  const groups = new Map();
  for (const citation of citations) {
    const list = groups.get(citation.domain) || [];
    list.push(citation);
    groups.set(citation.domain, list);
  }
  for (const [domain, group] of groups) {
    const section = document.createElement("section");
    section.className = "citation-group";
    const heading = document.createElement("p");
    heading.className = "citation-group-title";
    heading.textContent = domain[0].toUpperCase() + domain.slice(1);
    section.append(heading);
    for (const citation of group) {
      const item = document.createElement("p");
      item.className = "citation-item";
      const admissions = citation.admission_ids.length
        ? citation.admission_ids.join(", ")
        : "No admission ID";
      item.textContent = `${citation.chunk_id} | Admissions: ${admissions} | Repeated: ${citation.repeat_count}`;
      section.append(item);
    }
    details.append(section);
  }
  container.append(details);
}

function renderMessages(session) {
  elements.messages.replaceChildren();
  for (const message of session.messages) {
    const article = document.createElement("article");
    if (message.role === "doctor") {
      article.className = "message message-doctor";
      article.textContent = message.text;
    } else {
      const state = responseState(message.status);
      article.className = "message message-assistant";
      article.dataset.tone = state.tone;
      const status = document.createElement("p");
      status.className = "message-status";
      status.textContent = state.label;
      const text = document.createElement("p");
      text.className = "message-text";
      text.textContent = message.text;
      article.append(status, text);
      appendCitations(article, message.citations || []);
    }
    elements.messages.append(article);
  }
  if (session.inFlight) {
    const loading = document.createElement("div");
    loading.className = "message message-assistant loading-message";
    loading.setAttribute("role", "status");
    const bar = document.createElement("span");
    bar.className = "loading-bar";
    bar.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = "Reviewing recorded history";
    loading.append(bar, label);
    elements.messages.append(loading);
  }
}

function renderWorkspace() {
  const session = selectedSession();
  elements.empty.hidden = Boolean(session);
  elements.conversation.hidden = !session;
  if (!session) {
    elements.selectedTitle.textContent = "No patient selected";
    elements.admission.replaceChildren();
    addOption(elements.admission, "", "All admissions");
    elements.admission.disabled = true;
    elements.question.disabled = true;
    elements.question.placeholder = "Select a patient before asking a question";
    elements.send.disabled = true;
    renderTabs();
    return;
  }
  elements.selectedTitle.textContent = `Patient ${session.patient.patient_id}`;
  elements.conversationIntro.hidden = session.messages.length > 0;
  renderAdmission(session);
  renderMessages(session);
  elements.question.disabled = session.inFlight;
  elements.question.placeholder = "Ask about this patient's recorded history";
  elements.send.disabled = session.inFlight || elements.question.value.trim().length < 2;
  renderTabs();
}

function selectPatient(patientId) {
  let session = sessions.get(patientId);
  if (!session) {
    const patient = patients.find((item) => item.patient_id === patientId);
    if (!patient) return;
    session = createPatientSession(patient);
    sessions.set(patientId, session);
    openPatientIds.push(patientId);
  }
  selectedPatientId = patientId;
  session.unread = false;
  renderWorkspace();
  elements.liveRegion.textContent = `Selected patient ${patientId}`;
  elements.question.focus();
  apiFetch(`/v1/patients/${encodeURIComponent(patientId)}/selection`, {
    method: "POST",
  }).catch(() => {
    // Recent-list persistence does not block access to the selected history.
  });
}

async function submitQuestion(questionText) {
  const session = selectedSession();
  const patientId = selectedPatientId;
  const question = questionText.trim();
  if (!session || !patientId || session.inFlight || question.length < 2) return;
  session.messages.push({ role: "doctor", text: question });
  session.inFlight = true;
  elements.question.value = "";
  elements.question.style.height = "auto";
  renderWorkspace();
  elements.stage.scrollTo({ top: elements.stage.scrollHeight, behavior: "smooth" });
  try {
    const response = await apiFetch(
      `/v1/patients/${encodeURIComponent(patientId)}/history-query`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          admission_id: session.admissionId || null,
        }),
      },
    );
    const data = await response.json();
    if (sessions.get(patientId) !== session) return;
    session.messages.push({
      role: "assistant",
      text: data.answer,
      status: data.status,
      citations: data.citations,
    });
  } catch (error) {
    if (sessions.get(patientId) !== session) return;
    if (error.message !== "UNAUTHORIZED" && error.message !== "SESSION_UNAVAILABLE") {
      session.messages.push({
        role: "assistant",
        text: "The history service is temporarily unavailable. Please try again.",
        status: "error",
        citations: [],
      });
    }
  } finally {
    if (sessions.get(patientId) === session) {
      session.inFlight = false;
      if (selectedPatientId !== patientId) session.unread = true;
      renderWorkspace();
      if (selectedPatientId === patientId) {
        elements.stage.scrollTo({ top: elements.stage.scrollHeight, behavior: "smooth" });
      }
    }
  }
}

function renderSuggestions() {
  elements.suggestions.replaceChildren();
  for (const question of SUGGESTED_QUESTIONS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "suggestion-button";
    button.textContent = question;
    button.addEventListener("click", () => submitQuestion(question));
    elements.suggestions.append(button);
  }
}

elements.wheel.addEventListener("scroll", () => {
  window.clearTimeout(wheelTimer);
  wheelTimer = window.setTimeout(() => {
    const index = nearestWheelIndex();
    setActiveWheelIndex(index, false);
  }, 100);
});

elements.wheel.addEventListener("keydown", (event) => {
  let next = activeWheelIndex;
  if (event.key === "ArrowDown") next = nextWheelIndex(activeWheelIndex, 1, patients.length);
  else if (event.key === "ArrowUp") next = nextWheelIndex(activeWheelIndex, -1, patients.length);
  else if (event.key === "Home") next = patients.length ? 0 : -1;
  else if (event.key === "End") next = patients.length - 1;
  else if (event.key === "Enter" && activeWheelIndex >= 0) {
    selectPatient(patients[activeWheelIndex].patient_id);
    return;
  } else return;
  event.preventDefault();
  setActiveWheelIndex(next, true);
});

elements.wheelToggle.addEventListener("click", () => {
  const expanded = elements.wheelToggle.getAttribute("aria-expanded") === "true";
  elements.wheelToggle.setAttribute("aria-expanded", String(!expanded));
  elements.wheelToggle.setAttribute(
    "aria-label",
    expanded ? "Expand patient picker" : "Collapse patient picker",
  );
  elements.wheelToggle.textContent = expanded ? "⌄" : "⌃";
  elements.wheelRegion.hidden = expanded;
});

elements.search.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => loadPatients(), 250);
});

elements.loadMore.addEventListener("click", () => loadPatients({ append: true }));

elements.admission.addEventListener("change", () => {
  const session = selectedSession();
  if (session) session.admissionId = elements.admission.value;
});

elements.question.addEventListener("input", () => {
  const session = selectedSession();
  elements.question.style.height = "auto";
  elements.question.style.height = `${Math.min(elements.question.scrollHeight, 150)}px`;
  elements.send.disabled = !session || session.inFlight || elements.question.value.trim().length < 2;
});

elements.question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitQuestion(elements.question.value);
  }
});

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitQuestion(elements.question.value);
});

async function start(options) {
  if (!options || typeof options.getAccessToken !== "function") {
    setSessionStatus("A secure host session is required", "error");
    return;
  }
  clearAllState();
  getAccessToken = options.getAccessToken;
  unauthorizedCallback = options.onUnauthorized;
  const displayName =
    typeof options.doctorDisplayName === "string" && options.doctorDisplayName.trim()
      ? options.doctorDisplayName.trim()
      : "Doctor";
  elements.greeting.textContent = `${greetingForHour(new Date().getHours())}, ${displayName}`;
  elements.search.disabled = false;
  await loadPatients();
}

async function bootstrapDevelopmentAuth() {
  try {
    const response = await fetch("/v1/runtime-config", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const config = await response.json();
    if (config.development_auth_enabled && typeof config.development_auth_url === "string") {
      developmentAuthUrl = config.development_auth_url.replace(/\/$/, "");
      showDevelopmentAccess();
    }
  } catch {
    // A hosting application can still initialize the page through DocAgentApp.start.
  }
}

elements.developmentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!developmentAuthUrl) return;
  const doctorId = elements.developmentDoctorId.value.trim();
  const patientIds = [
    ...new Set(
      elements.developmentPatientIds.value
        .split(/[\s,]+/)
        .map((value) => value.trim())
        .filter(Boolean),
    ),
  ];
  if (!doctorId || patientIds.length === 0) {
    elements.developmentStatus.textContent = "Enter a doctor ID and at least one patient ID.";
    return;
  }
  elements.developmentSubmit.disabled = true;
  elements.developmentStatus.textContent = "Creating a temporary local session…";
  try {
    const response = await fetch(`${developmentAuthUrl}/v1/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doctor_id: doctorId, patient_ids: patientIds }),
    });
    if (!response.ok) throw new Error("TOKEN_REQUEST_FAILED");
    const data = await response.json();
    if (typeof data.access_token !== "string" || !data.access_token) {
      throw new Error("TOKEN_RESPONSE_INVALID");
    }
    developmentToken = data.access_token;
    elements.developmentAccess.hidden = true;
    await start({
      getAccessToken: async () => developmentToken,
      doctorDisplayName: doctorId,
      onUnauthorized: () => showDevelopmentAccess("The local session expired. Start another session."),
    });
  } catch {
    developmentToken = null;
    elements.developmentStatus.textContent =
      "The local authentication server is unavailable. Confirm it is running on this PC.";
  } finally {
    elements.developmentSubmit.disabled = false;
  }
});

renderSuggestions();
renderWheel();
renderWorkspace();
window.DocAgentApp = Object.freeze({ start });
bootstrapDevelopmentAuth();
