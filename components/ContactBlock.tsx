import type { Legislator } from "@/lib/types";

export default function ContactBlock({
  legislator,
}: {
  legislator: Legislator;
}) {
  const c = legislator.contact_details;
  const website = c["website"] || legislator.web_links[0];

  return (
    <section aria-labelledby="contact-heading">
      <h2
        id="contact-heading"
        className="text-xl font-bold text-gray-900 mb-4"
      >
        Contact
      </h2>
      <div className="bg-white rounded-lg border border-gray-200 p-5 grid gap-3 sm:grid-cols-2">
        {c["email"] && (
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
              Email
            </p>
            <a
              href={`mailto:${c["email"]}`}
              className="text-blue-700 hover:underline text-sm"
            >
              {c["email"]}
            </a>
          </div>
        )}
        {c["voice"] ||
          (c["phone"] && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
                Phone
              </p>
              <a
                href={`tel:${c["voice"] || c["phone"]}`}
                className="text-sm text-gray-900"
              >
                {c["voice"] || c["phone"]}
              </a>
            </div>
          ))}
        {c["address"] && (
          <div className="sm:col-span-2">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
              Office
            </p>
            <p className="text-sm text-gray-900 whitespace-pre-line">
              {c["address"]}
            </p>
          </div>
        )}
        {website && (
          <div className="sm:col-span-2">
            <a
              href={website}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-blue-700 hover:underline"
              aria-label={`${legislator.name}'s official website`}
            >
              Official website →
            </a>
          </div>
        )}
      </div>
    </section>
  );
}
