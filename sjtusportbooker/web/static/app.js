const state = {
  venues: [],
  targetDates: [],
  streamStarted: false,
  pollTimer: null,
  activeTaskPollTimer: null,
};

const defaultTitle = document.title;

function setButtonDisabled(selector, disabled) {
  const node = document.querySelector(selector);
  if (!node) {
    return;
  }
  node.disabled = disabled;
}

function stopActiveTaskPolling() {
  if (state.activeTaskPollTimer) {
    clearInterval(state.activeTaskPollTimer);
    state.activeTaskPollTimer = null;
  }
}

function startActiveTaskPolling() {
  if (state.activeTaskPollTimer) {
    return;
  }
  state.activeTaskPollTimer = setInterval(() => {
    refreshStatus().catch(() => {});
  }, 1000);
}

function renderControls(status) {
  const busyStates = new Set(["starting", "running", "recovering", "stopping"]);
  const isBusy = busyStates.has(status.state);
  setButtonDisabled("#start-task", isBusy);
  setButtonDisabled("#test-login", isBusy);
  setButtonDisabled("#test-email", isBusy);
  setButtonDisabled("#stop-task", !isBusy);
  if (isBusy) {
    startActiveTaskPolling();
  } else {
    stopActiveTaskPolling();
  }
}

function setFeedback(message, tone = "success") {
  const node = document.querySelector("#feedback");
  node.hidden = !message;
  node.className = `feedback is-${tone}`;
  node.textContent = message;
}

function renderSuccessBanner(status) {
  const banner = document.querySelector("#success-banner");
  const success = status.state === "success";
  banner.hidden = !success;
  document.body.classList.toggle("is-success", success);
  document.title = success ? "抢票成功 | SJTU Appointment Console" : defaultTitle;
  if (success) {
    setFeedback("抢票成功，请尽快前往平台确认并支付。", "success");
  }
}

function parseCsvNumbers(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item))
    .filter((item) => !Number.isNaN(item));
}

function renderTargetDates() {
  const container = document.querySelector("#target-dates");
  if (!state.targetDates.length) {
    container.innerHTML = '<span class="date-empty">尚未选择日期</span>';
    return;
  }

  container.innerHTML = "";
  state.targetDates.forEach((date) => {
    const chip = document.createElement("span");
    chip.className = "date-chip";

    const text = document.createElement("span");
    text.textContent = date;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "date-remove";
    remove.dataset.date = date;
    remove.setAttribute("aria-label", `移除日期 ${date}`);
    remove.textContent = "×";

    chip.append(text, remove);
    container.appendChild(chip);
  });
}

function addTargetDate() {
  const picker = document.querySelector("#target-date-picker");
  const date = picker.value;
  if (!date) {
    setFeedback("请先选择一个日期", "error");
    return;
  }

  state.targetDates = [...new Set([...state.targetDates, date])].sort();
  picker.value = "";
  renderTargetDates();
  setFeedback("");
}

function collectConfig() {
  return {
    account: {
      username: document.querySelector("#username").value.trim(),
      password: document.querySelector("#password").value,
    },
    task: {
      venue: document.querySelector("#venue").value,
      venue_item: document.querySelector("#venue-item").value,
      target_dates: [...state.targetDates],
      times: parseCsvNumbers(document.querySelector("#times").value),
      concurrency: Number(document.querySelector("#concurrency").value || 1),
      headless: document.querySelector("#headless").checked,
      pre_poll_ms: Number(document.querySelector("#pre-poll").value || 1000),
      post_poll_ms: Number(document.querySelector("#post-poll").value || 500),
    },
    notification: {
      enabled: document.querySelector("#notification-enabled").checked,
      smtp_host: document.querySelector("#smtp-host").value.trim(),
      smtp_port: Number(document.querySelector("#smtp-port").value || 465),
      use_ssl: document.querySelector("#smtp-ssl").value === "true",
      sender: document.querySelector("#smtp-sender").value.trim(),
      password: document.querySelector("#smtp-password").value,
      receiver: document.querySelector("#smtp-receiver").value.trim(),
    },
  };
}

function updateVenueItems(selectedVenue, selectedItem = "") {
  const venueItemSelect = document.querySelector("#venue-item");
  const venue = state.venues.find((entry) => entry.name === selectedVenue);
  venueItemSelect.innerHTML = "";
  (venue?.items || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = item;
    if (item === selectedItem) {
      option.selected = true;
    }
    venueItemSelect.appendChild(option);
  });
}

function fillForm(config, venues) {
  state.venues = venues;
  const venueSelect = document.querySelector("#venue");
  venueSelect.innerHTML = "";
  venues.forEach((venue) => {
    const option = document.createElement("option");
    option.value = venue.name;
    option.textContent = venue.name;
    venueSelect.appendChild(option);
  });

  document.querySelector("#username").value = config.account.username || "";
  document.querySelector("#password").value = config.account.password || "";
  document.querySelector("#headless").checked = Boolean(config.task.headless);
  state.targetDates = [
    ...(config.task.target_dates || (config.task.target_date ? [config.task.target_date] : [])),
  ].sort();
  document.querySelector("#target-date-picker").value = "";
  renderTargetDates();
  document.querySelector("#times").value = (config.task.times || []).join(",");
  document.querySelector("#concurrency").value = config.task.concurrency ?? 1;
  document.querySelector("#pre-poll").value = config.task.pre_poll_ms ?? 1000;
  document.querySelector("#post-poll").value = config.task.post_poll_ms ?? 500;
  document.querySelector("#notification-enabled").checked = Boolean(config.notification.enabled);
  document.querySelector("#smtp-host").value = config.notification.smtp_host || "";
  document.querySelector("#smtp-port").value = config.notification.smtp_port ?? 465;
  document.querySelector("#smtp-ssl").value = String(config.notification.use_ssl ?? true);
  document.querySelector("#smtp-sender").value = config.notification.sender || "";
  document.querySelector("#smtp-password").value = config.notification.password || "";
  document.querySelector("#smtp-receiver").value = config.notification.receiver || "";

  const selectedVenue = config.task.venue || venues[0]?.name || "";
  venueSelect.value = selectedVenue;
  updateVenueItems(selectedVenue, config.task.venue_item);
}

function renderStatus(status) {
  const statusBox = document.querySelector(".status-box");
  statusBox.classList.remove("is-success", "is-error");
  if (status.state === "success") {
    statusBox.classList.add("is-success");
  } else if (status.state === "error") {
    statusBox.classList.add("is-error");
  }
  document.querySelector("#status-message").textContent = status.message || "Ready";
  document.querySelector("#status-meta").textContent = `状态: ${status.state} | 尝试次数: ${status.attempts ?? 0}`;
  renderSuccessBanner(status);
  renderControls(status);
}

function renderLogs(logs) {
  const container = document.querySelector("#logs");
  if (!logs.length) {
    container.innerHTML = '<div class="log-line">暂无日志</div>';
    return;
  }
  container.innerHTML = logs
    .map((entry) => `<div class="log-line"><span class="log-time">${entry.time}</span>${entry.message}</div>`)
    .join("");
  container.scrollTop = container.scrollHeight;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || data.error || "请求失败");
  }
  return data;
}

async function refreshStatus() {
  const payload = await fetchJson("/api/status");
  renderStatus(payload.status);
  renderLogs(payload.logs);
}

function startPolling() {
  if (state.pollTimer) {
    return;
  }
  state.pollTimer = setInterval(() => {
    refreshStatus().catch(() => {});
  }, 3000);
}

function startStream() {
  if (state.streamStarted || !window.EventSource) {
    startPolling();
    return;
  }

  const stream = new EventSource("/api/stream");
  state.streamStarted = true;

  stream.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    renderStatus(payload.status);
    renderLogs(payload.logs);
  };

  stream.onerror = () => {
    stream.close();
    state.streamStarted = false;
    startPolling();
    setTimeout(startStream, 3000);
  };
}

async function bootstrap() {
  const payload = await fetchJson("/api/bootstrap");
  fillForm(payload.config, payload.venues);
  renderStatus(payload.status);
  renderLogs(payload.logs);
}

async function invokeAction(url) {
  const payload = await fetchJson(url, {
    method: "POST",
    body: JSON.stringify(collectConfig()),
  });
  if (payload.message) {
    setFeedback(payload.message);
  }
  await refreshStatus();
}

async function runAction(action) {
  try {
    await action();
  } catch (error) {
    setFeedback(error.message || "请求失败", "error");
  }
}

document.querySelector("#venue").addEventListener("change", (event) => {
  updateVenueItems(event.target.value);
});

document.querySelector("#add-target-date").addEventListener("click", addTargetDate);

document.querySelector("#target-dates").addEventListener("click", (event) => {
  const button = event.target.closest(".date-remove");
  if (!button) {
    return;
  }
  state.targetDates = state.targetDates.filter((date) => date !== button.dataset.date);
  renderTargetDates();
});

document.querySelector("#test-login").addEventListener("click", () =>
  runAction(async () => {
    await invokeAction("/api/test-login");
  })
);

document.querySelector("#test-email").addEventListener("click", () =>
  runAction(async () => {
    await invokeAction("/api/test-email");
  })
);

document.querySelector("#start-task").addEventListener("click", () =>
  runAction(async () => {
    startActiveTaskPolling();
    await invokeAction("/api/start");
    await refreshStatus();
  })
);

document.querySelector("#stop-task").addEventListener("click", () =>
  runAction(async () => {
    await invokeAction("/api/stop");
    await refreshStatus();
  })
);

document.querySelector("#refresh-status").addEventListener("click", () =>
  runAction(async () => {
    await refreshStatus();
    setFeedback("状态已刷新");
  })
);

runAction(bootstrap);
startStream();
