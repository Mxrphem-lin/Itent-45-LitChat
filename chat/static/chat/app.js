(() => {
  const providerData = JSON.parse(document.getElementById("provider-data").textContent);
  const providerById = new Map(providerData.map((provider) => [provider.id, provider]));
  const providerSelect = document.getElementById("provider-select");
  const providerOrb = document.getElementById("provider-orb");
  const modelCaption = document.getElementById("model-caption");
  const simulationNote = document.querySelector(".simulation-note");
  const sidebar = document.getElementById("sidebar");
  const scrim = document.getElementById("mobile-scrim");
  const conversationList = document.getElementById("conversation-list");
  const historyCount = document.getElementById("history-count");
  const welcomePanel = document.getElementById("welcome-panel");
  const messageList = document.getElementById("message-list");
  const composerForm = document.getElementById("composer-form");
  const promptInput = document.getElementById("prompt-input");
  const sendButton = document.getElementById("send-button");
  const stopButton = document.getElementById("stop-button");
  const newChatButton = document.getElementById("new-chat");
  const deleteButton = document.getElementById("delete-chat");
  const logoutForm = document.getElementById("logout-form");
  const menuToggle = document.getElementById("menu-toggle");
  const toast = document.getElementById("toast");
  const topbarTitle = document.getElementById("topbar-title");
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

  let activeConversationId = null;
  let activeController = null;
  let activeLoadController = null;
  let activeAssistant = null;
  let creatingConversation = false;
  let toastTimer = null;
  let historyRequestSequence = 0;

  function selectedProvider() {
    return providerById.get(providerSelect.value);
  }

  function updateProviderPresentation() {
    const provider = selectedProvider();
    const initial = provider.label.charAt(0);
    providerOrb.textContent = initial;
    providerOrb.dataset.provider = provider.id;
    modelCaption.textContent = `Simulated · ${provider.model}`;
    simulationNote.textContent = provider.configured
      ? "Simulated by DeepSeek Flash at proxy.litechat.ai."
      : `${provider.key_name} is not set. Add it to .env to send a prompt.`;
    simulationNote.classList.toggle("needs-key", !provider.configured);
    sendButton.disabled = !provider.configured || isBusy();
  }

  function csrfHeaders(extra = {}) {
    return {
      "X-CSRFToken": csrfToken,
      ...extra,
    };
  }

  function closeSidebar() {
    sidebar.classList.remove("is-open");
    scrim.hidden = true;
    menuToggle.setAttribute("aria-expanded", "false");
  }

  function openSidebar() {
    sidebar.classList.add("is-open");
    scrim.hidden = false;
    menuToggle.setAttribute("aria-expanded", "true");
  }

  function showToast(message) {
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      toast.hidden = true;
    }, 5000);
  }

  function scrollToLatest() {
    const stage = document.querySelector(".conversation-stage");
    stage.scrollTop = stage.scrollHeight;
  }

  function makeMessage(role, content, providerId, status = "complete") {
    const row = document.createElement("article");
    row.className = `message-row ${role}`;
    row.dataset.status = status;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = role === "user" ? "Y" : "L";

    const body = document.createElement("div");
    body.className = "message-content";

    const meta = document.createElement("div");
    meta.className = "message-meta";
    const name = document.createElement("span");
    if (role === "user") {
      name.textContent = "You";
    } else {
      name.textContent = providerById.get(providerId)?.label || "LitChat";
      if (providerId && providerById.has(providerId)) {
        const badge = document.createElement("span");
        badge.className = "message-provider";
        badge.textContent = providerById.get(providerId).model;
        meta.append(name, badge);
      } else {
        meta.append(name);
      }
    }
    if (role === "user") meta.append(name);

    const text = document.createElement("div");
    text.className = "message-text";
    text.textContent = content;

    const statusLine = document.createElement("div");
    statusLine.className = "message-status";
    statusLine.hidden = true;

    body.append(meta, text, statusLine);
    row.append(avatar, body);

    return { row, text, statusLine };
  }

  function addMessage(role, content, providerId, status = "complete") {
    const message = makeMessage(role, content, providerId, status);
    messageList.append(message.row);
    return message;
  }

  function setMessageStatus(message, text, isError = false) {
    message.loading?.remove();
    message.loading = null;
    message.statusLine.textContent = text;
    message.statusLine.hidden = !text;
    message.row.dataset.status = isError ? "error" : "complete";
    message.row.classList.toggle("error", isError);
  }

  function showChat() {
    welcomePanel.hidden = true;
    messageList.hidden = false;
    deleteButton.hidden = !activeConversationId;
  }

  function showWelcome() {
    messageList.replaceChildren();
    messageList.hidden = true;
    welcomePanel.hidden = false;
    deleteButton.hidden = !activeConversationId;
    topbarTitle.textContent = activeConversationId
      ? "New conversation"
      : "A place to think out loud";
  }

  function renderConversationList(conversations) {
    conversationList.replaceChildren();
    historyCount.textContent = String(conversations.length);
    if (!conversations.length) {
      const empty = document.createElement("p");
      empty.className = "history-empty";
      empty.id = "history-empty";
      empty.textContent = "Your conversations will gather here.";
      conversationList.append(empty);
      return;
    }

    for (const conversation of conversations) {
      const button = document.createElement("button");
      button.className = "conversation-link";
      button.type = "button";
      button.dataset.conversationId = conversation.id;
      button.setAttribute("aria-current", conversation.id === activeConversationId ? "page" : "false");

      const glyph = document.createElement("span");
      glyph.className = "conversation-glyph";
      glyph.setAttribute("aria-hidden", "true");
      glyph.textContent = ">";

      const title = document.createElement("span");
      title.className = "conversation-title";
      title.textContent = conversation.title;
      button.append(glyph, title);
      conversationList.append(button);
    }
  }

  async function refreshConversationList() {
    const requestSequence = ++historyRequestSequence;
    try {
      const response = await fetch("/api/conversations/", { headers: { Accept: "application/json" } });
      if (!response.ok) return;
      const data = await response.json();
      if (requestSequence !== historyRequestSequence) return;
      renderConversationList(data.conversations);
    } catch (error) {
      if (error.name !== "AbortError") showToast("Could not refresh conversation history.");
    }
  }

  function cancelPendingLoad() {
    activeLoadController?.abort();
    activeLoadController = null;
  }

  function isBusy() {
    return Boolean(activeController || activeLoadController || creatingConversation);
  }

  async function createConversation() {
    cancelPendingLoad();
    creatingConversation = true;
    setBusy();
    try {
      const response = await fetch("/api/conversations/", {
        method: "POST",
        headers: csrfHeaders({ Accept: "application/json" }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not start a new conversation.");
      activeConversationId = data.id;
      showWelcome();
      await refreshConversationList();
      closeSidebar();
      promptInput.focus();
      return data;
    } finally {
      creatingConversation = false;
      setBusy();
    }
  }

  async function openConversation(conversationId) {
    if (activeController) {
      activeController.abort();
      activeController = null;
      activeAssistant = null;
    }
    cancelPendingLoad();
    const loadController = new AbortController();
    activeLoadController = loadController;
    activeConversationId = conversationId;
    setBusy();
    try {
      const response = await fetch(`/api/conversations/${conversationId}/`, {
        headers: { Accept: "application/json" },
        signal: loadController.signal,
      });
      const data = await response.json();
      if (activeLoadController !== loadController || activeConversationId !== conversationId) return;
      if (!response.ok) throw new Error(data.error || "Could not open that conversation.");

      messageList.replaceChildren();
      topbarTitle.textContent = data.title;
      showChat();
      for (const message of data.messages) {
        const item = addMessage(message.role, message.content, message.provider, message.status);
        if (message.status === "interrupted") {
          setMessageStatus(item, "Response interrupted. The partial text is saved.", true);
        } else if (message.status === "error") {
          setMessageStatus(item, "The response could not be completed.", true);
        }
      }
      await refreshConversationList();
      closeSidebar();
      scrollToLatest();
      promptInput.focus();
    } catch (error) {
      if (activeLoadController === loadController && error.name !== "AbortError") {
        activeConversationId = null;
        showWelcome();
        showToast(error.message || "Could not open that conversation.");
      }
    } finally {
      if (activeLoadController === loadController) {
        activeLoadController = null;
        setBusy();
      }
    }
  }

  async function deleteConversation() {
    if (!activeConversationId || isBusy()) return;
    cancelPendingLoad();
    const response = await fetch(`/api/conversations/${activeConversationId}/`, {
      method: "DELETE",
      headers: csrfHeaders({ Accept: "application/json" }),
    });
    if (!response.ok) {
      showToast("Could not delete this conversation.");
      return;
    }
    activeConversationId = null;
    activeAssistant = null;
    showWelcome();
    await refreshConversationList();
    promptInput.focus();
  }

  function resizeInput() {
    promptInput.style.height = "auto";
    promptInput.style.height = `${Math.min(promptInput.scrollHeight, 170)}px`;
  }

  function setBusy() {
    const busy = isBusy();
    sendButton.disabled = busy || !selectedProvider().configured;
    providerSelect.disabled = busy;
    newChatButton.disabled = busy;
    deleteButton.disabled = busy;
    stopButton.hidden = !activeController;
    sendButton.hidden = Boolean(activeController);
  }

  function parseSseFrame(frame) {
    const line = frame.split("\n").find((entry) => entry.startsWith("data:"));
    if (!line) return null;
    try {
      return JSON.parse(line.slice(5).trim());
    } catch {
      return null;
    }
  }

  async function consumeStream(response, assistant, controller) {
    if (!response.body) throw new Error("This browser could not read the streamed response.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finished = false;

    async function handleFrame(frame) {
      const event = parseSseFrame(frame);
      if (!event) return;
      if (event.type === "delta") {
        assistant.loading?.remove();
        assistant.loading = null;
        assistant.text.textContent += event.text;
        scrollToLatest();
      } else if (event.type === "done") {
        assistant.loading?.remove();
        assistant.loading = null;
        finished = true;
        assistant.row.dataset.status = "complete";
      } else if (event.type === "error") {
        finished = true;
        setMessageStatus(
          assistant,
          event.partial ? `${event.message} Partial text was saved.` : event.message,
          true,
        );
      }
    }

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        await handleFrame(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }

    if (buffer.trim()) await handleFrame(buffer);
    if (!finished && !controller.signal.aborted) {
      setMessageStatus(assistant, "The stream ended before completion. The partial text was saved.", true);
    }
  }

  async function sendMessage(content, userMessage) {
    const provider = selectedProvider();
    const conversationId = activeConversationId;
    const assistant = addMessage("assistant", "", provider.id, "streaming");
    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.setAttribute("aria-label", "Waiting for response");
    for (let index = 0; index < 3; index += 1) typing.append(document.createElement("span"));
    assistant.text.append(typing);
    assistant.loading = typing;
    activeAssistant = assistant;
    const controller = new AbortController();
    activeController = controller;
    setBusy();
    scrollToLatest();

    try {
      const response = await fetch(`/api/conversations/${conversationId}/messages/`, {
        method: "POST",
        signal: controller.signal,
        headers: csrfHeaders({ "Content-Type": "application/json", Accept: "text/event-stream" }),
        body: JSON.stringify({ provider: provider.id, content }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const error = new Error(data.error || "Could not send this message.");
        error.status = response.status;
        throw error;
      }
      await consumeStream(response, assistant, controller);
      await refreshConversationList();
    } catch (error) {
      if (activeConversationId !== conversationId) return;
      if (error.name === "AbortError") {
        setMessageStatus(assistant, "Response stopped. Any partial text was kept.", true);
      } else if (error.status === 503) {
        userMessage.row.remove();
        assistant.row.remove();
        promptInput.value = content;
        resizeInput();
        showToast(error.message);
      } else {
        setMessageStatus(assistant, error.message || "The response was interrupted.", true);
      }
    } finally {
      if (activeController === controller) {
        activeController = null;
        if (activeAssistant === assistant) activeAssistant = null;
        setBusy();
        promptInput.focus();
      }
    }
  }

  providerSelect.addEventListener("change", updateProviderPresentation);
  composerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const content = promptInput.value.trim();
    if (!content || isBusy()) return;
    const provider = selectedProvider();
    if (!provider.configured) {
      showToast(`Add ${provider.key_name} to .env, then restart LitChat.`);
      return;
    }
    if (!activeConversationId) {
      try {
        await createConversation();
      } catch (error) {
        showToast(error.message || "Could not start a new conversation.");
        return;
      }
    }
    promptInput.value = "";
    resizeInput();
    if (topbarTitle.textContent === "New conversation") {
      topbarTitle.textContent = content.replace(/\s+/g, " ").slice(0, 120);
    }
    const userMessage = addMessage("user", content, "");
    showChat();
    await sendMessage(content, userMessage);
  });

  promptInput.addEventListener("input", resizeInput);
  promptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      composerForm.requestSubmit();
    }
  });

  newChatButton.addEventListener("click", async () => {
    if (activeController) activeController.abort();
    activeConversationId = null;
    showWelcome();
    try {
      await createConversation();
    } catch (error) {
      showToast(error.message || "Could not start a new conversation.");
    }
  });

  deleteButton.addEventListener("click", deleteConversation);
  stopButton.addEventListener("click", () => activeController?.abort());
  logoutForm?.addEventListener("submit", () => {
    conversationList.replaceChildren();
    historyCount.textContent = "0";
    messageList.replaceChildren();
    messageList.hidden = true;
    welcomePanel.hidden = true;
    topbarTitle.textContent = "Signing out";
    document.querySelector(".sidebar-foot strong").textContent = "Signed out";
    document.querySelector(".account-name").textContent = "";
    document.querySelector(".account-avatar").textContent = "";
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) window.location.reload();
  });
  conversationList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-conversation-id]");
    if (creatingConversation) return;
    if (button) openConversation(button.dataset.conversationId);
  });

  document.querySelectorAll(".suggestion-card").forEach((button) => {
    button.addEventListener("click", () => {
      promptInput.value = button.dataset.prompt;
      resizeInput();
      promptInput.focus();
    });
  });

  menuToggle.addEventListener("click", () => {
    if (sidebar.classList.contains("is-open")) closeSidebar();
    else openSidebar();
  });
  scrim.addEventListener("click", closeSidebar);
  document.addEventListener("keydown", (event) => {
    if (
      event.key.toLowerCase() === "n" &&
      !event.metaKey && !event.ctrlKey && !event.altKey &&
      !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)
    ) {
      event.preventDefault();
      newChatButton.click();
    }
    if (event.key === "Escape") closeSidebar();
  });

  updateProviderPresentation();
  promptInput.focus();
})();
