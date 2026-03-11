import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export function useKeyboardShortcuts() {
  const navigate = useNavigate();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't fire when typing in inputs/textareas
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if ((e.target as HTMLElement)?.isContentEditable) return;

      switch (e.key) {
        case "n":
          navigate("/chatbots/new");
          break;
        case "c":
          navigate("/conversations");
          break;
        case "/":
          e.preventDefault();
          window.dispatchEvent(new CustomEvent("open-command-palette"));
          break;
        case "Escape":
          window.dispatchEvent(new CustomEvent("close-all-panels"));
          break;
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [navigate]);
}
