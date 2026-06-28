import { type Legislator } from "./types";

export function partyColor(party: string): string {
  if (party === "Democratic") return "democrat";
  if (party === "Republican") return "republican";
  return "independent";
}

export function partyHex(party: string): string {
  if (party === "Democratic") return "#1d4ed8";
  if (party === "Republican") return "#b91c1c";
  return "#6b7280";
}

export function chamberLabel(chamber: "lower" | "upper" | string): string {
  return chamber === "upper" ? "Senate" : "House";
}

export function formatDistrict(legislator: Legislator): string {
  return `${chamberLabel(legislator.chamber)} District ${legislator.district}`;
}

export function pct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function actionTypeBadge(
  type: string
): { label: string; color: string } {
  const map: Record<string, { label: string; color: string }> = {
    bill_introduced: { label: "Bill Introduced", color: "bg-blue-100 text-blue-800" },
    bill_passed: { label: "Bill Passed", color: "bg-green-100 text-green-800" },
    statement: { label: "Statement", color: "bg-gray-100 text-gray-700" },
    event: { label: "Event", color: "bg-purple-100 text-purple-800" },
    award: { label: "Award", color: "bg-yellow-100 text-yellow-800" },
    committee_action: { label: "Committee", color: "bg-orange-100 text-orange-800" },
    budget: { label: "Budget", color: "bg-teal-100 text-teal-800" },
    other: { label: "Other", color: "bg-gray-100 text-gray-600" },
  };
  return map[type] ?? { label: type, color: "bg-gray-100 text-gray-600" };
}
