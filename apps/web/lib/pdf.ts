import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import type { ApprovedPlan } from "@/lib/types";

/* ── Colour palette (HEMAS brand-esque) ── */
const BRAND_PRIMARY: [number, number, number] = [0, 63, 135]; // deep navy
const BRAND_SECONDARY: [number, number, number] = [0, 150, 136]; // teal accent
const BRAND_LIGHT: [number, number, number] = [235, 245, 255]; // header bg tint
const TEXT_DARK: [number, number, number] = [30, 30, 40];
const TEXT_SOFT: [number, number, number] = [100, 110, 130];
const BORDER_COLOR: [number, number, number] = [200, 210, 220];

function fmtDate(value: string | null | undefined): string {
  if (!value) return "N/A";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "N/A";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function drawHeaderStripe(doc: jsPDF) {
  const w = doc.internal.pageSize.getWidth();

  // Solid navy banner
  doc.setFillColor(...BRAND_PRIMARY);
  doc.rect(0, 0, w, 44, "F");

  // Teal accent stripe
  doc.setFillColor(...BRAND_SECONDARY);
  doc.rect(0, 44, w, 3, "F");
}

function drawPageHeader(doc: jsPDF, plan: ApprovedPlan) {
  const w = doc.internal.pageSize.getWidth();

  drawHeaderStripe(doc);

  // Company name
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.setTextColor(255, 255, 255);
  doc.text("HEMAS Pharmaceuticals", 14, 18);

  // Subtitle
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(200, 220, 240);
  doc.text("Pharmacy Distribution – Dispatch Plan Report", 14, 28);

  // Right-aligned plan version
  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.setTextColor(255, 255, 255);
  doc.text(`Plan Version #${plan.version_number}`, w - 14, 18, { align: "right" });

  // Right-aligned score
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(200, 220, 240);
  doc.text(`Optimization Score: ${plan.score ?? "—"}`, w - 14, 28, { align: "right" });

  // Light info band below the stripe
  doc.setFillColor(...BRAND_LIGHT);
  doc.rect(0, 47, w, 22, "F");

  doc.setFontSize(8);
  doc.setTextColor(...TEXT_SOFT);
  doc.setFont("helvetica", "normal");

  const now = new Date();
  const generatedStr = `Generated: ${now.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}`;
  const approvedStr = `Approved: ${fmtDateTime(plan.approved_at)}`;
  const approvedByStr = `Approved By: ${plan.approved_by ?? "Planner"}`;

  doc.text(generatedStr, 14, 56);
  doc.text(approvedStr, w / 3, 56);
  doc.text(approvedByStr, (2 * w) / 3, 56);

  doc.text(`Engine Run ID: ${plan.engine_run_id}`, 14, 63);
  doc.text(
    `Total Runs: ${plan.runs.length}  |  Total Stops: ${plan.stops.length}`,
    w / 3,
    63
  );

  // Divider
  doc.setDrawColor(...BORDER_COLOR);
  doc.setLineWidth(0.3);
  doc.line(14, 70, w - 14, 70);
}

function drawFooter(doc: jsPDF, pageNum: number) {
  const w = doc.internal.pageSize.getWidth();
  const h = doc.internal.pageSize.getHeight();

  doc.setDrawColor(...BORDER_COLOR);
  doc.setLineWidth(0.3);
  doc.line(14, h - 16, w - 14, h - 16);

  doc.setFontSize(7);
  doc.setTextColor(...TEXT_SOFT);
  doc.setFont("helvetica", "italic");
  doc.text(
    "HEMAS Pharmaceuticals – Confidential Dispatch Plan Report – Pharma Availability Control Tower",
    14,
    h - 10
  );

  doc.setFont("helvetica", "normal");
  doc.text(`Page ${pageNum}`, w - 14, h - 10, { align: "right" });
}

export function generateDispatchPlanPdf(plan: ApprovedPlan) {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const w = doc.internal.pageSize.getWidth();
  let pageNum = 1;

  /* ── Page 1: Header + Summary + Overview Table ── */
  drawPageHeader(doc, plan);
  drawFooter(doc, pageNum);

  let y = 78;

  // Section: Plan Summary
  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.setTextColor(...BRAND_PRIMARY);
  doc.text("Plan Summary", 14, y);
  y += 8;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(...TEXT_DARK);

  const totalItems = plan.stops.reduce((a, s) => a + s.items.length, 0);
  const totalQty = plan.stops.reduce(
    (a, s) => a + s.items.reduce((b, i) => b + i.quantity, 0),
    0
  );
  const uniqueDCs = new Set(plan.stops.map((s) => s.dc_code)).size;
  const uniqueLorries = new Set(plan.runs.map((r) => r.registration)).size;

  const summaryData = [
    ["Plan Version", `#${plan.version_number}`],
    ["Optimization Score", `${plan.score ?? "—"}`],
    ["Total Dispatch Runs", `${plan.runs.length}`],
    ["Total Stops", `${plan.stops.length}`],
    ["Total SKU Lines", `${totalItems}`],
    ["Total Units Dispatched", totalQty.toLocaleString()],
    ["Distribution Centres Covered", `${uniqueDCs}`],
    ["Fleet Vehicles Assigned", `${uniqueLorries}`],
    ["Approved At", fmtDateTime(plan.approved_at)],
    ["Approved By", plan.approved_by ?? "Planner"],
    ["Engine Run ID", `${plan.engine_run_id}`],
  ];

  autoTable(doc, {
    startY: y,
    head: [],
    body: summaryData,
    theme: "plain",
    styles: { fontSize: 9, cellPadding: { top: 2.5, bottom: 2.5, left: 4, right: 4 } },
    columnStyles: {
      0: { fontStyle: "bold", textColor: TEXT_SOFT, cellWidth: 60 },
      1: { textColor: TEXT_DARK },
    },
    alternateRowStyles: { fillColor: [248, 250, 252] },
    margin: { left: 14, right: 14 },
  });

  y = (doc as any).lastAutoTable.finalY + 10;

  // Section: Decisions / Approvals
  if (plan.decisions.length > 0) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(13);
    doc.setTextColor(...BRAND_PRIMARY);
    doc.text("Decision Trail", 14, y);
    y += 7;

    const decisionRows = plan.decisions.map((d) => [
      d.decision_type.toUpperCase(),
      d.decided_by,
      fmtDateTime(d.decided_at),
      d.notes ?? "—",
    ]);

    autoTable(doc, {
      startY: y,
      head: [["Decision", "Actor", "Timestamp", "Notes"]],
      body: decisionRows,
      headStyles: {
        fillColor: BRAND_PRIMARY,
        textColor: [255, 255, 255],
        fontStyle: "bold",
        fontSize: 8,
      },
      styles: { fontSize: 8, cellPadding: 3 },
      alternateRowStyles: { fillColor: [248, 250, 252] },
      margin: { left: 14, right: 14 },
    });

    y = (doc as any).lastAutoTable.finalY + 10;
  }

  /* ── DC-by-DC Dispatch Detail ── */

  // Group stops by DC
  type StopGroup = {
    dc_code: string;
    dc_name: string;
    stops: typeof plan.stops;
  };

  const dcMap = new Map<string, StopGroup>();
  for (const stop of plan.stops) {
    if (!dcMap.has(stop.dc_code)) {
      dcMap.set(stop.dc_code, { dc_code: stop.dc_code, dc_name: stop.dc_name, stops: [] });
    }
    dcMap.get(stop.dc_code)!.stops.push(stop);
  }

  const dcGroups = Array.from(dcMap.values()).sort((a, b) =>
    a.dc_code.localeCompare(b.dc_code)
  );

  for (const dc of dcGroups) {
    // Check if we need a new page
    if (y > 240) {
      doc.addPage();
      pageNum++;
      drawHeaderStripe(doc);
      drawFooter(doc, pageNum);
      y = 56;
    }

    // DC Title
    doc.setFillColor(...BRAND_SECONDARY);
    doc.roundedRect(14, y - 4, w - 28, 10, 1.5, 1.5, "F");
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.setTextColor(255, 255, 255);
    doc.text(`${dc.dc_name}  (${dc.dc_code})`, 18, y + 2.5);
    y += 12;

    // Build item rows for this DC
    const itemRows: string[][] = [];
    for (const stop of dc.stops) {
      for (const item of stop.items) {
        itemRows.push([
          stop.registration,
          stop.lorry_type,
          `Day ${stop.dispatch_day}`,
          `#${stop.stop_sequence}`,
          item.sku_code,
          item.sku_name,
          item.quantity.toLocaleString(),
        ]);
      }
    }

    autoTable(doc, {
      startY: y,
      head: [["Vehicle", "Type", "Dispatch", "Stop", "SKU Code", "SKU Name", "Qty"]],
      body: itemRows,
      headStyles: {
        fillColor: BRAND_PRIMARY,
        textColor: [255, 255, 255],
        fontStyle: "bold",
        fontSize: 7.5,
      },
      styles: { fontSize: 7.5, cellPadding: 2 },
      alternateRowStyles: { fillColor: [245, 248, 252] },
      margin: { left: 14, right: 14 },
      didDrawPage: () => {
        // On new pages, redraw chrome
        pageNum++;
        drawHeaderStripe(doc);
        drawFooter(doc, pageNum);
      },
    });

    y = (doc as any).lastAutoTable.finalY + 10;
  }

  /* ── Fleet Assignment Summary ── */
  if (y > 240) {
    doc.addPage();
    pageNum++;
    drawHeaderStripe(doc);
    drawFooter(doc, pageNum);
    y = 56;
  }

  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.setTextColor(...BRAND_PRIMARY);
  doc.text("Fleet Assignment Summary", 14, y);
  y += 7;

  const fleetRows = plan.runs.map((run) => [
    run.registration,
    run.lorry_type,
    `Day ${run.dispatch_day}`,
    `${run.stops.length}`,
    run.stops
      .reduce((a, s) => a + s.items.reduce((b, i) => b + i.quantity, 0), 0)
      .toLocaleString(),
  ]);

  autoTable(doc, {
    startY: y,
    head: [["Vehicle", "Type", "Dispatch Day", "Stops", "Total Qty"]],
    body: fleetRows,
    headStyles: {
      fillColor: BRAND_PRIMARY,
      textColor: [255, 255, 255],
      fontStyle: "bold",
      fontSize: 8,
    },
    styles: { fontSize: 8, cellPadding: 3 },
    alternateRowStyles: { fillColor: [248, 250, 252] },
    margin: { left: 14, right: 14 },
  });

  /* ── Save ── */
  const ts = new Date().toISOString().slice(0, 10);
  doc.save(`HEMAS_Dispatch_Plan_v${plan.version_number}_${ts}.pdf`);
}
