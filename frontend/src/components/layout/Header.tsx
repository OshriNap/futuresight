"use client";

import { usePathname } from "next/navigation";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/predictions": "Predictions",
  "/accuracy": "Accuracy Tracking",
  "/agents": "Agent Performance",
  "/graph": "Event Graph",
  "/interests": "Interests",
};

export default function Header() {
  const pathname = usePathname();
  const title = pageTitles[pathname] || "FutureSight";

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-bg-primary/80 px-8 backdrop-blur-sm">
      <h1 className="text-xl font-semibold text-white">{title}</h1>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
          System Online
        </div>
      </div>
    </header>
  );
}
