/**
 * Official metadata for the 17 UN Sustainable Development Goals.
 *
 * Names and official hex colours from the UN SDG branding guidelines
 * (sdgs.un.org). These names should be used verbatim — they are the
 * canonical wording adopted by all UN Member States in 2015.
 *
 * Icon source: 17 PNGs in web/public/sdg/01.png ... 17.png, downloaded
 * from un.org/sustainabledevelopment (free to use per UN guidelines).
 */

export interface SDGMeta {
  num: number;
  /** Short label used in the home grid. */
  label: string;
  /** Full official UN name. */
  fullName: string;
  /** Official UN SDG colour (hex). */
  color: string;
}

export const SDG_META: SDGMeta[] = [
  { num: 1, label: "No poverty", fullName: "No Poverty", color: "#E5243B" },
  { num: 2, label: "Zero hunger", fullName: "Zero Hunger", color: "#DDA63A" },
  { num: 3, label: "Good health", fullName: "Good Health and Well-being", color: "#4C9F38" },
  { num: 4, label: "Quality education", fullName: "Quality Education", color: "#C5192D" },
  { num: 5, label: "Gender equality", fullName: "Gender Equality", color: "#FF3A21" },
  { num: 6, label: "Clean water", fullName: "Clean Water and Sanitation", color: "#26BDE2" },
  { num: 7, label: "Clean energy", fullName: "Affordable and Clean Energy", color: "#FCC30B" },
  { num: 8, label: "Decent work", fullName: "Decent Work and Economic Growth", color: "#A21942" },
  { num: 9, label: "Industry & infra.", fullName: "Industry, Innovation and Infrastructure", color: "#FD6925" },
  { num: 10, label: "Reduced inequalities", fullName: "Reduced Inequalities", color: "#DD1367" },
  { num: 11, label: "Sustainable cities", fullName: "Sustainable Cities and Communities", color: "#FD9D24" },
  { num: 12, label: "Resp. consumption", fullName: "Responsible Consumption and Production", color: "#BF8B2E" },
  { num: 13, label: "Climate action", fullName: "Climate Action", color: "#3F7E44" },
  { num: 14, label: "Life below water", fullName: "Life Below Water", color: "#0A97D9" },
  { num: 15, label: "Life on land", fullName: "Life on Land", color: "#56C02B" },
  { num: 16, label: "Peace & justice", fullName: "Peace, Justice and Strong Institutions", color: "#00689D" },
  { num: 17, label: "Partnerships", fullName: "Partnerships for the Goals", color: "#19486A" },
];

/** Zero-padded ID for icon lookup (e.g. 1 → "01"). */
export function sdgIconId(num: number): string {
  return num.toString().padStart(2, "0");
}
