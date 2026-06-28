"use client";

import { useState } from "react";
import type { Bill } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function BillsList({ bills }: { bills: Bill[] }) {
  const [filter, setFilter] = useState<"all" | "primary" | "instrumental">(
    "all"
  );

  const filtered = bills.filter((b) => {
    if (filter === "primary") return b.sponsorship_role === "primary";
    if (filter === "instrumental") return b.instrumental;
    return true;
  });

  if (bills.length === 0) {
    return (
      <section aria-labelledby="bills-heading">
        <h2 id="bills-heading" className="text-xl font-bold text-gray-900 mb-4">
          Legislation
        </h2>
        <p className="text-gray-500 text-sm">No bill data available.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="bills-heading">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 id="bills-heading" className="text-xl font-bold text-gray-900">
          Legislation{" "}
          <span className="text-base font-normal text-gray-500">
            ({bills.length})
          </span>
        </h2>
        <div
          className="flex gap-2 text-sm"
          role="group"
          aria-label="Filter bills"
        >
          {(
            [
              ["all", "All"],
              ["primary", "Primary sponsor"],
              ["instrumental", "Made progress"],
            ] as const
          ).map(([val, label]) => (
            <button
              key={val}
              onClick={() => setFilter(val)}
              aria-pressed={filter === val}
              className={`px-3 py-1 rounded-full border transition ${
                filter === val
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        {filtered.map((bill) => (
          <div
            key={bill.id}
            className="bg-white border border-gray-200 rounded-lg p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="text-xs font-mono font-semibold text-gray-500">
                    {bill.identifier}
                  </span>
                  {bill.sponsorship_role === "primary" && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-100">
                      Primary
                    </span>
                  )}
                  {bill.instrumental && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-700 border border-green-100">
                      Made progress
                    </span>
                  )}
                  <span className="text-xs text-gray-400">{bill.session}</span>
                </div>
                <p className="text-sm text-gray-900 leading-snug">
                  {bill.title}
                </p>
                {bill.status && (
                  <p className="text-xs text-gray-500 mt-1">
                    Status: {bill.status}
                  </p>
                )}
                {bill.latest_action && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    Last action: {formatDate(bill.latest_action.date)} —{" "}
                    {bill.latest_action.description}
                  </p>
                )}
              </div>
              {bill.openstates_url && (
                <a
                  href={bill.openstates_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`View ${bill.identifier} on OpenStates`}
                  className="text-xs text-blue-600 hover:underline flex-shrink-0"
                >
                  Details →
                </a>
              )}
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-gray-400">
            No bills match this filter.
          </p>
        )}
      </div>
    </section>
  );
}
