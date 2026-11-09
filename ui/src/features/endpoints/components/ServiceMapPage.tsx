import { Link } from "react-router";

import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { MAP_NODE_HEIGHT, MAP_NODE_WIDTH, MAP_STATUS_NAMES, NO_MAP_NOTE, SERVICE_MAP_DESCRIPTION } from "../../../constants/traces";
import { edgeLabel, kindName, nodeFacts, type PlacedEdge, type PlacedNode } from "../../../lib/serviceMap";
import type { MapKind, MapNode } from "../api";
import { useServiceMap } from "../hooks/useServiceMap";
import { ApiTabs } from "./ApiTabs";
import { MapLogo } from "./MapLogo";
import { RangeControls } from "./RangeControls";

/** What calls what in the project, drawn from requests, with the chosen box's details. */
export function ServiceMapPage() {
  const serviceMap = useServiceMap();
  const { map, layout, project, range, chosen } = serviceMap;
  const kinds = new Map(map?.nodes.map((node) => [node.id, node.kind]));
  return (
    <div className="setup-page">
      <ApiTabs />
      <header className="page-heading page-heading-row">
        <div className="page-heading">
          <h1 className="page-title">Service map</h1>
          <p className="text-secondary">{SERVICE_MAP_DESCRIPTION}</p>
          <p className="text-secondary">
            <strong className="text-primary">
              {project ? `${project.client} · ${project.project} · ${project.environment}` : "This project"}
            </strong>{" "}
            · <strong className="text-primary">{range.name}</strong>
          </p>
        </div>
        <RangeControls range={range} />
      </header>
      {serviceMap.error && <ErrorBanner error={serviceMap.error} />}
      {map?.nodes.length === 0 && <p className="panel text-secondary">{NO_MAP_NOTE}</p>}
      {map && layout && layout.nodes.length > 0 && (
        <div className="service-map-split">
          <section className="panel service-map" aria-label="Map">
            <div className="service-map-canvas" style={{ width: layout.width, height: layout.height }}>
              <svg className="service-map-lines" width={layout.width} height={layout.height} aria-hidden="true">
                <defs>
                  <marker id="map-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                    <path d="M0 0L10 5L0 10z" className="service-map-arrow" />
                  </marker>
                </defs>
                {layout.edges.map((placed) => (
                  <MapLine
                    key={`${placed.edge.source} ${placed.edge.target}`}
                    placed={placed}
                    targetKind={kinds.get(placed.edge.target) ?? "external"}
                    rangeSeconds={map.range_seconds}
                  />
                ))}
              </svg>
              {layout.nodes.map((placed) => (
                <MapBox
                  key={placed.node.id}
                  placed={placed}
                  chosen={placed.node.id === chosen?.id}
                  onSelect={serviceMap.select}
                />
              ))}
            </div>
          </section>
          {chosen && (
            <aside className="panel service-map-details" aria-label="Details">
              <span className="text-secondary text-sm">{kindName(chosen.kind)}</span>
              <h2 className="panel-title service-map-title">
                <MapLogo kind={chosen.kind} name={chosen.name} />
                {chosen.name}
              </h2>
              <span className="service-map-status" data-status={chosen.status}>
                {MAP_STATUS_NAMES[chosen.status]}
              </span>
              <dl className="service-map-facts">
                {nodeFacts(chosen, map.range_seconds).map(([name, value]) => (
                  <div key={name}>
                    <dt className="text-secondary">{name}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              {serviceMap.chosenLink && <Link to={serviceMap.chosenLink.to}>{serviceMap.chosenLink.label} →</Link>}
            </aside>
          )}
        </div>
      )}
    </div>
  );
}

/** One line with its rate and time (or failures), coloured by status. */
function MapLine({ placed, targetKind, rangeSeconds }: { placed: PlacedEdge; targetKind: MapKind; rangeSeconds: number }) {
  return (
    <g className="service-map-line" data-status={placed.edge.status}>
      <path d={placed.path} markerEnd="url(#map-arrow)" />
      <text x={placed.labelX} y={placed.labelY} textAnchor="middle">
        {edgeLabel(placed.edge, targetKind, rangeSeconds)}
      </text>
    </g>
  );
}

interface MapBoxProps {
  placed: PlacedNode;
  chosen: boolean;
  onSelect: (node: MapNode) => void;
}

/** One box: its name and kind; selecting it shows its details. */
function MapBox({ placed, chosen, onSelect }: MapBoxProps) {
  return (
    <button
      type="button"
      className="service-map-box"
      data-status={placed.node.status}
      aria-pressed={chosen}
      style={{ left: placed.x, top: placed.y, width: MAP_NODE_WIDTH, height: MAP_NODE_HEIGHT }}
      onClick={() => {
        onSelect(placed.node);
      }}
    >
      <MapLogo kind={placed.node.kind} name={placed.node.name} />
      <span className="service-map-label">
        <span className="service-map-name" title={placed.node.name}>
          {placed.node.name}
        </span>
        <span className="text-secondary text-xs">{kindName(placed.node.kind)}</span>
      </span>
    </button>
  );
}
