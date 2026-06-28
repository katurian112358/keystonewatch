"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { VoteStats } from "@/lib/types";
import { pct, formatDate } from "@/lib/utils";

const VOTE_COLORS: Record<string, string> = {
  yes: "#16a34a",
  no: "#dc2626",
  absent: "#9ca3af",
  abstain: "#d97706",
  excused: "#9ca3af",
  "not voting": "#9ca3af",
};

export default function VotingTrendChart({ stats }: { stats: VoteStats }) {
  const gaugeData = [
    {
      name: "Attendance",
      value: stats.attendance_rate != null ? Math.round(stats.attendance_rate * 100) : 0,
      label: pct(stats.attendance_rate),
    },
    {
      name: "With majority",
      value: stats.partisan_score != null ? Math.round(stats.partisan_score * 100) : 0,
      label: pct(stats.partisan_score),
    },
  ];

  const recentVotes = stats.recent_votes.slice(0, 20).map((v, i) => ({
    index: i + 1,
    vote: v.vote,
    bill: v.bill_identifier ?? "—",
    title: (v.bill_title ?? "").slice(0, 60),
    date: formatDate(v.date),
    color: VOTE_COLORS[v.vote] ?? "#9ca3af",
  }));

  return (
    <section aria-labelledby="voting-heading">
      <h2
        id="voting-heading"
        className="text-xl font-bold text-gray-900 mb-4"
      >
        Voting Record
      </h2>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {[
          { label: "Total votes", value: stats.total_votes.toLocaleString() },
          { label: "Attendance rate", value: pct(stats.attendance_rate) },
          { label: "Voted with majority", value: pct(stats.partisan_score) },
          { label: "Absent / excused", value: stats.absent_count.toLocaleString() },
        ].map(({ label, value }) => (
          <div
            key={label}
            className="bg-white border border-gray-200 rounded-lg p-3 text-center"
          >
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            <p className="text-xs text-gray-500 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Bar chart */}
      {gaugeData.some((d) => d.value > 0) && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
          <p className="text-sm font-medium text-gray-700 mb-3">
            Participation metrics
          </p>
          <div aria-hidden="true">
            <ResponsiveContainer width="100%" height={120}>
              <BarChart data={gaugeData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  <Cell fill="#1d4ed8" />
                  <Cell fill="#7c3aed" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {/* Accessible table fallback */}
          <table className="sr-only">
            <caption>Participation metrics</caption>
            <tbody>
              {gaugeData.map((d) => (
                <tr key={d.name}>
                  <th scope="row">{d.name}</th>
                  <td>{d.label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Recent votes table */}
      {recentVotes.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <p className="text-sm font-medium text-gray-700 p-4 pb-2">
            Last {recentVotes.length} votes
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th
                    scope="col"
                    className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase"
                  >
                    Bill
                  </th>
                  <th
                    scope="col"
                    className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase"
                  >
                    Title
                  </th>
                  <th
                    scope="col"
                    className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase"
                  >
                    Vote
                  </th>
                  <th
                    scope="col"
                    className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase"
                  >
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentVotes.map((v) => (
                  <tr key={`${v.bill}-${v.index}`} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-mono text-xs text-gray-600">
                      {v.bill}
                    </td>
                    <td className="px-4 py-2 text-gray-700 max-w-xs truncate">
                      {v.title}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className="font-semibold capitalize"
                        style={{ color: v.color }}
                      >
                        {v.vote}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                      {v.date}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {stats.total_votes === 0 && (
        <p className="text-gray-500 text-sm">
          No voting data available for this legislator.
        </p>
      )}
    </section>
  );
}
