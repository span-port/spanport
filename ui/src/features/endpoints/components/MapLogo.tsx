import { MAP_KIND_ICONS } from "../../../constants/mapLogos";
import { brandLogo } from "../../../lib/mapLogos";
import type { MapKind } from "../api";

/** A box's logo: the brand's when its name names one, else a drawn icon for its kind. */
export function MapLogo({ kind, name }: { kind: MapKind; name: string }) {
  const logo = brandLogo(kind, name);
  return (
    <svg className="map-logo" viewBox="0 0 24 24" aria-hidden="true" data-brand={logo?.title}>
      {logo ? (
        <path d={logo.path} fill={logo.color ?? "currentColor"} />
      ) : (
        <path d={MAP_KIND_ICONS[kind]} className="map-logo-drawn" />
      )}
    </svg>
  );
}
