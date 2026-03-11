export function getStyles(primaryColor: string, bgColor: string, textColor: string): string {
  return `
    :host {
      --pulse-primary: ${primaryColor};
      --pulse-bg: ${bgColor};
      --pulse-text: ${textColor};
      --pulse-text-light: #6b7280;
      --pulse-border: #e5e7eb;
      --pulse-user-text: #ffffff;
      --pulse-bot-bg: #f3f4f6;
      --pulse-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
      --pulse-radius: 16px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    .pulse-container {
      position: fixed;
      z-index: 2147483647;
    }

    .pulse-container.bottom-right {
      bottom: 20px;
      right: 20px;
    }

    .pulse-container.bottom-left {
      bottom: 20px;
      left: 20px;
    }

    .pulse-launcher {
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: var(--pulse-primary);
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      position: relative;
    }

    .pulse-launcher:hover {
      transform: scale(1.08);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
    }

    .pulse-launcher svg {
      width: 24px;
      height: 24px;
      fill: white;
      transition: transform 0.3s ease;
    }

    .pulse-launcher.open svg {
      transform: rotate(90deg);
    }

    .pulse-unread {
      position: absolute;
      top: -2px;
      right: -2px;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #ef4444;
      border: 2px solid white;
      display: none;
    }

    .pulse-unread.show { display: block; }

    .pulse-window {
      position: absolute;
      bottom: 70px;
      width: 380px;
      height: 520px;
      background: var(--pulse-bg);
      border-radius: var(--pulse-radius);
      box-shadow: var(--pulse-shadow);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      opacity: 0;
      transform: translateY(20px) scale(0.95);
      pointer-events: none;
      transition: opacity 0.25s ease, transform 0.25s ease;
    }

    .pulse-container.bottom-right .pulse-window { right: 0; }
    .pulse-container.bottom-left .pulse-window { left: 0; }

    .pulse-window.open {
      opacity: 1;
      transform: translateY(0) scale(1);
      pointer-events: all;
    }

    .pulse-header {
      background: var(--pulse-primary);
      color: white;
      padding: 16px 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }

    .pulse-header-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      overflow: hidden;
    }

    .pulse-header-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .pulse-header-avatar svg {
      width: 20px;
      height: 20px;
      fill: white;
    }

    .pulse-header-info { flex: 1; }

    .pulse-header-name {
      font-weight: 600;
      font-size: 15px;
    }

    .pulse-header-status {
      font-size: 12px;
      opacity: 0.8;
    }

    .pulse-close-btn {
      background: none;
      border: none;
      cursor: pointer;
      color: white;
      padding: 4px;
      display: flex;
      opacity: 0.8;
      transition: opacity 0.15s;
    }

    .pulse-close-btn:hover { opacity: 1; }

    .pulse-close-btn svg {
      width: 20px;
      height: 20px;
      fill: currentColor;
    }

    .pulse-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      scroll-behavior: smooth;
    }

    .pulse-messages::-webkit-scrollbar { width: 4px; }
    .pulse-messages::-webkit-scrollbar-track { background: transparent; }
    .pulse-messages::-webkit-scrollbar-thumb {
      background: var(--pulse-border);
      border-radius: 2px;
    }

    .pulse-msg {
      display: flex;
      gap: 8px;
      max-width: 85%;
      animation: pulse-fade-in 0.2s ease;
    }

    @keyframes pulse-fade-in {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .pulse-msg.user {
      align-self: flex-end;
      flex-direction: row-reverse;
    }

    .pulse-msg-avatar {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: var(--pulse-bot-bg);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      overflow: hidden;
    }

    .pulse-msg-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .pulse-msg-avatar svg {
      width: 14px;
      height: 14px;
      fill: var(--pulse-text-light);
    }

    .pulse-msg-bubble {
      padding: 10px 14px;
      border-radius: 12px;
      word-wrap: break-word;
      overflow-wrap: break-word;
    }

    .pulse-msg.bot .pulse-msg-bubble {
      background: var(--pulse-bot-bg);
      color: var(--pulse-text);
      border-bottom-left-radius: 4px;
    }

    .pulse-msg.user .pulse-msg-bubble {
      background: var(--pulse-primary);
      color: var(--pulse-user-text);
      border-bottom-right-radius: 4px;
    }

    .pulse-msg-time {
      font-size: 11px;
      color: var(--pulse-text-light);
      margin-top: 4px;
    }

    .pulse-msg.user .pulse-msg-time { text-align: right; }

    .pulse-msg-bubble a {
      color: inherit;
      text-decoration: underline;
    }

    .pulse-msg-bubble strong { font-weight: 600; }

    .pulse-msg-bubble .pulse-code-block {
      background: #1f2937;
      color: #e5e7eb;
      padding: 8px 12px;
      border-radius: 6px;
      font-family: 'SF Mono', Monaco, monospace;
      font-size: 13px;
      overflow-x: auto;
      margin: 4px 0;
      white-space: pre-wrap;
    }

    .pulse-msg-bubble .pulse-inline-code {
      background: rgba(0, 0, 0, 0.06);
      padding: 2px 5px;
      border-radius: 3px;
      font-family: 'SF Mono', Monaco, monospace;
      font-size: 13px;
    }

    .pulse-msg-bubble .pulse-list {
      padding-left: 20px;
      margin: 4px 0;
    }

    .pulse-msg-bubble .pulse-citation {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      font-size: 10px;
      font-weight: 600;
      background: var(--pulse-primary);
      color: #fff;
      border-radius: 50%;
      text-decoration: none;
      vertical-align: super;
      line-height: 1;
      margin-left: 1px;
      cursor: pointer;
    }

    .pulse-msg-bubble .pulse-footnotes {
      margin-top: 10px;
      padding: 8px 10px;
      border-top: 1px solid var(--pulse-border);
      list-style: none;
      counter-reset: footnote;
    }

    .pulse-msg-bubble .pulse-footnotes li {
      counter-increment: footnote;
      font-size: 11px;
      color: var(--pulse-text-light);
      margin-top: 3px;
    }

    .pulse-msg-bubble .pulse-footnotes li::before {
      content: "[" counter(footnote) "] ";
      font-weight: 600;
    }

    .pulse-msg-bubble .pulse-footnote-link {
      color: var(--pulse-primary);
      text-decoration: none;
    }

    .pulse-msg-bubble .pulse-footnote-link:hover {
      text-decoration: underline;
    }

    .pulse-streaming-dots {
      display: flex;
      gap: 4px;
      padding: 4px 0;
    }

    .pulse-streaming-dots span {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--pulse-text-light);
      animation: pulse-dot-bounce 1.4s infinite ease-in-out;
    }

    .pulse-streaming-dots span:nth-child(2) { animation-delay: 0.16s; }
    .pulse-streaming-dots span:nth-child(3) { animation-delay: 0.32s; }

    @keyframes pulse-dot-bounce {
      0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
      40% { transform: scale(1); opacity: 1; }
    }

    .pulse-input-area {
      padding: 12px 16px;
      border-top: 1px solid var(--pulse-border);
      display: flex;
      gap: 8px;
      align-items: flex-end;
      flex-shrink: 0;
    }

    .pulse-input {
      flex: 1;
      border: 1px solid var(--pulse-border);
      border-radius: 20px;
      padding: 8px 16px;
      font-size: 14px;
      font-family: inherit;
      outline: none;
      resize: none;
      max-height: 100px;
      line-height: 1.4;
      color: var(--pulse-text);
      background: var(--pulse-bg);
      transition: border-color 0.15s;
    }

    .pulse-input:focus { border-color: var(--pulse-primary); }

    .pulse-input::placeholder { color: var(--pulse-text-light); }

    .pulse-send-btn {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--pulse-primary);
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: opacity 0.15s, transform 0.15s;
    }

    .pulse-send-btn:hover { transform: scale(1.05); }
    .pulse-send-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

    .pulse-send-btn svg {
      width: 16px;
      height: 16px;
      fill: white;
    }

    .pulse-powered {
      text-align: center;
      padding: 6px;
      font-size: 11px;
      color: var(--pulse-text-light);
      flex-shrink: 0;
    }

    .pulse-powered a {
      color: var(--pulse-text-light);
      text-decoration: none;
      font-weight: 500;
    }

    .pulse-powered a:hover { text-decoration: underline; }

    .pulse-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding: 4px 12px 8px;
    }
    .pulse-chip {
      background: transparent;
      border: 1.5px solid var(--pulse-primary);
      border-radius: 16px;
      color: var(--pulse-primary);
      cursor: pointer;
      font-size: 12px;
      padding: 4px 12px;
      transition: all 0.15s;
    }
    .pulse-chip:hover {
      background: var(--pulse-primary);
      color: #fff;
    }

    .pulse-lead-form {
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .pulse-lead-label {
      font-size: 12px;
      color: #6b7280;
      font-weight: 500;
    }
    .pulse-lead-input {
      width: 100%;
      border: 1.5px solid #e5e7eb;
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.15s;
      box-sizing: border-box;
    }
    .pulse-lead-input:focus {
      border-color: var(--pulse-primary);
    }
    .pulse-lead-btn {
      background: var(--pulse-primary);
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 10px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      margin-top: 4px;
    }

    .pulse-consent-banner {
      position: absolute;
      inset: 0;
      background: var(--pulse-bg);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
      z-index: 10;
      gap: 16px;
      text-align: center;
    }

    .pulse-consent-banner p {
      font-size: 13px;
      color: var(--pulse-text-light);
      line-height: 1.6;
    }

    .pulse-consent-accept {
      background: var(--pulse-primary);
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 10px 24px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
    }

    .pulse-consent-accept:hover { opacity: 0.9; }

    .pulse-consent-decline {
      background: none;
      border: none;
      font-size: 12px;
      color: var(--pulse-text-light);
      cursor: pointer;
      text-decoration: underline;
    }

    .pulse-copy-btn {
      display: none;
      background: none;
      border: none;
      cursor: pointer;
      font-size: 13px;
      color: #9ca3af;
      padding: 2px 4px;
      margin-top: 4px;
      border-radius: 4px;
    }
    .pulse-copy-btn:hover { color: #374151; background: #f3f4f6; }
    .pulse-msg:hover .pulse-copy-btn { display: inline-block; }
    .pulse-feedback-btn {
      display: none;
      background: none;
      border: none;
      cursor: pointer;
      font-size: 14px;
      padding: 2px 3px;
      border-radius: 4px;
      opacity: 0.5;
      transition: opacity 0.15s;
    }
    .pulse-feedback-btn:hover { opacity: 1; background: #f3f4f6; }
    .pulse-feedback-btn:disabled { cursor: default; }
    .pulse-msg:hover .pulse-feedback-btn { display: inline-block; }

    .pulse-mic-btn {
      background: none;
      border: none;
      cursor: pointer;
      padding: 6px;
      border-radius: 50%;
      color: #9ca3af;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: color 0.15s, background 0.15s;
      flex-shrink: 0;
    }
    .pulse-mic-btn svg { width: 20px; height: 20px; fill: currentColor; }
    .pulse-mic-btn:hover { color: #374151; background: #f3f4f6; }
    .pulse-mic-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .pulse-mic-active { color: #ef4444 !important; background: #fee2e2 !important; }

    .pulse-action-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin: 4px 16px 8px;
      padding: 10px 18px;
      background: var(--pulse-primary);
      color: #fff;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
      transition: opacity 0.15s, transform 0.15s;
      align-self: flex-start;
      box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }
    .pulse-action-btn:hover {
      opacity: 0.9;
      transform: translateY(-1px);
    }
    .pulse-action-btn--booking {
      background: #fff;
      color: var(--pulse-primary);
      border: 1.5px solid var(--pulse-primary);
    }
    .pulse-action-btn--booking:hover {
      background: var(--pulse-primary);
      color: #fff;
    }

    .pulse-booking-card {
      margin: 4px 0;
      border: 1.5px solid var(--pulse-border);
      border-radius: 12px;
      overflow: hidden;
      background: var(--pulse-bg);
    }
    .pulse-booking-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
    }
    .pulse-booking-icon { font-size: 16px; flex-shrink: 0; }
    .pulse-booking-title {
      flex: 1;
      font-size: 13px;
      font-weight: 600;
      color: var(--pulse-text);
    }
    .pulse-booking-toggle {
      background: var(--pulse-primary);
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 5px 12px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      flex-shrink: 0;
      transition: opacity 0.15s;
    }
    .pulse-booking-toggle:hover { opacity: 0.85; }
    .pulse-booking-embed {
      border-top: 1px solid var(--pulse-border);
      overflow: hidden;
    }
    .pulse-booking-embed iframe {
      display: block;
      border: none;
    }

    @media (max-width: 480px) {
      .pulse-window {
        width: 100vw;
        height: 100vh;
        bottom: 0;
        right: 0 !important;
        left: 0 !important;
        border-radius: 0;
      }
      .pulse-container.bottom-right .pulse-window,
      .pulse-container.bottom-left .pulse-window {
        right: 0;
        left: 0;
      }
    }
  `;
}
