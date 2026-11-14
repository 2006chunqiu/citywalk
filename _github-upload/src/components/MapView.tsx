import { useEffect, useRef } from "react";
import {
  Map,
  MapControls,
  MapMarker,
  MapRoute,
  MarkerContent,
  MarkerPopup,
  type MapRef,
  useMap,
} from "amapcn";
import { Navigation } from "lucide-react";
import { StopThumb } from "@/components/StopThumb";
import { amapMarkerUrl, type Route } from "@/data/routes";
import { cn } from "@/lib/utils";

interface MapViewProps {
  route: Route | null;
  path?: Array<[number, number]> | null;
  activeStop: number | null;
  onSelectStop: (index: number) => void;
  amapKey?: string;
  securityJsCode?: string;
  mapRef?: React.RefObject<MapRef | null>;
  onError: () => void;
}

const WUHAN_CENTER: [number, number] = [114.305, 30.593];
const WUHAN_BOUNDS: [[number, number], [number, number]] = [
  [113.79, 30.12],
  [114.95, 30.95],
];

function StopFocus({ stop }: { stop: [number, number] | null }) {
  const { map, isLoaded } = useMap();
  useEffect(() => {
    if (!map || !isLoaded || !stop) return;
    map.setZoomAndCenter(15.6, stop, false, 500);
  }, [map, isLoaded, stop?.[0], stop?.[1]]);
  return null;
}

export function MapView({
  route,
  path,
  activeStop,
  onSelectStop,
  amapKey,
  securityJsCode,
  mapRef,
  onError,
}: MapViewProps) {
  const hasRoute = !!route;
  const centerRef = useRef(WUHAN_CENTER);
  const boundsRef = useRef(WUHAN_BOUNDS);
  const zoomRef = useRef(11);

  if (route) {
    centerRef.current = [
      route.stops[Math.floor(route.stops.length / 2)].lng,
      route.stops[Math.floor(route.stops.length / 2)].lat,
    ];
    const lngs = route.stops.map((s) => s.lng);
    const lats = route.stops.map((s) => s.lat);
    const pad = 0.012;
    boundsRef.current = [
      [Math.min(...lngs) - pad, Math.min(...lats) - pad],
      [Math.max(...lngs) + pad, Math.max(...lats) + pad],
    ];
    zoomRef.current = 13;
  }

  const active = hasRoute && activeStop !== null ? route!.stops[activeStop] : null;

  return (
    <Map
      ref={mapRef}
      amapKey={amapKey || undefined}
      securityJsCode={securityJsCode || undefined}
      center={centerRef.current}
      zoom={zoomRef.current}
      bounds={boundsRef.current}
      viewMode="2D"
      styles={{
        light: "amap://styles/whitesmoke",
        dark: "amap://styles/darkblue",
      }}
      className="h-full w-full"
      onError={onError}
    >
      <StopFocus stop={active ? [active.lng, active.lat] : null} />

      {route && (
        <MapRoute
          coordinates={
            path && path.length > 1 ? path : route.stops.map((s) => [s.lng, s.lat])
          }
          color={route.color}
          width={6}
          opacity={0.85}
        />
      )}

      {route &&
        route.stops.map((stop, index) => {
          const isActive = activeStop === index;
          return (
            <MapMarker
              key={`${route.id}-${stop.name}`}
              longitude={stop.lng}
              latitude={stop.lat}
              zIndex={isActive ? 130 : 100}
              onClick={() => onSelectStop(index)}
            >
              <MarkerContent>
                <div className="-translate-x-1/2 -translate-y-1/2">
                  <div className="relative flex flex-col items-center">
                    {isActive && (
                      <span className="absolute top-1/2 size-8 -translate-y-1/2 rounded-full bg-clay/25 animate-pulse-ring" />
                    )}
                    <span
                      className={cn(
                        "relative grid size-8 place-items-center rounded-full border-2 font-display text-[12px] shadow-[0_8px_16px_-8px_rgba(0,0,0,0.6)] transition-all duration-300",
                        isActive
                          ? "scale-110 border-white bg-clay text-white"
                          : "border-white/90 text-white"
                      )}
                      style={isActive ? undefined : { backgroundColor: route.color }}
                    >
                      {index + 1}
                    </span>
                    <span
                      className={cn(
                        "mt-1 whitespace-nowrap rounded-full bg-background/90 px-2 py-0.5 text-[10px] text-foreground shadow-sm backdrop-blur transition-opacity",
                        isActive ? "opacity-100" : "opacity-0"
                      )}
                    >
                      {stop.name}
                    </span>
                  </div>
                </div>
              </MarkerContent>

              <MarkerPopup
                className="w-[248px] rounded-2xl border border-hairline bg-card p-4 text-card-foreground shadow-[var(--shadow-float)]"
                closeButton
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] tracking-[0.18em] text-muted-foreground">
                    第 {index + 1} 站 · {stop.kind}
                  </span>
                  <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                    {stop.stay}
                  </span>
                </div>
                <h4 className="mt-1.5 font-display text-[16px]">{stop.name}</h4>
                {index > 0 && index < route.stops.length - 1 && (
                  <StopThumb stop={stop} className="mt-2 h-24 w-full rounded-lg" />
                )}
                <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
                  {stop.desc}
                </p>
                <a
                  href={amapMarkerUrl(stop)}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-river px-3 py-1.5 text-[11px] text-primary-foreground transition hover:opacity-90"
                >
                  <Navigation className="size-3" strokeWidth={1.9} />
                  导航到这里
                </a>
              </MarkerPopup>
            </MapMarker>
          );
        })}

      <MapControls
        position="bottom-right"
        showZoom
        showLocate
        showScale
        showFullscreen={false}
      />
    </Map>
  );
}
