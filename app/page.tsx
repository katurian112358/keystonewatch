import { getLastUpdated } from "@/lib/data";
import { formatDate } from "@/lib/utils";
import ZipLookup from "@/components/ZipLookup";

export default function HomePage() {
  const lastUpdated = getLastUpdated();

  return (
    <div>
      <div className="mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-3">
          Track your Pennsylvania representatives
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl">
          Nonpartisan voting records, sponsored bills, and plain-language
          summaries of press releases for all 253 Pennsylvania state
          legislators.
        </p>
        {lastUpdated && (
          <p className="text-sm text-gray-400 mt-2">
            Data updated {formatDate(lastUpdated)}
          </p>
        )}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-10 max-w-2xl">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">
          Find your representatives
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Enter your Pennsylvania ZIP code to see your House and Senate members.
        </p>
        <ZipLookup />
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900">
          All legislators
        </h2>
        <a
          href="/legislators"
          className="text-sm text-blue-700 hover:underline"
        >
          View full directory →
        </a>
      </div>
      <p className="text-gray-500 text-sm">
        Browse all 251 current Pennsylvania state legislators in the{" "}
        <a href="/legislators" className="text-blue-700 hover:underline">
          full directory
        </a>
        , filterable by chamber and party.
      </p>
    </div>
  );
}
