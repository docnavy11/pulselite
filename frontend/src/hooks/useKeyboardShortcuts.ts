import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function useKeyboardShortcuts() {
  const router = useRouter();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't fire when typing in inputs/textareas
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if ((e.target as HTMLElement)?.isContentEditable) return;

      switch (e.key) {
        case "n":
          router.push("/chatbots/new");
          break;
        case "c":
          router.push("/conversations");
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
  }, [router]);
}
