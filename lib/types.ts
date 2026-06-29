export interface Legislator {
  id: string;
  name: string;
  party: "Democratic" | "Republican" | "Independent" | string;
  chamber: "lower" | "upper";
  district: string;
  title: string;
  image_url: string | null;
  openstates_url: string;
  web_links: string[];
  social_links: Record<string, string>;
  contact_details: Record<string, string>;
}

export interface VoteRecord {
  bill_id: string | null;
  bill_identifier: string | null;
  bill_title: string | null;
  vote: "yes" | "no" | "absent" | "abstain" | "not voting" | "excused" | string;
  date: string | null;
  motion: string | null;
  yes_total: number;
  no_total: number;
  party_majority?: "yes" | "no" | null;
}

export interface VoteStats {
  legislator_id: string;
  total_votes: number;
  yes_count: number;
  no_count: number;
  absent_count: number;
  attendance_rate: number | null;
  partisan_score: number | null;
  party_unity_score: number | null;
  recent_votes: VoteRecord[];
}

export interface BillAction {
  id: string;
  description: string;
  date: string;
  classification: string[];
  organization: { name: string; classification: string };
}

export interface Bill {
  id: string;
  identifier: string;
  title: string;
  session: string;
  status: string | null;
  subjects: string[];
  latest_action: BillAction | null;
  openstates_url: string;
  sponsorship_role: "primary" | "cosponsor";
  instrumental: boolean;
}

export interface AiSummary {
  summary: string;
  action_type:
    | "bill_introduced"
    | "bill_passed"
    | "statement"
    | "event"
    | "award"
    | "committee_action"
    | "budget"
    | "other";
  topics: string[];
  spin_flag: boolean;
}

export interface PressRelease {
  title: string;
  url: string;
  date: string | null;
  raw_text: string;
  ai_summary: AiSummary | null;
}

export interface LegislatorPageData {
  legislator: Legislator;
  votes: VoteStats | null;
  bills: Bill[];
  pressReleases: PressRelease[];
}
