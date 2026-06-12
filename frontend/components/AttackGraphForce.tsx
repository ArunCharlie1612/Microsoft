"use client";

import * as d3 from "d3";
import React, { useEffect, useRef } from "react";

export type AttackNodeType = "resource" | "technique" | "finding";
export type AttackSeverity = "critical" | "high" | "medium" | "low";

export interface AttackGraphProps {
  nodes: Array<{
    id: string;
    label: string;
    type: AttackNodeType;
    severity?: AttackSeverity;
  }>;
  edges: Array<{ source: string; target: string; label?: string }>;
}

type GraphNode = AttackGraphProps["nodes"][number];
type GraphEdge = AttackGraphProps["edges"][number];

interface SimNode extends d3.SimulationNodeDatum, GraphNode {}
interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  label?: string;
}

const EDGE_COLOR = "#334155";
const TYPE_COLOR: Record<AttackNodeType, string> = {
  resource: "#0EA5E9",
  technique: "#8B5CF6",
  finding: "#FBBF24",
};
const SEVERITY_COLOR: Record<AttackSeverity, string> = {
  critical: "#EF4444",
  high: "#F59E0B",
  medium: "#FBBF24",
  low: "#10B981",
};

const MIN_HEIGHT = 420;
const LABEL_MAX = 18;

/** Resolve a node's fill colour: findings use severity, others use their type. */
function nodeColor(node: GraphNode): string {
  if (node.type === "finding") {
    return node.severity ? SEVERITY_COLOR[node.severity] : "#64748B";
  }
  return TYPE_COLOR[node.type];
}

/** Truncate a label to LABEL_MAX characters, appending an ellipsis when clipped. */
function truncate(label: string): string {
  return label.length > LABEL_MAX ? `${label.slice(0, LABEL_MAX - 1)}\u2026` : label;
}

const LEGEND: Array<{ swatch: string; label: string }> = [
  { swatch: TYPE_COLOR.resource, label: "Resource" },
  { swatch: TYPE_COLOR.technique, label: "Technique" },
  { swatch: SEVERITY_COLOR.critical, label: "Finding · Critical" },
  { swatch: SEVERITY_COLOR.high, label: "Finding · High" },
  { swatch: SEVERITY_COLOR.medium, label: "Finding · Medium" },
  { swatch: SEVERITY_COLOR.low, label: "Finding · Low" },
];

/**
 * Force-directed attack graph of BreachSim findings rendered with D3.
 *
 * Nodes are coloured by type (findings by severity), edges carry arrowheads,
 * and nodes are draggable. The SVG fills the parent width and re-draws cleanly
 * whenever `nodes` or `edges` change.
 */
export function AttackGraph({ nodes, edges }: AttackGraphProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const svgEl = svgRef.current;
    const wrapperEl = wrapperRef.current;
    const tooltipEl = tooltipRef.current;
    if (!svgEl || !wrapperEl || !tooltipEl) return;

    const width = wrapperEl.clientWidth || 640;
    const height = Math.max(MIN_HEIGHT, wrapperEl.clientHeight || MIN_HEIGHT);

    const svg = d3.select(svgEl);
    // Clean slate: drop any nodes/links/markers from a previous render.
    svg.selectAll("*").remove();

    if (nodes.length === 0) {
      return () => {
        svg.selectAll("*").remove();
      };
    }

    svg.attr("viewBox", `0 0 ${width} ${height}`);

    // Arrowhead marker shared by every edge.
    svg
      .append("defs")
      .append("marker")
      .attr("id", "attack-arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 22)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", EDGE_COLOR);

    const simNodes: SimNode[] = nodes.map((n) => ({ ...n }));
    const nodeIds = new Set(simNodes.map((n) => n.id));
    // Drop dangling edges so d3.forceLink does not throw on a missing endpoint.
    const simLinks: SimLink[] = edges
      .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, label: e.label }));

    const simulation = d3
      .forceSimulation(simNodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance(130),
      )
      .force("charge", d3.forceManyBody().strength(-320))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(38));

    const link = svg
      .append("g")
      .attr("stroke", EDGE_COLOR)
      .attr("stroke-width", 1.5)
      .selectAll("line")
      .data(simLinks)
      .join("line")
      .attr("marker-end", "url(#attack-arrow)");

    const node = svg
      .append("g")
      .selectAll<SVGGElement, SimNode>("g")
      .data(simNodes)
      .join("g")
      .attr("cursor", "grab");

    node
      .append("circle")
      .attr("r", 14)
      .attr("fill", (d) => nodeColor(d))
      .attr("stroke", "#0A0E1A")
      .attr("stroke-width", 2);

    node
      .append("text")
      .text((d) => truncate(d.label))
      .attr("text-anchor", "middle")
      .attr("y", 28)
      .attr("fill", "#cbd5e1")
      .attr("font-size", "11px")
      .attr("pointer-events", "none");

    // Tooltip with the full label + type, positioned relative to the wrapper.
    const tooltip = d3.select(tooltipEl);
    node
      .on("mouseover", (event: MouseEvent, d) => {
        const [x, y] = d3.pointer(event, wrapperEl);
        tooltip
          .style("opacity", "1")
          .style("left", `${x + 12}px`)
          .style("top", `${y + 12}px`)
          .html(
            `<div class="font-medium">${d.label}</div><div class="text-slate-400 capitalize">${d.type}${
              d.severity ? ` · ${d.severity}` : ""
            }</div>`,
          );
      })
      .on("mousemove", (event: MouseEvent) => {
        const [x, y] = d3.pointer(event, wrapperEl);
        tooltip.style("left", `${x + 12}px`).style("top", `${y + 12}px`);
      })
      .on("mouseout", () => {
        tooltip.style("opacity", "0");
      });

    const drag = d3
      .drag<SVGGElement, SimNode>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });
    node.call(drag);

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimNode).y ?? 0);
      node.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      simulation.stop();
      svg.selectAll("*").remove();
      tooltip.style("opacity", "0");
    };
  }, [nodes, edges]);

  return (
    <div ref={wrapperRef} className="relative w-full" style={{ minHeight: MIN_HEIGHT }}>
      <svg ref={svgRef} className="w-full" style={{ minHeight: MIN_HEIGHT }} role="img" />

      <div className="pointer-events-none absolute right-3 top-3 rounded-md border border-slate-700/60 bg-slate-900/80 p-2 text-[10px] text-slate-300 shadow-lg backdrop-blur">
        <div className="mb-1 font-semibold uppercase tracking-wider text-slate-400">Legend</div>
        <ul className="space-y-1">
          {LEGEND.map((item) => (
            <li key={item.label} className="flex items-center gap-2">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: item.swatch }}
              />
              <span>{item.label}</span>
            </li>
          ))}
        </ul>
      </div>

      <div
        ref={tooltipRef}
        className="pointer-events-none absolute z-10 rounded-md border border-slate-700/60 bg-slate-900/95 px-2 py-1 text-xs text-slate-100 shadow-lg transition-opacity"
        style={{ opacity: 0 }}
      />
    </div>
  );
}
