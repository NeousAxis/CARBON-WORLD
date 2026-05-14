/**
 * Official metadata for the 9 Planetary Boundaries (Rockström et al. 2009,
 * with the 2023 update from Richardson et al. — added novel entities and
 * split freshwater into green/blue components).
 *
 * Source of authoritative status (transgressed / at-limit / within):
 * Stockholm Resilience Centre 2023 Planetary Health Check
 * https://www.stockholmresilience.org/planetary-boundaries.html
 *
 * Each boundary carries a keyword pattern array. The home grid counts
 * how many BURN events (positive aspects mention these keywords) or MINT
 * events (negative aspects mention them) per boundary over the last 7 days.
 * This is approximate (~80 % recall) because the Analyst only tags an aspect
 * with a generic "PB" framework label, not the specific boundary number.
 * A future analyst-prompt update could tag the specific PB to reach 100 %.
 */

export type PBStatus = "transgressed" | "at_limit" | "safe";

export interface PBMeta {
  slug: string;
  num: number;
  label: string;
  fullName: string;
  status: PBStatus;
  /** Regex patterns used to match this boundary in aspect descriptions / titles. */
  patterns: RegExp[];
}

export const PB_META: PBMeta[] = [
  {
    slug: "climate",
    num: 1,
    label: "Climate change",
    fullName: "Climate change",
    status: "transgressed",
    patterns: [
      /\bclimate\b/i, /\bemission/i, /\bwarming\b/i, /\bCO2\b/, /\bcarbon\b/i,
      /\bgreenhouse\b/i, /\bfossil\b/i, /\bdecarbon/i, /\b1\.5\s*°?C\b/i,
    ],
  },
  {
    slug: "biosphere",
    num: 2,
    label: "Biosphere integrity",
    fullName: "Biosphere integrity (loss of biodiversity)",
    status: "transgressed",
    patterns: [
      /\bbiodivers/i, /\bspecies\b/i, /\bextinct/i, /\becosystem/i, /\bwildlife\b/i,
      /\bhabitat\b/i, /\bendangered\b/i, /\bconservation\b/i, /\bpoach/i,
    ],
  },
  {
    slug: "land",
    num: 3,
    label: "Land-system change",
    fullName: "Land-system change",
    status: "transgressed",
    patterns: [
      /\bdeforest/i, /\bland use\b/i, /\bforest clear/i, /\burban sprawl\b/i,
      /\bagriculture expansion\b/i, /\bsoil\b/i, /\bland grab\b/i, /\barable\b/i,
    ],
  },
  {
    slug: "freshwater",
    num: 4,
    label: "Freshwater change",
    fullName: "Freshwater change (green & blue water)",
    status: "transgressed",
    patterns: [
      /\baquifer\b/i, /\bdrought\b/i, /\bfreshwater\b/i, /\birrigation\b/i,
      /\bgroundwater\b/i, /\briver flow\b/i, /\bwater scarcity\b/i, /\bwater stress\b/i,
    ],
  },
  {
    slug: "biogeochem",
    num: 5,
    label: "Biogeochemical flows",
    fullName: "Biogeochemical flows (nitrogen, phosphorus)",
    status: "transgressed",
    patterns: [
      /\bnitrogen\b/i, /\bphosphorus\b/i, /\bfertilizer/i, /\brunoff\b/i,
      /\beutrophic/i, /\balgae bloom\b/i, /\bdead zone\b/i,
    ],
  },
  {
    slug: "novel-entities",
    num: 6,
    label: "Novel entities",
    fullName: "Novel entities (synthetic chemicals, plastics)",
    status: "transgressed",
    patterns: [
      /\bmicroplastic/i, /\bPFAS\b/, /\bplastic[s]?\b/i, /\bchemical[s]?\b/i,
      /\btoxic\b/i, /\bpesticide/i, /\bherbicide\b/i, /\be-?waste\b/i, /\btailings?\b/i,
    ],
  },
  {
    slug: "ocean-acid",
    num: 7,
    label: "Ocean acidification",
    fullName: "Ocean acidification",
    status: "at_limit",
    patterns: [
      /\bocean acid/i, /\bmarine acid/i, /\bcoral\b/i, /\bpH ocean\b/i,
      /\bshell/i, /\breef\b/i, /\bocean chemistry\b/i,
    ],
  },
  {
    slug: "aerosols",
    num: 8,
    label: "Atmospheric aerosols",
    fullName: "Atmospheric aerosol loading",
    status: "safe",
    patterns: [
      /\baerosol/i, /\bparticulate\b/i, /\bair pollut/i, /\bsmog\b/i, /\bPM2\.5\b/,
      /\bPM10\b/, /\bair quality\b/i,
    ],
  },
  {
    slug: "ozone",
    num: 9,
    label: "Stratospheric ozone",
    fullName: "Stratospheric ozone depletion",
    status: "safe",
    patterns: [
      /\bozone\b/i, /\bUV\b/, /\bCFC\b/, /\bmontreal protocol\b/i,
      /\bHCFC\b/, /\bstratospher/i,
    ],
  },
];

export const PB_STATUS_COLOR: Record<PBStatus, string> = {
  transgressed: "#FF5C33",  // red
  at_limit: "#FCC30B",      // yellow
  safe: "#56C02B",          // green
};

export const PB_STATUS_LABEL: Record<PBStatus, string> = {
  transgressed: "Transgressed",
  at_limit: "At limit",
  safe: "Within safe zone",
};
