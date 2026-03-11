"use client";

import { useCopilot } from "./CopilotProvider";
import { ComponentRegistry } from "./registry";

export function ComponentPanel() {
  const { activePanel, setActivePanel } = useCopilot();

  const Component = activePanel ? ComponentRegistry[activePanel.component] : null;

  return (
    <div
      className="flex-shrink-0 overflow-hidden border-l border-[#e8e2d9] bg-white transition-all duration-300 ease-in-out"
      style={{ width: activePanel ? 480 : 0 }}
    >
      {activePanel && Component && (
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-[#f0ebe3] px-4 py-2.5">
            <span className="text-xs font-semibold text-gray-700">
              {activePanel.component}
            </span>
            <button
              onClick={() => setActivePanel(null)}
              className="text-gray-400 hover:text-gray-600 transition-colors text-base leading-none"
              aria-label="Close panel"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-auto">
            <Component {...activePanel.props} />
          </div>
        </div>
      )}
    </div>
  );
}
