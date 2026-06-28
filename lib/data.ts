import fs from "fs";
import path from "path";
import type { Legislator, VoteStats, Bill, PressRelease } from "./types";

const DATA_DIR = path.join(process.cwd(), "data");

function readJson<T>(filePath: string): T | null {
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function safeId(id: string): string {
  return id.replace(/\//g, "_");
}

export function getAllLegislators(): Legislator[] {
  return readJson<Legislator[]>(path.join(DATA_DIR, "legislators.json")) ?? [];
}

export function getLegislatorById(id: string): Legislator | null {
  const all = getAllLegislators();
  return all.find((l) => l.id === id) ?? null;
}

export function getVoteStats(id: string): VoteStats | null {
  return readJson<VoteStats>(
    path.join(DATA_DIR, "votes", `${safeId(id)}.json`)
  );
}

export function getBills(id: string): Bill[] {
  return (
    readJson<Bill[]>(path.join(DATA_DIR, "bills", `${safeId(id)}.json`)) ?? []
  );
}

export function getPressReleases(id: string): PressRelease[] {
  return (
    readJson<PressRelease[]>(
      path.join(DATA_DIR, "press_releases", `${safeId(id)}.json`)
    ) ?? []
  );
}

export function getLastUpdated(): string | null {
  const data = readJson<{ timestamp: string }>(
    path.join(DATA_DIR, "last_updated.json")
  );
  return data?.timestamp ?? null;
}
