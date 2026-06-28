import { notFound } from "next/navigation";
import Image from "next/image";
import {
  getAllLegislators,
  getLegislatorById,
  getVoteStats,
  getBills,
  getPressReleases,
} from "@/lib/data";
import { chamberLabel, formatDistrict, partyHex } from "@/lib/utils";
import VotingTrendChart from "@/components/VotingTrendChart";
import BillsList from "@/components/BillsList";
import PressReleases from "@/components/PressReleases";
import SocialLinks from "@/components/SocialLinks";
import ContactBlock from "@/components/ContactBlock";

// Use safe ID (slashes → underscores) in URLs to avoid Next.js encoding issues
function toSafeId(id: string) {
  return id.replace(/\//g, "_");
}

function fromSafeId(safeId: string, legislators: ReturnType<typeof getAllLegislators>) {
  return legislators.find((l) => toSafeId(l.id) === safeId) ?? null;
}

export async function generateStaticParams() {
  const legislators = getAllLegislators();
  return legislators.map((l) => ({ id: toSafeId(l.id) }));
}

export async function generateMetadata({
  params,
}: {
  params: { id: string };
}) {
  const legislator = fromSafeId(params.id, getAllLegislators());
  if (!legislator) return {};
  return {
    title: `${legislator.name} — Keystone Watch`,
    description: `Voting record, bills, and press releases for ${legislator.name}, ${formatDistrict(legislator)}.`,
  };
}

export default function LegislatorPage({
  params,
}: {
  params: { id: string };
}) {
  const legislator = fromSafeId(params.id, getAllLegislators());
  const id = legislator?.id ?? "";
  if (!legislator) notFound();

  const votes = getVoteStats(id);
  const bills = getBills(id);
  const pressReleases = getPressReleases(id);
  const accentColor = partyHex(legislator.party);

  return (
    <div>
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="mb-6 text-sm text-gray-500">
        <a href="/" className="hover:text-gray-700">
          Home
        </a>{" "}
        /{" "}
        <a href="/legislators" className="hover:text-gray-700">
          Legislators
        </a>{" "}
        / <span className="text-gray-900">{legislator.name}</span>
      </nav>

      {/* Header */}
      <div
        className="bg-white rounded-xl border border-gray-200 p-6 mb-8"
        style={{ borderTopColor: accentColor, borderTopWidth: 4 }}
      >
        <div className="flex items-start gap-5">
          {legislator.image_url ? (
            <Image
              src={legislator.image_url}
              alt={legislator.name}
              width={96}
              height={96}
              className="rounded-full object-cover w-24 h-24 flex-shrink-0"
              unoptimized
              priority
            />
          ) : (
            <div className="w-24 h-24 rounded-full bg-gray-200 flex-shrink-0" />
          )}
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              {legislator.name}
            </h1>
            <p className="text-lg text-gray-600 mt-1">
              {legislator.title},{" "}
              <span style={{ color: accentColor }}>{legislator.party}</span>
            </p>
            <p className="text-gray-500 mt-0.5">{formatDistrict(legislator)}</p>
            <div className="flex gap-3 mt-3 flex-wrap">
              <span className="text-sm px-3 py-1 rounded-full bg-gray-100 text-gray-700">
                PA {chamberLabel(legislator.chamber)}
              </span>
              <span
                className="text-sm px-3 py-1 rounded-full text-white"
                style={{ backgroundColor: accentColor }}
              >
                {legislator.party}
              </span>
              {legislator.openstates_url && (
                <a
                  href={legislator.openstates_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm px-3 py-1 rounded-full border border-gray-200 bg-white text-gray-600 hover:border-gray-400"
                  aria-label="View on OpenStates"
                >
                  OpenStates ↗
                </a>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Content sections */}
      <div className="space-y-10">
        {votes ? (
          <VotingTrendChart stats={votes} />
        ) : (
          <section>
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              Voting Record
            </h2>
            <p className="text-gray-500 text-sm">
              Voting data not yet available.
            </p>
          </section>
        )}

        <BillsList bills={bills} />

        <PressReleases releases={pressReleases} />

        {Object.keys(legislator.social_links).length > 0 && (
          <SocialLinks legislator={legislator} />
        )}

        <ContactBlock legislator={legislator} />
      </div>
    </div>
  );
}
