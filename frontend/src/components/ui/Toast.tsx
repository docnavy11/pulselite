"use client";

import { Toaster } from "react-hot-toast";

export function ToastProvider() {
  return (
    <Toaster
      position="bottom-right"
      gutter={8}
      containerStyle={{ bottom: 24, right: 24 }}
      toastOptions={{
        duration: 3000,
        style: {
          background: "#fff",
          color: "#1a1a1a",
          border: "1px solid #f0ebe3",
          borderRadius: "10px",
          fontSize: "13px",
          fontWeight: 500,
          padding: "10px 14px",
          boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
          maxWidth: 360,
        },
        success: {
          iconTheme: { primary: "#ff6b35", secondary: "#fff" },
        },
      }}
    />
  );
}
