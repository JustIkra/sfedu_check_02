(function () {
  document.addEventListener("DOMContentLoaded", () => {
    // Modal confirm
    const modalOverlay = document.getElementById("app-modal");
    const modalMessage = modalOverlay ? modalOverlay.querySelector(".modal__message") : null;
    const modalOk = modalOverlay ? modalOverlay.querySelector(".modal__ok") : null;
    const modalCancel = modalOverlay ? modalOverlay.querySelector(".modal__cancel") : null;
    let pendingForm = null;

    function openConfirm(message, form) {
      if (!modalOverlay || !modalMessage || !modalOk || !modalCancel) {
        return window.confirm(message);
      }
      modalMessage.textContent = message || "Подтвердите действие";
      modalOverlay.hidden = false;
      pendingForm = form || null;
    }

    function closeConfirm() {
      if (modalOverlay) {
        modalOverlay.hidden = true;
      }
      pendingForm = null;
    }

    if (modalOk && modalCancel) {
      modalOk.addEventListener("click", () => {
        if (pendingForm) {
          const form = pendingForm;
          pendingForm = null;
          modalOverlay.hidden = true;
          form.submit();
        } else {
          closeConfirm();
        }
      });
      modalCancel.addEventListener("click", () => closeConfirm());
      if (modalOverlay) {
        modalOverlay.addEventListener("click", (e) => {
          if (e.target === modalOverlay) closeConfirm();
        });
      }
    }

    document.querySelectorAll("form.js-confirm").forEach((form) => {
      form.addEventListener("submit", (e) => {
        const message = form.dataset.confirmMessage || "Подтвердить действие?";
        e.preventDefault();
        openConfirm(message, form);
      });
    });

    const form = document.querySelector(".auto-checker-form");
    const progressPanel = document.getElementById("auto-check-progress");

    if (!form || !progressPanel) {
      return;
    }

    const datasetSelect = form.querySelector("select[name='dataset']");
    const submitButton = form.querySelector("button[type='submit']");
    const stageEl = progressPanel.querySelector(".progress-stage");
    const countEl = progressPanel.querySelector(".progress-count");
    const barTrack = progressPanel.querySelector(".progress-bar-track");
    const barFill = progressPanel.querySelector(".progress-bar-fill");
    const messageEl = progressPanel.querySelector(".progress-message");
    const downloadSlot = progressPanel.querySelector("[data-download-slot]");

    let pollTimer = null;
    let currentJobId = progressPanel.dataset.activeJob || null;

    function setProgressWidth(value) {
      const width = Math.max(0, Math.min(100, Number(value) || 0));
      barFill.style.width = `${width}%`;
      barTrack.setAttribute("aria-valuenow", String(Math.round(width)));
    }

    function clearPolling() {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    function resetDownloadArea() {
      if (!downloadSlot) {
        return;
      }
      downloadSlot.innerHTML = "";
      downloadSlot.hidden = true;
    }

    function renderDownloadLink(url, text, title) {
      if (!downloadSlot) {
        return;
      }
      const link = document.createElement("a");
      link.className = "button";
      link.href = url;
      link.textContent = text;
      if (title) link.title = title;
      link.rel = "noopener";
      downloadSlot.appendChild(link);
      downloadSlot.hidden = false;
    }

    function schedulePolling(jobId) {
      clearPolling();
      if (!jobId) {
        return;
      }
      currentJobId = jobId;
      progressPanel.dataset.activeJob = jobId;
      poll(jobId);
      pollTimer = setInterval(() => poll(jobId), 2000);
    }

    function handleError(message) {
      clearPolling();
      stageEl.textContent = "Ошибка";
      messageEl.textContent = message;
      countEl.textContent = "";
      setProgressWidth(0);
      resetDownloadArea();
      submitButton.disabled = false;
      currentJobId = null;
      progressPanel.dataset.activeJob = "";
    }

    function startJob(dataset) {
      fetch(form.action, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ dataset }),
      })
        .then((response) =>
          response
            .json()
            .catch(() => ({}))
            .then((data) => ({ response, data }))
        )
        .then(({ response, data }) => {
          if (response.status === 409 && data.job_id) {
            stageEl.textContent = "Проверка выполняется";
            messageEl.textContent = data.error || "Уже запущена проверка для этого архива.";
            schedulePolling(data.job_id);
            return;
          }

          if (!response.ok || !data.job_id) {
            throw new Error(data.error || "Не удалось запустить проверку.");
          }

          schedulePolling(data.job_id);
        })
        .catch((error) => {
          handleError(error.message);
        });
    }

    function poll(jobId) {
      const statusTemplate = progressPanel.dataset.statusTemplate;
      if (!statusTemplate) {
        return;
      }
      const statusUrl = statusTemplate.replace("__JOB__", jobId);
      fetch(statusUrl, {
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then((response) =>
          response
            .json()
            .catch(() => ({}))
            .then((data) => ({ response, data }))
        )
        .then(({ response, data }) => {
          if (!response.ok) {
            throw new Error(data.error || "Не удалось получить статус проверки.");
          }
          updatePanel(data, jobId);
        })
        .catch((error) => {
          handleError(error.message);
        });
    }

    function updatePanel(data, jobId) {
      const {
        status,
        stage,
        message,
        completed,
        total,
        download_name: downloadName,
        result_ready: resultReady,
        error,
      } = data;

      resetDownloadArea();

      if (typeof completed === "number" && typeof total === "number" && total > 0) {
        countEl.textContent = `${completed} из ${total}`;
        setProgressWidth((completed / total) * 100);
      } else if (stage === "generating_summary") {
        countEl.textContent = "";
        setProgressWidth(90);
      } else if (status === "finished") {
        countEl.textContent = "";
        setProgressWidth(100);
      } else if (!currentJobId) {
        countEl.textContent = "";
        setProgressWidth(0);
      }

      const fallbackMessage = message || error;
      if (status === "failed") {
        messageEl.textContent = fallbackMessage || "Проверка завершилась с ошибкой.";
        stageEl.textContent = "Ошибка";
        handleError(messageEl.textContent);
        return;
      }

      stageEl.textContent = message || stage || "Проверка";
      if (status === "finished") {
        clearPolling();
        messageEl.textContent = "Проверка завершена, отчёт готов к скачиванию.";
        submitButton.disabled = false;
        currentJobId = null;
        progressPanel.dataset.activeJob = "";
        const downloadTemplate = progressPanel.dataset.downloadTemplate;
        if (downloadTemplate && resultReady) {
          const downloadUrl = downloadTemplate.replace("__JOB__", jobId);
          const fullLabel = downloadName
            ? `Скачать отчёт (${downloadName})`
            : "Скачать отчёт";
          const truncated = (() => {
            const maxLen = 70; // keep button compact
            const input = fullLabel;
            if (!input || input.length <= maxLen) return input;
            const head = input.slice(0, Math.ceil(maxLen * 0.6));
            const tail = input.slice(-Math.floor(maxLen * 0.3));
            return `${head}…${tail}`;
          })();
          renderDownloadLink(downloadUrl, truncated, fullLabel);
        }
        return;
      }

      if (!messageEl.textContent || messageEl.textContent === "Панель прогресса появится при запуске проверки.") {
        messageEl.textContent = message || "Проверка выполняется";
      } else if (message) {
        messageEl.textContent = message;
      }
    }

    form.addEventListener("submit", (event) => {
      if (!datasetSelect) {
        return;
      }

      event.preventDefault();

      const dataset = datasetSelect.value;
      if (!dataset) {
        handleError("Выберите архив для проверки.");
        return;
      }

      progressPanel.hidden = false;
      submitButton.disabled = true;
      stageEl.textContent = "Подготовка";
      messageEl.textContent = "Запуск проверки...";
      countEl.textContent = "";
      setProgressWidth(5);
      resetDownloadArea();

      startJob(dataset);
    });

    if (currentJobId) {
      progressPanel.hidden = false;
      submitButton.disabled = true;
      schedulePolling(currentJobId);
    }
  });
})();
