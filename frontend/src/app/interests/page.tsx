"use client";

import { useEffect, useState } from "react";
import { getInterests, createInterest, deleteInterest } from "@/lib/api";
import { UserInterest } from "@/lib/types";

const mockInterests: UserInterest[] = [
  {
    id: "1",
    name: "AI & Machine Learning",
    keywords: ["artificial intelligence", "machine learning", "LLM", "neural networks"],
    priority: "high",
    category: "Technology",
    active: true,
    created_at: "2026-01-15T00:00:00Z",
    updated_at: "2026-03-01T00:00:00Z",
  },
  {
    id: "2",
    name: "Federal Reserve Policy",
    keywords: ["federal reserve", "interest rates", "FOMC", "monetary policy"],
    priority: "high",
    category: "Economics",
    active: true,
    created_at: "2026-01-20T00:00:00Z",
    updated_at: "2026-03-05T00:00:00Z",
  },
  {
    id: "3",
    name: "Renewable Energy",
    keywords: ["solar", "wind", "renewable", "clean energy", "EV"],
    priority: "medium",
    category: "Energy",
    active: true,
    created_at: "2026-02-01T00:00:00Z",
    updated_at: "2026-02-15T00:00:00Z",
  },
  {
    id: "4",
    name: "Cryptocurrency Markets",
    keywords: ["bitcoin", "ethereum", "crypto", "defi", "blockchain"],
    priority: "low",
    category: "Finance",
    active: true,
    created_at: "2026-02-10T00:00:00Z",
    updated_at: "2026-02-20T00:00:00Z",
  },
];

function getPriorityBadge(priority: string): string {
  switch (priority) {
    case "high":
      return "bg-confidence-low/15 text-confidence-low";
    case "medium":
      return "bg-confidence-medium/15 text-confidence-medium";
    case "low":
      return "bg-gray-500/15 text-gray-400";
    default:
      return "bg-gray-500/15 text-gray-400";
  }
}

export default function InterestsPage() {
  const [interests, setInterests] = useState<UserInterest[]>(mockInterests);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    keywords: "",
    priority: "medium" as "high" | "medium" | "low",
    category: "",
  });

  useEffect(() => {
    async function loadData() {
      try {
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${API_BASE}/api/interests`);
        if (res.ok) {
          const data = await res.json();
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const mapped = (Array.isArray(data) ? data : []).map((i: any) => ({
            id: i.id,
            name: i.name || "Interest",
            keywords: Array.isArray(i.keywords) ? i.keywords : [],
            priority: i.priority || "medium",
            category: i.category || "General",
            active: i.active ?? true,
            created_at: i.created_at || new Date().toISOString(),
            updated_at: i.updated_at || new Date().toISOString(),
          }));
          if (mapped.length > 0) setInterests(mapped);
        }
      } catch {
        // Use mock data
      }
    }
    loadData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const newInterest = {
      name: formData.name,
      keywords: formData.keywords.split(",").map((k) => k.trim()).filter(Boolean),
      priority: formData.priority,
      category: formData.category,
      active: true,
    };

    try {
      const created = await createInterest(newInterest);
      setInterests([...interests, created]);
    } catch {
      // Add locally with a temp id
      const tempInterest: UserInterest = {
        ...newInterest,
        id: `temp-${Date.now()}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setInterests([...interests, tempInterest]);
    }

    setFormData({ name: "", keywords: "", priority: "medium", category: "" });
    setShowForm(false);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteInterest(id);
    } catch {
      // Remove locally anyway
    }
    setInterests(interests.filter((i) => i.id !== id));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400">
            Manage your interests to customize prediction feeds and alerts.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn-primary"
        >
          {showForm ? "Cancel" : "+ Add Interest"}
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">
            Add New Interest
          </h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="e.g., AI & Machine Learning"
                  className="input-field"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Category
                </label>
                <input
                  type="text"
                  value={formData.category}
                  onChange={(e) =>
                    setFormData({ ...formData, category: e.target.value })
                  }
                  placeholder="e.g., Technology"
                  className="input-field"
                  required
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Keywords (comma-separated)
              </label>
              <input
                type="text"
                value={formData.keywords}
                onChange={(e) =>
                  setFormData({ ...formData, keywords: e.target.value })
                }
                placeholder="e.g., artificial intelligence, machine learning, LLM"
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Priority
              </label>
              <div className="flex gap-3">
                {(["high", "medium", "low"] as const).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setFormData({ ...formData, priority: p })}
                    className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                      formData.priority === p
                        ? "bg-accent-blue text-white"
                        : "bg-bg-primary text-gray-400 hover:text-gray-200"
                    }`}
                  >
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex justify-end">
              <button type="submit" className="btn-primary">
                Add Interest
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Interests list */}
      <div className="space-y-3">
        {interests.map((interest) => (
          <div key={interest.id} className="card-hover">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <h3 className="font-medium text-white">{interest.name}</h3>
                  <span
                    className={`badge ${getPriorityBadge(interest.priority)}`}
                  >
                    {interest.priority}
                  </span>
                  <span className="badge bg-accent-blue/10 text-accent-blue">
                    {interest.category}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {interest.keywords.map((keyword) => (
                    <span
                      key={keyword}
                      className="rounded bg-bg-primary px-2 py-0.5 text-xs text-gray-400"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleDelete(interest.id)}
                  className="rounded p-1.5 text-gray-500 transition-colors hover:bg-red-500/10 hover:text-red-400"
                  title="Delete"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {interests.length === 0 && (
        <div className="card flex h-40 items-center justify-center">
          <div className="text-center">
            <p className="text-gray-500">No interests configured yet.</p>
            <p className="mt-1 text-sm text-gray-600">
              Add your first interest to start receiving personalized
              predictions.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
