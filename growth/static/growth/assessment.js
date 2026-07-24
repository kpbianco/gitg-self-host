(function () {
  "use strict";

  const app = document.getElementById("assessment-app");
  if (!app || !window.GroundedGrowthAssessment) return;

  const spec = JSON.parse(document.getElementById("assessment-spec").textContent);
  const model = JSON.parse(document.getElementById("assessment-model").textContent);
  const assessment = spec.assessment;
  const engine = window.GroundedGrowthAssessment;
  const storageKey = app.dataset.storageKey;
  const saveUrl = app.dataset.saveUrl;
  const coreItems = assessment.core_items;
  const coreIds = coreItems.map((item) => item.id);
  const allItems = [
    ...coreItems,
    ...assessment.adaptive_capability_clarifiers,
    ...assessment.adaptive_orientation_clarifiers,
  ];
  const itemMap = Object.fromEntries(allItems.map((item) => [item.id, item]));
  const orientationNames = Object.fromEntries(
    model.orientation_modes.map((item) => [item.slug, item.name]),
  );

  const byId = (id) => document.getElementById(id);
  const stages = {
    intro: byId("assessment-intro"),
    quiz: byId("assessment-quiz"),
    clarify: byId("assessment-clarify"),
    results: byId("assessment-results"),
  };
  const importPanel = app.querySelector(".assessment-import");
  const csrfToken = app.querySelector("[name=csrfmiddlewaretoken]").value;
  const startButton = byId("assessment-start");
  const resetButton = byId("assessment-reset");
  const importButton = byId("assessment-import-submit");
  const count = byId("assessment-count");
  const autosave = byId("assessment-autosave");
  const progressFill = byId("assessment-progress-fill");
  const prompt = byId("assessment-prompt");
  const scale = byId("assessment-scale");
  const backButton = byId("assessment-back");
  const nextButton = byId("assessment-next");
  const saveStatus = byId("assessment-save-status");
  const saveError = byId("assessment-save-error");
  const profileLink = byId("assessment-profile-link");
  const retrySaveButton = byId("assessment-retry-save");

  function newSubmissionId() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
      const random = Math.floor(Math.random() * 16);
      const value = character === "x" ? random : (random & 3) | 8;
      return value.toString(16);
    });
  }

  function freshState() {
    return {
      assessment_version: assessment.version,
      responses: {},
      timings_seconds: {},
      index: 0,
      phase: "core",
      source: "application",
      submission_id: newSubmissionId(),
    };
  }

  function loadState() {
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey));
      if (
        stored &&
        stored.assessment_version === assessment.version &&
        typeof stored.responses === "object"
      ) {
        return stored;
      }
    } catch (_error) {
      localStorage.removeItem(storageKey);
    }
    return freshState();
  }

  let state = loadState();
  let order =
    state.phase === "clarifier" && Array.isArray(state.clarifier_order)
      ? state.clarifier_order
      : assessment.display_order;
  let itemStartedAt = performance.now();
  let currentTimedItem = null;

  function saveLocal() {
    localStorage.setItem(storageKey, JSON.stringify(state));
    autosave.textContent = "Saved locally";
  }

  function show(stageName) {
    Object.entries(stages).forEach(([name, element]) => {
      element.classList.toggle("hidden", name !== stageName);
    });
    importPanel.classList.toggle("hidden", stageName !== "intro");
  }

  function responseScale(item) {
    if (item.type.startsWith("orientation")) return assessment.response_scales.orientation;
    if (item.type === "response_quality") return assessment.response_scales.response_quality;
    return assessment.response_scales.capability;
  }

  function selectAnswer(itemId, value) {
    state.responses[itemId] = value;
    saveLocal();
    scale.querySelectorAll(".assessment-answer").forEach((button) => {
      button.classList.toggle("selected", button.dataset.value === String(value));
    });
    nextButton.disabled = false;
  }

  function answerButton(item, value, label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "assessment-answer";
    if (state.responses[item.id] === value) button.classList.add("selected");
    button.dataset.value = String(value);

    const strong = document.createElement("strong");
    strong.textContent = value === "NA" ? "N/A" : String(value);
    button.append(strong, document.createTextNode(` — ${label}`));
    button.addEventListener("click", () => selectAnswer(item.id, value));
    return button;
  }

  function renderQuestion(resetClock) {
    const itemId = order[state.index];
    const item = itemMap[itemId];
    if (!item) {
      showResults();
      return;
    }

    count.textContent = `${state.index + 1} of ${order.length}`;
    progressFill.style.width = `${(100 * (state.index + 1)) / order.length}%`;
    prompt.textContent = item.prompt;
    scale.replaceChildren();
    const labels = responseScale(item);
    for (let value = 1; value <= 5; value += 1) {
      scale.append(answerButton(item, value, labels[String(value)]));
    }
    if (item.allow_not_applicable) {
      scale.append(
        answerButton(item, "NA", "Not applicable or insufficient experience"),
      );
    }

    backButton.disabled = state.index === 0;
    nextButton.disabled = state.responses[itemId] == null;
    nextButton.textContent = state.index === order.length - 1 ? "Finish" : "Next";
    if (resetClock || currentTimedItem !== itemId) {
      itemStartedAt = performance.now();
      currentTimedItem = itemId;
    }
  }

  function captureTiming() {
    const itemId = order[state.index];
    if (currentTimedItem !== itemId) return;
    const elapsed = Math.max(0, (performance.now() - itemStartedAt) / 1000);
    state.timings_seconds[itemId] =
      Number(state.timings_seconds[itemId] || 0) + elapsed;
    currentTimedItem = null;
  }

  function beginOrResume() {
    if (state.phase === "complete" && state.last_result) {
      renderResults(state.last_result, state.display_share_code);
      show("results");
      persistResult();
      return;
    }
    if (state.phase === "core_complete") {
      show("clarify");
      return;
    }
    order =
      state.phase === "clarifier" && Array.isArray(state.clarifier_order)
        ? state.clarifier_order
        : assessment.display_order;
    state.index = Math.min(Number(state.index || 0), order.length - 1);
    show("quiz");
    renderQuestion(true);
  }

  function clearSavedAssessment() {
    if (
      Object.keys(state.responses || {}).length > 0 &&
      !window.confirm("Clear the saved assessment on this device?")
    ) {
      return;
    }
    localStorage.removeItem(storageKey);
    state = freshState();
    order = assessment.display_order;
    startButton.textContent = "Begin assessment";
    show("intro");
  }

  function startClarifiers() {
    const preliminary = engine.scoreAssessment(spec, model, state);
    const selected = [
      ...preliminary.suggested_capability_clarifiers.map(
        (item) => item.clarifier_id,
      ),
      ...preliminary.suggested_orientation_clarifiers.map(
        (item) => item.clarifier_id,
      ),
    ];
    if (selected.length === 0) {
      showResults();
      return;
    }
    state.phase = "clarifier";
    state.clarifier_order = selected;
    state.index = 0;
    order = selected;
    saveLocal();
    show("quiz");
    renderQuestion(true);
  }

  function element(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function metricRow(title, primary, secondary) {
    const row = element("div", "result-card");
    const content = element("div", "");
    content.append(element("strong", "", title), element("span", "", secondary));
    row.append(content, element("b", "", primary));
    return row;
  }

  function renderResults(result, shareCode) {
    const quality = result.response_quality;
    const duration = Math.round(quality.total_timed_seconds || 0);
    const median =
      quality.median_seconds_per_item == null
        ? "Not available"
        : `${quality.median_seconds_per_item.toFixed(1)} seconds per item`;
    const qualityPanel = byId("assessment-quality");
    qualityPanel.replaceChildren(
      element(
        "strong",
        "",
        `Response-quality modifier: ${Math.round(quality.modifier * 100)}%`,
      ),
      element("p", "muted", `${duration} timed seconds · Median ${median}`),
    );
    if (quality.flags && quality.flags.length) {
      qualityPanel.append(
        element(
          "p",
          "fine-print",
          `Quality note: ${quality.flags.join(" ")}`,
        ),
      );
    }

    const orientations = byId("assessment-orientations");
    orientations.replaceChildren();
    Object.entries(result.orientations.scores)
      .sort((left, right) => (right[1].score || 0) - (left[1].score || 0))
      .forEach(([slug, output]) => {
        orientations.append(
          metricRow(
            orientationNames[slug] || slug,
            `${Math.round((output.score || 0) * 100)}%`,
            `${Math.round((output.confidence || 0) * 100)}% evidence confidence`,
          ),
        );
      });

    const archetypes = byId("assessment-archetypes");
    archetypes.replaceChildren();
    result.archetypes.slice(0, 3).forEach((output) => {
      archetypes.append(
        metricRow(
          output.name,
          `${Math.round((output.raw_fit || 0) * 100)}%`,
          output.orientations.join(" + "),
        ),
      );
    });

    const needs = byId("assessment-needs");
    needs.replaceChildren();
    result.lever_need_ranking.slice(0, 3).forEach((ranked) => {
      const output = result.levers[ranked.lever_id];
      const estimate =
        output.estimate == null
          ? "Estimate unavailable"
          : `${Math.round(output.estimate * 100)}% calibrated estimate`;
      needs.append(
        metricRow(
          output.name,
          ranked.score == null
            ? "Need unavailable"
            : `${Math.round(ranked.score * 100)}% need`,
          `${estimate} · ${Math.round((output.confidence || 0) * 100)}% confidence`,
        ),
      );
    });

    byId("assessment-share-code").value = shareCode;
  }

  function payloadShareCode() {
    return state.source === "share_code"
      ? state.original_share_code
      : state.display_share_code;
  }

  async function persistResult() {
    if (!state.last_result) return;
    saveStatus.textContent = "Saving…";
    saveStatus.classList.remove("status-pill-ready");
    saveError.classList.add("hidden");
    retrySaveButton.classList.add("hidden");
    try {
      const response = await fetch(saveUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          submission_id: state.submission_id,
          source: state.source || "application",
          assessment_version: assessment.version,
          responses: state.responses,
          timings_seconds: state.timings_seconds || {},
          total_seconds: state.total_seconds ?? null,
          result: state.last_result,
          share_code: payloadShareCode(),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The assessment could not be saved.");
      state.saved_run_id = data.run_id;
      state.saved_profile_url = data.profile_url;
      saveLocal();
      saveStatus.textContent = data.created ? "Saved" : "Already saved";
      saveStatus.classList.add("status-pill-ready");
      profileLink.href = data.profile_url;
      profileLink.classList.remove("hidden");
    } catch (error) {
      saveStatus.textContent = "Save failed";
      saveError.textContent = error.message;
      saveError.classList.remove("hidden");
      retrySaveButton.classList.remove("hidden");
    }
  }

  function showResults() {
    if (Object.keys(state.timings_seconds || {}).length) {
      state.total_seconds = Object.values(state.timings_seconds).reduce(
        (total, value) => total + Number(value || 0),
        0,
      );
    }
    const result = engine.scoreAssessment(spec, model, state);
    const displayShareCode = engine.encodeShareCode(spec, state);
    state.phase = "complete";
    state.last_result = result;
    state.display_share_code = displayShareCode;
    saveLocal();
    renderResults(result, displayShareCode);
    show("results");
    persistResult();
  }

  function importShareCode() {
    const importCode = byId("assessment-import-code").value.trim();
    const importError = byId("assessment-import-error");
    importError.classList.add("hidden");
    try {
      const decoded = engine.decodeShareCode(spec, importCode);
      const missingCore = coreIds.filter((itemId) => decoded.responses[itemId] == null);
      if (missingCore.length) {
        throw new Error("The share code does not contain all 50 required core answers.");
      }
      state = freshState();
      state.source = "share_code";
      state.original_share_code = importCode;
      state.responses = decoded.responses;
      state.timings_seconds = {};
      state.total_seconds = decoded.total_seconds ?? null;
      showResults();
    } catch (error) {
      importError.textContent = `This share code could not be imported: ${error.message}`;
      importError.classList.remove("hidden");
    }
  }

  startButton.addEventListener("click", beginOrResume);
  resetButton.addEventListener("click", clearSavedAssessment);
  backButton.addEventListener("click", () => {
    captureTiming();
    if (state.index > 0) state.index -= 1;
    saveLocal();
    renderQuestion(true);
  });
  nextButton.addEventListener("click", () => {
    captureTiming();
    if (state.index < order.length - 1) {
      state.index += 1;
      saveLocal();
      renderQuestion(true);
      return;
    }
    if (state.phase === "core") {
      state.phase = "core_complete";
      state.index = 0;
      saveLocal();
      show("clarify");
      return;
    }
    showResults();
  });
  byId("assessment-clarify-start").addEventListener("click", startClarifiers);
  byId("assessment-clarify-skip").addEventListener("click", showResults);
  importButton.addEventListener("click", importShareCode);
  retrySaveButton.addEventListener("click", persistResult);
  byId("assessment-copy").addEventListener("click", async () => {
    const shareCodeField = byId("assessment-share-code");
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(shareCodeField.value);
    } else {
      shareCodeField.focus();
      shareCodeField.select();
      document.execCommand("copy");
    }
    byId("assessment-copy").textContent = "Copied";
  });
  byId("assessment-retake").addEventListener("click", () => {
    localStorage.removeItem(storageKey);
    window.location.reload();
  });

  document.addEventListener("keydown", (event) => {
    if (stages.quiz.classList.contains("hidden")) return;
    const itemId = order[state.index];
    const item = itemMap[itemId];
    if (["1", "2", "3", "4", "5"].includes(event.key)) {
      selectAnswer(itemId, Number(event.key));
      event.preventDefault();
    } else if (
      (event.key === "n" || event.key === "N") &&
      item.allow_not_applicable
    ) {
      selectAnswer(itemId, "NA");
      event.preventDefault();
    } else if (event.key === "Enter" && !nextButton.disabled) {
      nextButton.click();
      event.preventDefault();
    } else if (event.key === "ArrowLeft" && !backButton.disabled) {
      backButton.click();
      event.preventDefault();
    }
  });

  window.GroundedGrowthAssessmentApp = {
    completeWithState(nextState) {
      state = {
        ...freshState(),
        ...nextState,
        assessment_version: assessment.version,
      };
      showResults();
    },
    getState() {
      return JSON.parse(JSON.stringify(state));
    },
  };

  if (Object.keys(state.responses || {}).length) startButton.textContent = "Resume assessment";
  startButton.disabled = false;
  resetButton.disabled = false;
  importButton.disabled = false;
  byId("assessment-load-status").textContent = "Scored locally on this device";
  show("intro");
})();
