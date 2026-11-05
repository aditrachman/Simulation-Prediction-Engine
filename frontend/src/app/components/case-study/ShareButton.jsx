"use client";

import { useState } from "react";

export default function ShareButton({ label = "Bagikan tautan" }) {
  const [copied, setCopied] = useState(false);

  async function handleClick() {
    const url = window.location.href;

    try {
      if (!navigator.clipboard) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(url);
    } catch {
      window.prompt("Salin tautan ini:", url);
      return;
    }

    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button type="button" className="cs-btn" onClick={handleClick}>
      {copied ? "Tautan disalin" : label}
    </button>
  );
}
