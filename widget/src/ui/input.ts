const SEND_ICON = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
const MIC_ICON = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.76V20c0 .55.45 1 1 1s1-.45 1-1v-2.1c3.02-.41 5.42-2.76 5.91-5.76.1-.6-.39-1.14-1-1.14z"/></svg>`;

export function createInput(
  placeholder: string,
  onSend: (message: string) => void
): { element: HTMLElement; setDisabled: (disabled: boolean) => void; focus: () => void } {
  const container = document.createElement("div");
  container.className = "pulse-input-area";

  const input = document.createElement("textarea");
  input.className = "pulse-input";
  input.placeholder = placeholder;
  input.rows = 1;

  const sendBtn = document.createElement("button");
  sendBtn.className = "pulse-send-btn";
  sendBtn.setAttribute("aria-label", "Send");
  sendBtn.innerHTML = SEND_ICON;

  const micBtn = document.createElement("button");
  micBtn.className = "pulse-mic-btn";
  micBtn.setAttribute("aria-label", "Voice input");
  micBtn.innerHTML = MIC_ICON;

  function send() {
    const text = input.value.trim();
    if (!text) return;
    onSend(text);
    input.value = "";
    input.style.height = "auto";
  }

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 100) + "px";
  });

  sendBtn.addEventListener("click", send);

  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

  if (!SpeechRecognition) {
    micBtn.style.display = "none";
  } else {
    let recognition: any = null;
    let listening = false;

    micBtn.addEventListener("click", () => {
      if (listening) {
        recognition?.stop();
        return;
      }
      recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        listening = true;
        micBtn.classList.add("pulse-mic-active");
      };
      recognition.onresult = (e: any) => {
        const transcript = e.results[0][0].transcript;
        input.value = (input.value + " " + transcript).trim();
        input.dispatchEvent(new Event("input"));
      };
      recognition.onend = () => {
        listening = false;
        micBtn.classList.remove("pulse-mic-active");
      };
      recognition.onerror = () => {
        listening = false;
        micBtn.classList.remove("pulse-mic-active");
      };
      recognition.start();
    });
  }

  container.appendChild(input);
  container.appendChild(micBtn);
  container.appendChild(sendBtn);

  return {
    element: container,
    setDisabled(disabled: boolean) {
      input.disabled = disabled;
      sendBtn.disabled = disabled;
      micBtn.disabled = disabled;
    },
    focus() {
      input.focus();
    },
  };
}
