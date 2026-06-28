"use client";

import { useEffect, useState } from "react";
import type { Legislator } from "@/lib/types";
import LegislatorCard from "@/components/LegislatorCard";

export default function LegislatorsPage() {
  const [legislators, setLegislators] = useState<Legislator[]>([]);
  const [chamber, setChamber] = useState<"all" | "lower" | "upper">("all");
  const [party, setParty] = useState<"all" | "Democratic" | "Republican">("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/legislators.json")
      .then((r) => r.json())
      .then(setLegislators)
      .catch(() => {});
  }, []);

  const filtered = legislators.filter((l) => {
    if (chamber !== "all" && l.chamber !== chamber) return false;
    if (party !== "all" && l.party !== party) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        l.name.toLowerCase().includes(q) ||
        l.district.includes(q)
      );
    }
    return true;
  });

  const sorted = [...filtered].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 mb-6">
        PA Legislators
        <span className="text-xl font-normal text-gray-500 ml-2">
          ({legislators.length} total)
        </span>
      </h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="search"
          placeholder="Search by name or district…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search legislators"
          className="border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        <div className="flex gap-1" role="group" aria-label="Filter by chamber">
          {(
            [
              ["all", "Both chambers"],
              ["lower", "House"],
              ["upper", "Senate"],
            ] as const
          ).map(([val, label]) => (
            <button
              key={val}
              onClick={() => setChamber(val)}
              aria-pressed={chamber === val}
              className={`px-3 py-2 rounded-lg border text-sm transition ${
                chamber === val
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex gap-1" role="group" aria-label="Filter by party">
          {(
            [
              ["all", "All parties"],
              ["Democratic", "Democrat"],
              ["Republican", "Republican"],
            ] as const
          ).map(([val, label]) => (
            <button
              key={val}
              onClick={() => setParty(val)}
              aria-pressed={party === val}
              className={`px-3 py-2 rounded-lg border text-sm transition ${
                party === val
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        Showing {sorted.length} legislators
      </p>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {sorted.map((l) => (
          <LegislatorCard key={l.id} legislator={l} />
        ))}
      </div>

      {legislators.length === 0 && (
        <p className="text-gray-400 text-sm mt-8">Loading legislators…</p>
      )}
    </div>
  );
}
