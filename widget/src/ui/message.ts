import { formatTime, renderMarkdownLite } from "../utils";

const BOT_ICON = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg>`;

export interface FeedbackContext {
  apiUrl: string;
  workspaceId: string;
  conversationId: string;
  messageId: string;
}

export function createMessage(
  content: string,
  type: "user" | "bot",
  avatarUrl: string | null = null,
  feedbackContext: FeedbackContext | null = null
): { element: HTMLElement; updateContent: (html: string) => void; setFeedbackContext: (ctx: FeedbackContext) => void } {
  const msg = document.createElement("div");
  msg.className = `pulse-msg ${type}`;

  if (type === "bot") {
    const avatar = document.createElement("div");
    avatar.className = "pulse-msg-avatar";
    if (avatarUrl) {
      const img = document.createElement("img");
      img.src = avatarUrl;
      img.alt = "Bot";
      avatar.appendChild(img);
    } else {
      avatar.innerHTML = BOT_ICON;
    }
    msg.appendChild(avatar);
  }

  const wrapper = document.createElement("div");

  const bubble = document.createElement("div");
  bubble.className = "pulse-msg-bubble";
  if (type === "bot") {
    bubble.innerHTML = renderMarkdownLite(content);
  } else {
    bubble.textContent = content;
  }

  const time = document.createElement("div");
  time.className = "pulse-msg-time";
  time.textContent = formatTime(new Date());

  wrapper.appendChild(bubble);
  wrapper.appendChild(time);

  let currentFeedbackCtx: FeedbackContext | null = feedbackContext;

  if (type === "bot") {
    const copyBtn = document.createElement("button");
    copyBtn.className = "pulse-copy-btn";
    copyBtn.title = "Copy";
    copyBtn.textContent = "⎘";
    copyBtn.onclick = () => {
      const text = bubble.innerText || bubble.textContent || "";
      navigator.clipboard.writeText(text).catch(() => {});
    };
    wrapper.appendChild(copyBtn);

    const thumbsUp = document.createElement("button");
    thumbsUp.className = "pulse-feedback-btn";
    thumbsUp.title = "Helpful";
    thumbsUp.textContent = "👍";

    const thumbsDown = document.createElement("button");
    thumbsDown.className = "pulse-feedback-btn";
    thumbsDown.title = "Not helpful";
    thumbsDown.textContent = "👎";

    function submitFeedback(rating: string, up: HTMLButtonElement, down: HTMLButtonElement) {
      if (!currentFeedbackCtx) return;
      const { apiUrl, workspaceId, conversationId, messageId } = currentFeedbackCtx;
      up.disabled = true;
      down.disabled = true;
      up.style.opacity = rating === "thumbs_up" ? "1" : "0.3";
      down.style.opacity = rating === "thumbs_down" ? "1" : "0.3";
      fetch(
        `${apiUrl}/api/v1/workspaces/${workspaceId}/conversations/${conversationId}/messages/${messageId}/feedback`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rating }),
        }
      ).catch(() => {});
    }

    thumbsUp.addEventListener("click", () => submitFeedback("thumbs_up", thumbsUp, thumbsDown));
    thumbsDown.addEventListener("click", () => submitFeedback("thumbs_down", thumbsUp, thumbsDown));

    wrapper.appendChild(thumbsUp);
    wrapper.appendChild(thumbsDown);
  }

  msg.appendChild(wrapper);

  return {
    element: msg,
    updateContent(html: string) {
      bubble.innerHTML = html;
    },
    setFeedbackContext(ctx: FeedbackContext) {
      currentFeedbackCtx = ctx;
    },
  };
}
