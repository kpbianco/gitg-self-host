(() => {
  "use strict";

  const showForState = (stateControl, valueContainer) => {
    if (!stateControl || !valueContainer) return;
    const hasError = Boolean(valueContainer.querySelector(".errorlist"));
    valueContainer.hidden = stateControl.value !== "provided" && !hasError;
  };

  document.querySelectorAll("[data-personal-os-section]").forEach((container) => {
    const sectionId = container.dataset.personalOsSection;
    const state = document.querySelector(`#id_${sectionId}_state`);
    showForState(state, container);
    state?.addEventListener("change", () => showForState(state, container));
  });

  document.querySelectorAll("[data-state-value]").forEach((container) => {
    const factorId = container.dataset.stateValue;
    const state = document.querySelector(`#id_${factorId}_state`);
    showForState(state, container);
    state?.addEventListener("change", () => showForState(state, container));
  });

  const practiceForm = document.querySelector("[data-practice-context-form]");
  if (practiceForm) {
    const modeControls = [...practiceForm.querySelectorAll('input[name="mode"]')];
    const updateMode = () => {
      const selected = modeControls.find((control) => control.checked)?.value || "";
      practiceForm.querySelectorAll("[data-context-mode]").forEach((section) => {
        section.hidden = section.dataset.contextMode !== selected;
      });
    };
    modeControls.forEach((control) => control.addEventListener("change", updateMode));
    updateMode();
  }

  const firstInvalid = document.querySelector('[aria-invalid="true"]');
  firstInvalid?.focus();
})();
