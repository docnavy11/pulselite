import { useState } from "react";
import { clsx } from "clsx";

interface CopyButtonProps {
  value: string;
  className?: string;
  label?: string;
}

export function CopyButton({ value, className, label = "Copy" }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // fallback
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={clsx(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all",
        copied
          ? "bg-green-50 text-green-600 border border-green-200"
          : "bg-[#faf8f5] text-gray-500 border border-[#f0ebe3] hover:bg-[#f0ebe3] hover:text-gray-700",
        className
      )}
    >
      {copied ? (
        <>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M1.5 5 L4 7.5 L8.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <rect x="3" y="1" width="6" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
            <path d="M1 3 L1 9 Q1 9 1 9 L7 9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
          </svg>
          {label}
        </>
      )}
    </button>
  );
}
