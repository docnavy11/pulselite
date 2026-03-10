const BOT_ICON = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg>`;
const CLOSE_ICON = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;

export function createHeader(
  displayName: string,
  avatarUrl: string | null,
  onClose: () => void
): HTMLElement {
  const header = document.createElement("div");
  header.className = "pulse-header";

  const avatar = document.createElement("div");
  avatar.className = "pulse-header-avatar";
  if (avatarUrl) {
    const img = document.createElement("img");
    img.src = avatarUrl;
    img.alt = displayName;
    avatar.appendChild(img);
  } else {
    avatar.innerHTML = BOT_ICON;
  }

  const info = document.createElement("div");
  info.className = "pulse-header-info";

  const name = document.createElement("div");
  name.className = "pulse-header-name";
  name.textContent = displayName;

  const status = document.createElement("div");
  status.className = "pulse-header-status";
  status.textContent = "Online";

  info.appendChild(name);
  info.appendChild(status);

  const closeBtn = document.createElement("button");
  closeBtn.className = "pulse-close-btn";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.innerHTML = CLOSE_ICON;
  closeBtn.addEventListener("click", onClose);

  header.appendChild(avatar);
  header.appendChild(info);
  header.appendChild(closeBtn);

  return header;
}
