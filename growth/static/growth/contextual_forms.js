(function () {
  "use strict";

  function fieldWrapper(control) {
    return control.closest(".form-field");
  }

  function setFieldAvailable(control, available) {
    const wrapper = fieldWrapper(control);
    if (!wrapper) {
      return;
    }
    const hasError = Boolean(wrapper.querySelector(".form-error"));
    wrapper.hidden = !available && !hasError;
  }

  function configureFeedbackForm() {
    const stageControl = document.querySelector("[data-feedback-stage-control]");
    if (!stageControl) {
      return;
    }
    const scopedControls = document.querySelectorAll("[data-feedback-stages]");

    function updateFeedbackFields() {
      const selectedStage = stageControl.value;
      for (const control of scopedControls) {
        const stages = control.dataset.feedbackStages.split(/\s+/).filter(Boolean);
        setFieldAvailable(control, Boolean(selectedStage) && stages.includes(selectedStage));
      }
    }

    stageControl.addEventListener("change", updateFeedbackFields);
    updateFeedbackFields();
  }

  function configureCheckInForm() {
    const actionControl = document.querySelector("[data-check-in-action-control]");
    const mappingElement = document.getElementById("check-in-action-observations");
    if (!actionControl || !mappingElement) {
      return;
    }
    const actionMap = JSON.parse(mappingElement.textContent);
    const observationControls = document.querySelectorAll("[data-check-in-observation]");
    const prompt = document.querySelector("[data-check-in-action-prompt]");

    function updateObservationFields() {
      const selectedAction = actionControl.value;
      const relevant = new Set(actionMap[selectedAction] || []);
      for (const control of observationControls) {
        setFieldAvailable(
          control,
          Boolean(selectedAction) && relevant.has(control.dataset.checkInObservation),
        );
      }
      if (prompt) {
        prompt.hidden = Boolean(selectedAction);
      }
    }

    actionControl.addEventListener("change", updateObservationFields);
    updateObservationFields();
  }

  configureFeedbackForm();
  configureCheckInForm();
})();
