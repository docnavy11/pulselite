const CHAT_ICON = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>`;
const CLOSE_ICON = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;

export function createLauncher(
  onClick: () => void
): { element: HTMLButtonElement; setOpen: (open: boolean) => void; showUnread: (show: boolean) => void } {
  const btn = document.createElement("button");
  btn.className = "pulse-launcher";
  btn.setAttribute("aria-label", "Open chat");
  btn.innerHTML = CHAT_ICON;

  const unread = document.createElement("span");
  unread.className = "pulse-unread";
  btn.appendChild(unread);

  btn.addEventListener("click", onClick);

  return {
    element: btn,
    setOpen(open: boolean) {
      btn.innerHTML = open ? CLOSE_ICON : CHAT_ICON;
      btn.appendChild(unread);
      btn.classList.toggle("open", open);
      btn.setAttribute("aria-label", open ? "Close chat" : "Open chat");
    },
    showUnread(show: boolean) {
      unread.classList.toggle("show", show);
    },
  };
}
