"use client";

import { useCopilot } from "./CopilotProvider";
import { CopilotChat } from "./CopilotChat";
import { ComponentPanel } from "./ComponentPanel";

export function CopilotPanel() {
  const { isOpen } = useCopilot();
  if (!isOpen) return null;
  return (
    <>
      <ComponentPanel />
      <CopilotChat />
    </>
  );
}
