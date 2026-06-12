import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { AttackGraph } from "./AttackGraphForce";

const meta: Meta<typeof AttackGraph> = {
  title: "BreachSim/AttackGraph",
  component: AttackGraph,
  parameters: { layout: "fullscreen" },
  decorators: [
    (Story) => (
      <div className="bg-slate-950 p-6" style={{ width: "100%" }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;

type Story = StoryObj<typeof AttackGraph>;

/** A realistic 3-resource → 2-technique → 1-finding kill chain. */
export const KillChain: Story = {
  args: {
    nodes: [
      { id: "res-storage", label: "stbreachsimprod (Storage)", type: "resource" },
      { id: "res-keyvault", label: "kv-breachsim-prod (Key Vault)", type: "resource" },
      { id: "res-vm", label: "vm-jumpbox-01 (Virtual Machine)", type: "resource" },
      { id: "tech-public-blob", label: "Public Blob Exposure", type: "technique" },
      { id: "tech-cred-theft", label: "Credential Theft", type: "technique" },
      {
        id: "find-data-exfil",
        label: "Sensitive data exfiltration path",
        type: "finding",
        severity: "critical",
      },
    ],
    edges: [
      { source: "res-storage", target: "tech-public-blob", label: "anonymous access" },
      { source: "res-keyvault", target: "tech-cred-theft", label: "over-permissive policy" },
      { source: "res-vm", target: "tech-cred-theft", label: "managed identity" },
      { source: "tech-public-blob", target: "find-data-exfil", label: "enables" },
      { source: "tech-cred-theft", target: "find-data-exfil", label: "enables" },
    ],
  },
};

/** Mixed-severity findings to exercise the severity colour scale. */
export const MixedSeverity: Story = {
  args: {
    nodes: [
      { id: "res-sql", label: "sql-breachsim-prod", type: "resource" },
      { id: "tech-sqli", label: "SQL Injection", type: "technique" },
      { id: "find-crit", label: "Unauthenticated DB read", type: "finding", severity: "critical" },
      { id: "find-high", label: "Verbose error leakage", type: "finding", severity: "high" },
      { id: "find-med", label: "Missing TLS enforcement", type: "finding", severity: "medium" },
      { id: "find-low", label: "Outdated TLS cipher", type: "finding", severity: "low" },
    ],
    edges: [
      { source: "res-sql", target: "tech-sqli" },
      { source: "tech-sqli", target: "find-crit" },
      { source: "tech-sqli", target: "find-high" },
      { source: "res-sql", target: "find-med" },
      { source: "res-sql", target: "find-low" },
    ],
  },
};

/** Empty state — the component should render nothing in the canvas. */
export const Empty: Story = {
  args: { nodes: [], edges: [] },
};
