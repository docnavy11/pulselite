// frontend/src/components/icons/NavIcons.tsx
// Custom SVG glyphs. All icons: 16×16 nav, 12×12 tab, stroke-linecap="round" stroke-linejoin="round".

interface IconProps {
  className?: string;
  size?: number;
}

// ── Nav icons (16×16) ──

export function IconOverview({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <path
        d="M1 8 L3.5 8 L5 4 L7 12 L9 6 L10.5 8 L15 8"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconChatbots({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <path
        d="M8 1.5 L10 6 L14.5 8 L10 10 L8 14.5 L6 10 L1.5 8 L6 6 Z"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconConversations({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <path
        d="M2 4 Q2 2 4 2 L12 2 Q14 2 14 4 L14 9 Q14 11 12 11 L9 11 L6 14 L7 11 L4 11 Q2 11 2 9 Z"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="5.5" cy="6.5" r="0.8" fill="currentColor" className="stroke-none" />
      <circle cx="8" cy="6.5" r="0.8" fill="currentColor" className="stroke-none" />
      <circle cx="10.5" cy="6.5" r="0.8" fill="currentColor" className="stroke-none" />
    </svg>
  );
}

export function IconIntelligence({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <circle cx="6" cy="8" r="4.5" strokeWidth="1.6" />
      <circle cx="10.5" cy="6.5" r="3.5" strokeWidth="1.6" />
    </svg>
  );
}

export function IconLogs({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <circle cx="3" cy="4.5" r="1" fill="currentColor" className="stroke-none" />
      <path d="M6 4.5 L14 4.5" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="3" cy="8" r="1" fill="currentColor" className="stroke-none" />
      <path d="M6 8 L14 8" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="3" cy="11.5" r="1" fill="currentColor" className="stroke-none" />
      <path d="M6 11.5 L11 11.5" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function IconSettings({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.5" strokeWidth="1.6" />
      <rect x="9"   y="1.5" width="5.5" height="5.5" rx="1.5" strokeWidth="1.6" />
      <rect x="1.5" y="9"   width="5.5" height="5.5" rx="1.5" strokeWidth="1.6" />
      <rect x="9"   y="9"   width="5.5" height="5.5" rx="1.5" strokeWidth="1.6" />
    </svg>
  );
}

export function IconAdmin({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <path
        d="M8 1.5 L14 5 L14 9.5 C14 12 11 14.5 8 14.5 C5 14.5 2 12 2 9.5 L2 5 Z"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M6 8 L7.5 9.5 L10 6.5" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Tab icons (12×12) ──

export function IconKnowledge({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <path d="M2 3 L10 3 M2 6 L8 6 M2 9 L6 9" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconConfigure({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <path
        d="M6 1 L7.2 4.2 L10.5 5.5 L7.2 6.8 L6 10 L4.8 6.8 L1.5 5.5 L4.8 4.2 Z"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconActions({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <circle cx="6" cy="6" r="4.5" strokeWidth="1.4" />
      <path d="M6 3.5 L6 6 L8 6" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function IconAppearance({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <rect x="1.5" y="1.5" width="9" height="9" rx="2" strokeWidth="1.4" />
      <path
        d="M3.5 6 Q4.5 4.5 6 5.5 Q7.5 6.5 8.5 5"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconTest({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <path
        d="M2 4 Q2 2 4 2 L8 2 Q10 2 10 4 L10 7 Q10 9 8 9 L7 9 L5 11 L5.5 9 L4 9 Q2 9 2 7 Z"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconQA({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <path
        d="M2 3 Q2 1.5 3.5 1.5 L8.5 1.5 Q10 1.5 10 3 L10 6 Q10 7.5 8.5 7.5 L7 7.5 L5 10 L5.3 7.5 L3.5 7.5 Q2 7.5 2 6 Z"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M5.2 5.8 L5.2 5.6 Q5.2 4.8 6 4.5 Q6.6 4.2 6.6 3.7 Q6.6 3.2 6 3 Q5.4 3 5.2 3.4" strokeWidth="0.9" strokeLinecap="round" fill="none" />
      <circle cx="5.3" cy="6.5" r="0.4" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconPublish({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <path
        d="M2 6 L5 9 L10 3"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ── Utility icons ──

export function IconSearch({ className = "stroke-current", size = 14 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className}>
      <circle cx="6" cy="6" r="4" strokeWidth="1.5" />
      <path d="M9.5 9.5 L12.5 12.5" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconBell({ className = "stroke-current", size = 14 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className}>
      <path
        d="M7 2 C5.3 2 4 3.3 4 5 L4 8 L2.5 10 L11.5 10 L10 8 L10 5 C10 3.3 8.7 2 7 2 Z"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M5.5 10 C5.5 10.8 6.2 11.5 7 11.5 C7.8 11.5 8.5 10.8 8.5 10" strokeWidth="1.4" />
    </svg>
  );
}

export function IconPlus({ className = "stroke-current", size = 14 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className}>
      <path d="M7 2 L7 12 M2 7 L12 7" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function IconChevronDown({ className = "stroke-current", size = 10 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 10 10" fill="none" className={className}>
      <path d="M2 3.5 L5 6.5 L8 3.5" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconChevronRight({ className = "stroke-current", size = 10 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 10 10" fill="none" className={className}>
      <path d="M3.5 2 L6.5 5 L3.5 8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
