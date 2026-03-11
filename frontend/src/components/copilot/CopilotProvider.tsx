import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

interface CopilotPageContext {
  page: string;
  chatbot_id?: string;
  conversation_id?: string;
  data: Record<string, unknown>;
}

interface ActivePanel {
  component: string;
  props: Record<string, unknown>;
}

interface CopilotContextValue {
  isOpen: boolean;
  toggle: () => void;
  open: () => void;
  close: () => void;
  context: CopilotPageContext;
  registerContext: (ctx: CopilotPageContext) => void;
  activePanel: ActivePanel | null;
  setActivePanel: (panel: ActivePanel | null) => void;
}

const CopilotContext = createContext<CopilotContextValue | null>(null);

const STORAGE_KEY = "copilot_open";

export function CopilotProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(STORAGE_KEY) === "true";
  });
  const [context, setContext] = useState<CopilotPageContext>({
    page: "unknown",
    data: {},
  });
  const [activePanel, setActivePanel] = useState<ActivePanel | null>(null);

  const toggle = useCallback(() => {
    setIsOpen((prev) => {
      const next = !prev;
      localStorage.setItem(STORAGE_KEY, String(next));
      return next;
    });
  }, []);

  const open = useCallback(() => {
    setIsOpen(true);
    localStorage.setItem(STORAGE_KEY, "true");
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    localStorage.setItem(STORAGE_KEY, "false");
  }, []);

  const registerContext = useCallback((ctx: CopilotPageContext) => {
    setContext(ctx);
  }, []);

  // ⌘J / Ctrl+J keyboard shortcut
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "j") {
        e.preventDefault();
        toggle();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  const value = useMemo(
    () => ({ isOpen, toggle, open, close, context, registerContext, activePanel, setActivePanel }),
    [isOpen, toggle, open, close, context, registerContext, activePanel, setActivePanel]
  );

  return (
    <CopilotContext.Provider value={value}>
      {children}
    </CopilotContext.Provider>
  );
}

export function useCopilot() {
  const ctx = useContext(CopilotContext);
  if (!ctx) throw new Error("useCopilot must be used within CopilotProvider");

  const register = useCallback(
    (pageCtx: CopilotPageContext) => {
      ctx.registerContext(pageCtx);
    },
    [ctx.registerContext]
  );

  return { ...ctx, register };
}
