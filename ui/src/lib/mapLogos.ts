// Which logo a service map box shows: a brand's (from simple-icons) when its name names one.
import {
  HEX_RADIX,
  LUMINANCE_WEIGHTS,
  MAP_LOGOS,
  MAX_COLOR_CHANNEL,
  MIN_LOGO_LUMINANCE,
} from "../constants/mapLogos";
import type { MapKind } from "../features/endpoints/api";

export interface BrandLogo {
  title: string;
  /** SVG path on a 24 × 24 view box, drawn filled. */
  path: string;
  /** "#RRGGBB", or null to use the text colour (the brand colour is too dark to see). */
  color: string | null;
}

/** How light a "RRGGBB" colour looks, 0 (black) to 1 (white). */
export function luminance(hex: string): number {
  const channels = [0, 2, 4].map((start) => parseInt(hex.slice(start, start + 2), HEX_RADIX) / MAX_COLOR_CHANNEL);
  return channels.reduce((total, channel, index) => total + channel * (LUMINANCE_WEIGHTS[index] ?? 0), 0);
}

/**
 * The brand logo for a box, or null for your own services and names no brand matches (they
 * get their kind's drawn icon).
 */
export function brandLogo(kind: MapKind, name: string): BrandLogo | null {
  if (kind === "service") return null;
  const lowerName = name.toLowerCase();
  const match = MAP_LOGOS.find((logo) => logo.keywords.some((keyword) => lowerName.includes(keyword)));
  if (!match) return null;
  const { title, path, hex } = match.icon;
  return { title, path, color: luminance(hex) < MIN_LOGO_LUMINANCE ? null : `#${hex}` };
}
