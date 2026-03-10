import { createHeader } from "./header";
import { createInput } from "./input";

export function createChatWindow(
  displayName: string,
  avatarUrl: string | null,
  placeholder: string,
  poweredBy: boolean,
  onClose: () => void,
  onSend: (message: string) => void
): {
  element: HTMLElement;
  messagesContainer: HTMLElement;
  setInputDisabled: (disabled: boolean) => void;
  focusInput: () => void;
  setOpen: (open: boolean) => void;
} {
  const window = document.createElement("div");
  window.className = "pulse-window";

  const header = createHeader(displayName, avatarUrl, onClose);

  const messages = document.createElement("div");
  messages.className = "pulse-messages";

  const input = createInput(placeholder, onSend);

  window.appendChild(header);
  window.appendChild(messages);
  window.appendChild(input.element);

  if (poweredBy) {
    const powered = document.createElement("div");
    powered.className = "pulse-powered";
    powered.innerHTML = 'Powered by <a href="https://pulse.app" target="_blank" rel="noopener">Pulse</a>';
    window.appendChild(powered);
  }

  return {
    element: window,
    messagesContainer: messages,
    setInputDisabled: input.setDisabled,
    focusInput: input.focus,
    setOpen(open: boolean) {
      window.classList.toggle("open", open);
    },
  };
}
