"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getInterests, createInterest, updateInterest, deleteInterest } from "@/lib/api";
import { UserInterest } from "@/lib/types";

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

function getRegionBadge(region: string): string {
  switch (region) {
    case "IL":
      return "bg-blue-500/15 text-blue-400";
    case "US":
      return "bg-green-500/15 text-green-400";
    case "EU":
      return "bg-purple-500/15 text-purple-400";
    case "global":
      return "bg-yellow-500/15 text-yellow-400";
    default:
      return "bg-gray-500/15 text-gray-400";
  }
}

interface FormData {
  name: string;
  keywords: string;
  priority: "high" | "medium" | "low";
  category: string;
  indicators: string;
  market_filters: string;
  region: string;
  enabled: boolean;
}

const emptyForm: FormData = {
  name: "",
  keywords: "",
  priority: "medium",
  category: "",
  indicators: "",
  market_filters: "",
  region: "global",
  enabled: true,
};

export default function InterestsPage() {
  const [interests, setInterests] = useState<UserInterest[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<FormData>(emptyForm);

  useEffect(() => {
    async function loadData() {
      try {
        const data = await getInterests();
        if (data.length > 0) setInterests(data);
      } catch {
        // Keep empty state
      }
    }
    loadData();
  }, []);

  const openCreateForm = () => {
    setEditingId(null);
    setFormData(emptyForm);
    setShowForm(true);
  };

  const openEditForm = (interest: UserInterest) => {
    setEditingId(interest.id);
    setFormData({
      name: interest.name,
      keywords: interest.keywords.join(", "),
      priority: interest.priority,
      category: interest.category,
      indicators: (interest.indicators || []).join(", "),
      market_filters: (interest.market_filters || []).join(", "),
      region: interest.region || "global",
      enabled: interest.enabled ?? interest.active ?? true,
    });
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name: formData.name,
      keywords: formData.keywords.split(",").map((k) => k.trim()).filter(Boolean),
      priority: formData.priority,
      category: formData.category,
      active: formData.enabled,
      enabled: formData.enabled,
      indicators: formData.indicators.split(",").map((k) => k.trim()).filter(Boolean),
      market_filters: formData.market_filters.split(",").map((k) => k.trim()).filter(Boolean),
      region: formData.region,
    };

    if (editingId) {
      try {
        const updated = await updateInterest(editingId, payload);
        setInterests(interests.map((i) => (i.id === editingId ? updated : i)));
      } catch {
        // Update locally
        setInterests(
          interests.map((i) =>
            i.id === editingId
              ? { ...i, ...payload, updated_at: new Date().toISOString() }
              : i
          )
        );
      }
    } else {
      try {
        const created = await createInterest(payload);
        setInterests([...interests, created]);
      } catch {
        const tempInterest: UserInterest = {
          ...payload,
          id: `temp-${Date.now()}`,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        setInterests([...interests, tempInterest]);
      }
    }

    setFormData(emptyForm);
    setEditingId(null);
    setShowForm(false);
  };

  const handleToggleEnabled = async (interest: UserInterest) => {
    const newEnabled = !(interest.enabled ?? interest.active ?? true);
    try {
      const updated = await updateInterest(interest.id, { enabled: newEnabled, active: newEnabled });
      setInterests(interests.map((i) => (i.id === interest.id ? updated : i)));
    } catch {
      setInterests(
        interests.map((i) =>
          i.id === interest.id
            ? { ...i, enabled: newEnabled, active: newEnabled, updated_at: new Date().toISOString() }
            : i
        )
      );
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteInterest(id);
    } catch {
      // Remove locally anyway
    }
    setInterests(interests.filter((i) => i.id !== id));
  };

  const cancelForm = () => {
    setShowForm(false);
    setEditingId(null);
    setFormData(emptyForm);
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
          onClick={() => (showForm ? cancelForm() : openCreateForm())}
          className="btn-primary"
        >
          {showForm ? "Cancel" : "+ Add Interest"}
        </button>
      </div>

      {/* Add/Edit form */}
      {showForm && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">
            {editingId ? "Edit Interest" : "Add New Interest"}
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
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Indicators (comma-separated series IDs)
                </label>
                <textarea
                  value={formData.indicators}
                  onChange={(e) =>
                    setFormData({ ...formData, indicators: e.target.value })
                  }
                  placeholder="e.g., FRED:UNRATE, CBS_IL:cpi"
                  className="input-field min-h-[60px] resize-y"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Market Filters (comma-separated)
                </label>
                <textarea
                  value={formData.market_filters}
                  onChange={(e) =>
                    setFormData({ ...formData, market_filters: e.target.value })
                  }
                  placeholder="e.g., israel, recession"
                  className="input-field min-h-[60px] resize-y"
                  rows={2}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
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
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Region
                </label>
                <select
                  value={formData.region}
                  onChange={(e) =>
                    setFormData({ ...formData, region: e.target.value })
                  }
                  className="input-field"
                >
                  <option value="global">Global</option>
                  <option value="US">US</option>
                  <option value="IL">IL (Israel)</option>
                  <option value="EU">EU</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Enabled
                </label>
                <label className="flex items-center gap-2 cursor-pointer mt-2">
                  <input
                    type="checkbox"
                    checked={formData.enabled}
                    onChange={(e) =>
                      setFormData({ ...formData, enabled: e.target.checked })
                    }
                    className="w-4 h-4 rounded border-gray-600 bg-bg-primary text-accent-blue focus:ring-accent-blue focus:ring-offset-0"
                  />
                  <span className="text-sm text-gray-300">
                    {formData.enabled ? "Active" : "Disabled"}
                  </span>
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={cancelForm}
                className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button type="submit" className="btn-primary">
                {editingId ? "Update Interest" : "Add Interest"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Interests list */}
      <div className="space-y-3">
        {interests.map((interest) => {
          const isEnabled = interest.enabled ?? interest.active ?? true;
          return (
            <div key={interest.id} className={`card-hover ${!isEnabled ? "opacity-60" : ""}`}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    {/* Enabled toggle */}
                    <button
                      onClick={() => handleToggleEnabled(interest)}
                      className={`w-9 h-5 rounded-full relative transition-colors flex-shrink-0 ${
                        isEnabled ? "bg-accent-blue" : "bg-gray-600"
                      }`}
                      title={isEnabled ? "Disable" : "Enable"}
                    >
                      <span
                        className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                          isEnabled ? "left-4" : "left-0.5"
                        }`}
                      />
                    </button>
                    <Link
                      href={`/interests/${interest.id}`}
                      className="font-medium text-white hover:text-accent-blue transition-colors"
                    >
                      {interest.name}
                    </Link>
                    <span
                      className={`badge ${getPriorityBadge(interest.priority)}`}
                    >
                      {interest.priority}
                    </span>
                    <span className="badge bg-accent-blue/10 text-accent-blue">
                      {interest.category}
                    </span>
                    {interest.region && (
                      <span className={`badge ${getRegionBadge(interest.region)}`}>
                        {interest.region}
                      </span>
                    )}
                  </div>
                  {/* Keywords */}
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
                  {/* Indicators */}
                  {interest.indicators && interest.indicators.length > 0 && (
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <span className="text-xs text-gray-500 mr-1">Indicators:</span>
                      {interest.indicators.map((ind) => (
                        <span
                          key={ind}
                          className="rounded bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-400"
                        >
                          {ind}
                        </span>
                      ))}
                    </div>
                  )}
                  {/* Market Filters */}
                  {interest.market_filters && interest.market_filters.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <span className="text-xs text-gray-500 mr-1">Market filters:</span>
                      {interest.market_filters.map((mf) => (
                        <span
                          key={mf}
                          className="rounded bg-orange-500/10 px-2 py-0.5 text-xs text-orange-400"
                        >
                          {mf}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 ml-3">
                  {/* Edit button */}
                  <button
                    onClick={() => openEditForm(interest)}
                    className="rounded p-1.5 text-gray-500 transition-colors hover:bg-accent-blue/10 hover:text-accent-blue"
                    title="Edit"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                    </svg>
                  </button>
                  {/* Delete button */}
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
          );
        })}
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
