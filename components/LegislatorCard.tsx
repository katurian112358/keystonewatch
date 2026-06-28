import Image from "next/image";
import type { Legislator } from "@/lib/types";
import { chamberLabel, formatDistrict, partyHex } from "@/lib/utils";

interface Props {
  legislator: Legislator;
}

export default function LegislatorCard({ legislator }: Props) {
  const borderColor = partyHex(legislator.party);

  return (
    <a
      href={`/legislators/${legislator.id.replace(/\//g, "_")}`}
      className="block bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all p-4"
      style={{ borderLeftColor: borderColor, borderLeftWidth: 4 }}
    >
      <div className="flex items-center gap-3">
        {legislator.image_url ? (
          <Image
            src={legislator.image_url}
            alt={legislator.name}
            width={48}
            height={48}
            className="rounded-full object-cover flex-shrink-0 w-12 h-12"
            unoptimized
          />
        ) : (
          <div className="w-12 h-12 rounded-full bg-gray-200 flex-shrink-0" />
        )}
        <div className="min-w-0">
          <p className="font-semibold text-gray-900 truncate">
            {legislator.name}
          </p>
          <p className="text-sm text-gray-500">{formatDistrict(legislator)}</p>
          <p
            className="text-xs mt-0.5 font-medium"
            style={{ color: borderColor }}
          >
            {legislator.party} · {chamberLabel(legislator.chamber)}
          </p>
        </div>
      </div>
    </a>
  );
}
