const studyPlanForm = document.getElementById("study-plan-form");
const studyPlanOutput = document.getElementById("study-plan-output");
const summaryForm = document.getElementById("summary-form");
const summaryOutput = document.getElementById("summary-output");
const moodForm = document.getElementById("mood-form");
const moodOutput = document.getElementById("mood-output");

async function postJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.error || response.statusText;
    throw new Error(message);
  }
  return data;
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

studyPlanForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  studyPlanOutput.textContent = "Generating plan...";
  try {
    const profile = studyPlanForm.profile.value.trim();
    const courses = studyPlanForm.courses.value.trim();
    const preferences = studyPlanForm.preferences.value.trim();
    const payload = {
      profile: profile ? JSON.parse(profile) : {},
      courses: courses ? JSON.parse(courses) : [],
      timeframe: studyPlanForm.timeframe.value || "Upcoming term",
      preferences: preferences ? JSON.parse(preferences) : undefined,
    };
    const result = await postJSON("/api/ai/study-plan", payload);
    studyPlanOutput.textContent = pretty(result);
  } catch (error) {
    console.error(error);
    studyPlanOutput.textContent = `Error: ${error.message}`;
  }
});

summaryForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  summaryOutput.textContent = "Summarising...";
  try {
    const payload = {
      text: summaryForm["summary-text"].value,
      audience: summaryForm["summary-audience"].value || undefined,
    };
    const result = await postJSON("/api/ai/summaries", payload);
    summaryOutput.textContent = pretty(result);
  } catch (error) {
    console.error(error);
    summaryOutput.textContent = `Error: ${error.message}`;
  }
});

moodForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  moodOutput.textContent = "Classifying...";
  try {
    const entries = moodForm["mood-entries"].value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    const result = await postJSON("/api/ai/mood-check", { entries });
    moodOutput.textContent = pretty(result);
  } catch (error) {
    console.error(error);
    moodOutput.textContent = `Error: ${error.message}`;
  }
});

(async function checkStatus() {
  try {
    const response = await fetch("/api/ai/status");
    const data = await response.json();
    const banner = document.createElement("div");
    banner.className = data.enabled ? "status enabled" : "status disabled";
    banner.innerHTML = data.enabled
      ? `AI services ready — model <strong>${data.model}</strong>`
      : "AI services disabled — set OPENAI_API_KEY";
    document.body.prepend(banner);
  } catch (error) {
    console.warn("Unable to fetch AI status", error);
  }
})();
