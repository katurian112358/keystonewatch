"use client";

import { useState } from "react";
import type { Legislator } from "@/lib/types";
import LegislatorCard from "./LegislatorCard";

interface GeoResult {
  house: Legislator | null;
  senate: Legislator | null;
  error?: string;
}

export default function ZipLookup() {
  const [zip, setZip] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GeoResult | null>(null);

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    if (zip.length !== 5 || !/^\d+$/.test(zip)) return;
    setLoading(true);
    setResult(null);

    try {
      const apiKey = process.env.NEXT_PUBLIC_GOOGLE_CIVIC_API_KEY;
      const url = `https://www.googleapis.com/civicinfo/v2/representatives?address=${zip}+PA&levels=administrativeArea1&roles=legislatorLowerBody&roles=legislatorUpperBody&key=${apiKey}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      // Match officials back to our local legislator data via district
      const divisions: Record<string, { name: string }> =
        data.divisions ?? {};
      const offices: Array<{
        name: string;
        divisionId: string;
        roles: string[];
        officialIndices: number[];
      }> = data.offices ?? [];

      // Extract district numbers from division IDs like
      // ocd-division/country:us/state:pa/sldl:2  or  sldu:2
      let houseDistrict: string | null = null;
      let senateDistrict: string | null = null;

      for (const office of offices) {
        const divId = office.divisionId ?? "";
        const sldlMatch = divId.match(/sldl:(\d+)/);
        const slduMatch = divId.match(/sldu:(\d+)/);
        if (sldlMatch) houseDistrict = sldlMatch[1];
        if (slduMatch) senateDistrict = slduMatch[1];
      }

      // Fetch local data and match
      const legsResp = await fetch("/legislators.json");
      const legs: Legislator[] = legsResp.ok ? await legsResp.json() : [];

      const house = houseDistrict
        ? (legs.find(
            (l) => l.chamber === "lower" && l.district === houseDistrict
          ) ?? null)
        : null;
      const senate = senateDistrict
        ? (legs.find(
            (l) => l.chamber === "upper" && l.district === senateDistrict
          ) ?? null)
        : null;

      if (!house && !senate) {
        setResult({ house: null, senate: null, error: "No PA legislators found for this zip code." });
      } else {
        setResult({ house, senate });
      }
    } catch (err) {
      setResult({
        house: null,
        senate: null,
        error: "Lookup failed. Please try again.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form onSubmit={handleLookup} className="flex gap-3 max-w-sm">
        <input
          type="text"
          inputMode="numeric"
          pattern="\d{5}"
          maxLength={5}
          value={zip}
          onChange={(e) => setZip(e.target.value)}
          placeholder="Enter your ZIP code"
          aria-label="ZIP code"
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-base focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={loading || zip.length !== 5}
          aria-label="Find my representatives"
          className="bg-blue-700 hover:bg-blue-800 disabled:bg-blue-300 text-white rounded-lg px-5 py-2 font-medium transition"
        >
          {loading ? "…" : "Find"}
        </button>
      </form>

      {result?.error && (
        <p className="mt-4 text-red-600 text-sm" role="alert">
          {result.error}
        </p>
      )}

      {result && (result.house || result.senate) && (
        <div className="mt-6">
          <p className="text-sm text-gray-500 mb-3">
            Your Pennsylvania representatives:
          </p>
          <div className="grid sm:grid-cols-2 gap-3 max-w-lg">
            {result.house && (
              <div>
                <p className="text-xs text-gray-400 mb-1 uppercase tracking-wide">
                  State House
                </p>
                <LegislatorCard legislator={result.house} />
              </div>
            )}
            {result.senate && (
              <div>
                <p className="text-xs text-gray-400 mb-1 uppercase tracking-wide">
                  State Senate
                </p>
                <LegislatorCard legislator={result.senate} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
