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
  const [address, setAddress] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GeoResult | null>(null);

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    if (!address.trim()) return;
    setLoading(true);
    setResult(null);

    try {
      const apiKey = process.env.NEXT_PUBLIC_GOOGLE_CIVIC_API_KEY;
      // Google's `representatives` endpoint was retired in 2025; `divisionsByAddress`
      // is still available and returns the OCD division IDs (incl. state legislative
      // districts) for an address, which we map to our local legislator data.
      const url = `https://www.googleapis.com/civicinfo/v2/divisionsByAddress?address=${encodeURIComponent(
        address
      )}&key=${apiKey}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      // divisions is an object keyed by division ID, e.g.
      // "ocd-division/country:us/state:pa/sldl:1" (House) / ".../sldu:49" (Senate)
      const divisionIds = Object.keys(data.divisions ?? {});
      let houseDistrict: string | null = null;
      let senateDistrict: string | null = null;
      for (const id of divisionIds) {
        const sldl = id.match(/sldl:(\d+)/);
        const sldu = id.match(/sldu:(\d+)/);
        if (sldl) houseDistrict = String(parseInt(sldl[1], 10));
        if (sldu) senateDistrict = String(parseInt(sldu[1], 10));
      }

      if (!houseDistrict && !senateDistrict) {
        setResult({
          house: null,
          senate: null,
          error:
            "Couldn't pinpoint your districts. Try a full street address (e.g. 123 Main St, Erie PA 16501).",
        });
        return;
      }

      const legsResp = await fetch("/legislators.json");
      const legs: Legislator[] = legsResp.ok ? await legsResp.json() : [];

      const house = houseDistrict
        ? legs.find((l) => l.chamber === "lower" && l.district === houseDistrict) ??
          null
        : null;
      const senate = senateDistrict
        ? legs.find((l) => l.chamber === "upper" && l.district === senateDistrict) ??
          null
        : null;

      if (!house && !senate) {
        setResult({
          house: null,
          senate: null,
          error: "No matching PA legislators found for that address.",
        });
      } else {
        setResult({ house, senate });
      }
    } catch {
      setResult({
        house: null,
        senate: null,
        error: "Lookup failed. Please try again with a full street address.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form onSubmit={handleLookup} className="flex gap-3 max-w-xl">
        <input
          type="text"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="123 Main St, Erie PA 16501"
          aria-label="Your home address"
          autoComplete="street-address"
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-base focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={loading || !address.trim()}
          aria-label="Find my representatives"
          className="bg-blue-700 hover:bg-blue-800 disabled:bg-blue-300 text-white rounded-lg px-5 py-2 font-medium transition whitespace-nowrap"
        >
          {loading ? "…" : "Find"}
        </button>
      </form>
      <p className="text-xs text-gray-400 mt-2">
        A full street address gives the most accurate result — a ZIP code alone
        often spans multiple House districts.
      </p>

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
