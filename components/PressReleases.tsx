"use client";

import { useState } from "react";
import type { PressRelease } from "@/lib/types";
import { formatDate, actionTypeBadge } from "@/lib/utils";

function Release({ release }: { release: PressRelease }) {
  const [expanded, setExpanded] = useState(false);
  const summary = release.ai_summary;
  const badge = summary ? actionTypeBadge(summary.action_type) : null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {badge && (
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge.color}`}
              >
                {badge.label}
              </span>
            )}
            {summary?.spin_flag && (
              <span
                className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-100"
                title="This release contains significant self-promotional framing"
              >
                ⚠ Spin detected
              </span>
            )}
            {summary?.topics?.map((t) => (
              <span
                key={t}
                className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600"
              >
                {t}
              </span>
            ))}
          </div>
          <p className="font-medium text-sm text-gray-900 leading-snug">
            {release.title}
          </p>
          {release.date && (
            <p className="text-xs text-gray-400 mt-0.5">
              {formatDate(release.date)}
            </p>
          )}
        </div>
        <a
          href={release.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Read original: ${release.title}`}
          className="text-xs text-blue-600 hover:underline flex-shrink-0"
        >
          Original →
        </a>
      </div>

      {summary ? (
        <div>
          <p className="text-sm text-gray-700 leading-relaxed">
            {summary.summary}
          </p>
          <button
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            className="mt-2 text-xs text-gray-400 hover:text-gray-600 underline"
          >
            {expanded ? "Hide original text" : "Show original press release"}
          </button>
          {expanded && (
            <div className="mt-3 p-3 bg-gray-50 rounded text-xs text-gray-600 whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
              {release.raw_text}
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-gray-400 italic">Summary unavailable.</p>
      )}
    </div>
  );
}

export default function PressReleases({
  releases,
}: {
  releases: PressRelease[];
}) {
  if (releases.length === 0) {
    return (
      <section aria-labelledby="releases-heading">
        <h2
          id="releases-heading"
          className="text-xl font-bold text-gray-900 mb-4"
        >
          What They&apos;ve Done
        </h2>
        <p className="text-gray-500 text-sm">
          No press releases available.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="releases-heading">
      <h2
        id="releases-heading"
        className="text-xl font-bold text-gray-900 mb-4"
      >
        What They&apos;ve Done{" "}
        <span className="text-base font-normal text-gray-500">
          ({releases.length} releases, AI-summarized)
        </span>
      </h2>
      <div className="space-y-3">
        {releases.map((r, i) => (
          <Release key={r.url ?? i} release={r} />
        ))}
      </div>
    </section>
  );
}
