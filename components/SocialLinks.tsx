import type { Legislator } from "@/lib/types";

const ICONS: Record<string, string> = {
  twitter: "𝕏",
  facebook: "f",
  instagram: "▣",
  youtube: "▶",
  linkedin: "in",
};

export default function SocialLinks({ legislator }: { legislator: Legislator }) {
  const social = legislator.social_links;
  const entries = Object.entries(social).filter(([, url]) => url);

  if (entries.length === 0) return null;

  return (
    <section aria-labelledby="social-heading">
      <h2 id="social-heading" className="text-xl font-bold text-gray-900 mb-4">
        Social &amp; Web
      </h2>
      <div className="flex flex-wrap gap-3">
        {entries.map(([platform, url]) => (
          <a
            key={platform}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${legislator.name} on ${platform}`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-gray-200 bg-white hover:border-gray-300 text-sm text-gray-700 transition"
          >
            <span aria-hidden="true">{ICONS[platform] ?? "↗"}</span>
            {platform.charAt(0).toUpperCase() + platform.slice(1)}
          </a>
        ))}
      </div>
    </section>
  );
}
