"use client";

import { AttackGraph as Graph } from "@/lib/api";
import * as d3 from "d3";
import { useEffect, useRef } from "react";

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  kind: string;
}
interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  relation: string;
  confidence: number;
}

const KIND_COLOR: Record<string, string> = {
  actor: "#FF3B5C",
  resource: "#00E5FF",
  node: "#7C8AA5",
};

export function AttackGraph({ graph }: { graph: Graph }) {
  const ref = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!ref.current || graph.nodes.length === 0) return;
    const width = ref.current.clientWidth;
    const height = 460;

    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();

    const nodes: SimNode[] = graph.nodes.map((n) => ({ ...n }));
    const links: SimLink[] = graph.edges.map((e) => ({
      source: e.from,
      target: e.to,
      relation: e.relation,
      confidence: e.confidence,
    }));

    const sim = d3
      .forceSimulation(nodes)
      .force("link", d3.forceLink<SimNode, SimLink>(links).id((d) => d.id).distance(120))
      .force("charge", d3.forceManyBody().strength(-280))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const link = svg
      .append("g")
      .attr("stroke", "#FF3B5C")
      .attr("stroke-opacity", 0.5)
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke-width", (d) => 1 + d.confidence * 2);

    const node = svg.append("g").selectAll("g").data(nodes).join("g");

    node
      .append("circle")
      .attr("r", 16)
      .attr("fill", (d) => KIND_COLOR[d.kind] ?? "#7C8AA5")
      .attr("stroke", "#0A0E1A")
      .attr("stroke-width", 2);

    node
      .append("text")
      .text((d) => d.label)
      .attr("x", 22)
      .attr("y", 5)
      .attr("fill", "#cbd5e1")
      .attr("font-size", "11px");

    sim.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x!)
        .attr("y1", (d) => (d.source as SimNode).y!)
        .attr("x2", (d) => (d.target as SimNode).x!)
        .attr("y2", (d) => (d.target as SimNode).y!);
      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => void sim.stop();
  }, [graph]);

  return (
    <div className="glass p-4">
      <h3 className="text-xs uppercase tracking-widest text-muted mb-3">Live Attack Graph</h3>
      <svg ref={ref} width="100%" height={460} />
    </div>
  );
}
