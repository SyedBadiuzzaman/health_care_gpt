export const SUGGESTED_QUESTIONS = Object.freeze([
  "Summarize the recorded history.",
  "Which medications, doses, and routes were recorded?",
  "What microbiology specimens, tests, and organisms were recorded?",
  "Summarize the recorded DRG descriptions and severity.",
  "Which encounter facts were recorded?",
]);

export function greetingForHour(hour) {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function createPatientSession(patient) {
  return {
    patient,
    admissionId: "",
    messages: [],
    inFlight: false,
    unread: false,
  };
}

export function mergePatientPages(current, incoming) {
  const byId = new Map(current.map((patient) => [patient.patient_id, patient]));
  for (const patient of incoming) byId.set(patient.patient_id, patient);
  return [...byId.values()];
}

export function responseState(status) {
  const states = {
    answered: { label: "History summary", tone: "answer" },
    blocked: { label: "Safety boundary", tone: "blocked" },
    no_history: { label: "No history found", tone: "empty" },
  };
  return states[status] || { label: "Service response", tone: "error" };
}

export function nextWheelIndex(currentIndex, direction, length) {
  if (length === 0) return -1;
  return Math.min(Math.max(currentIndex + direction, 0), length - 1);
}
