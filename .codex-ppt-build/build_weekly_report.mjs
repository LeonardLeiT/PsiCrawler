import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "D:\\Mywork\\PsiCrawler";
const SKILL_DIR = "C:\\Users\\lenovo\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.905.11957\\skills\\presentations";
const TMP_DIR = path.join(workspaceDir, ".codex-ppt-build");
const FINAL_PPTX = path.join(workspaceDir, "output", "PsiCrawler_项目周报_2026-09-18.pptx");
const RUNTIME_PYTHON = "C:\\Users\\lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";

const { finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);

const FONT = "Microsoft YaHei";
const C = {
  navy: "#102B36",
  navy2: "#173D49",
  teal: "#22A99A",
  mint: "#B9E6DB",
  paper: "#F4F7F6",
  white: "#FFFFFF",
  ink: "#173038",
  muted: "#587078",
  line: "#D5E2E0",
  amber: "#E8A33A",
};

function box(slide, x, y, w, h, fill, radius = "rect") {
  return slide.shapes.add({
    geometry: radius,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { fill: "none", width: 0 },
  });
}

function textBox(slide, text, x, y, w, h, size, color, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: FONT,
    fontSize: size,
    bold: options.bold ?? false,
    color,
    autoFit: "shrinkText",
    alignment: options.align ?? "left",
    verticalAlignment: options.vAlign ?? "top",
  };
  return shape;
}

async function addLogo(slide, filename, x, y, w, h, alt) {
  const ext = path.extname(filename).toLowerCase();
  const bytes = await fs.readFile(path.join(workspaceDir, "Figure", filename));
  slide.images.add({
    blob: bytes,
    contentType: ext === ".svg" ? "image/svg+xml" : "image/png",
    alt,
    fit: "contain",
    position: { left: x, top: y, width: w, height: h },
  });
}

await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });

const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const slide = presentation.slides.add();
slide.background.fill = C.paper;

// Left editorial band
box(slide, 0, 0, 414, 720, C.navy);
box(slide, 44, 42, 54, 6, C.teal);
textBox(slide, "WEEKLY REPORT", 44, 59, 240, 28, 14, C.mint, { bold: true });
textBox(slide, "PsiCrawler\n项目周报", 44, 99, 326, 118, 39, C.white, { bold: true });
textBox(slide, "公开科研数据的采集、标准化与可检索存储", 44, 228, 314, 52, 18, "#C8D8DA");

textBox(slide, "4", 44, 315, 98, 80, 56, C.white, { bold: true });
textBox(slide, "个 DFT 数据源已接入", 132, 338, 225, 34, 20, C.white, { bold: true });
box(slide, 44, 399, 300, 1, C.navy2);

textBox(slide, "115", 44, 420, 118, 66, 42, C.teal, { bold: true });
textBox(slide, "统一字段", 156, 435, 180, 30, 18, C.white, { bold: true });
textBox(slide, "Schema 3.0 统一跨源数据语义", 44, 486, 300, 40, 16, "#C8D8DA");

textBox(slide, "本周形成完整链路", 44, 570, 280, 28, 17, C.mint, { bold: true });
textBox(slide, "下载与分页采集  /  字段映射与结构标准化\nCIF 与原始文件存储  /  SQLite 索引与文档示例", 44, 607, 320, 64, 15, "#DCE8E9");
textBox(slide, "2026.09.09—09.18", 44, 681, 220, 22, 12, "#91AEB3");

// Right content area
textBox(slide, "本周完成：多源 DFT 数据管线从零落地", 458, 44, 760, 50, 30, C.ink, { bold: true });
textBox(slide, "采集端保留各数据源差异，标准层统一字段、结构与溯源信息", 458, 94, 720, 30, 17, C.muted);
box(slide, 458, 130, 760, 2, C.line);

const rows = [
  {
    logo: "mp_logo.png", alt: "Materials Project logo", y: 151,
    name: "Materials Project", tag: "26 个材料接口",
    body: "Schema 驱动采集，支持单条与批量任务、完整 Summary 字段、CIF 导出和 SQLite 索引。",
  },
  {
    logo: "aflow_logo.png", alt: "AFLOW logo", y: 248,
    name: "AFLOW", tag: "分类原始数据",
    body: "完成标准记录映射与性质路径留存；XZ 文件下载后自动解压，成功转换后清理压缩包。",
  },
  {
    logo: "alexandria_logo.png", alt: "Alexandria logo", y: 345,
    name: "Alexandria", tag: "流式批量采集",
    body: "支持 JSON.bz2 流式处理、OPTIMADE 按需查询、数据集命名空间标识符和 SQLite 索引。",
  },
  {
    logo: "materialscloud_logo.svg", alt: "Materials Cloud logo", y: 442,
    name: "Materials Cloud", tag: "约 10.5 万条记录",
    body: "接入 MC3D 与 MC2D 共 4 个数据集，支持 OPTIMADE 分页、精选归档批量下载和标准化记录。",
  },
];

for (const row of rows) {
  await addLogo(slide, row.logo, 458, row.y + 7, 72, 52, row.alt);
  textBox(slide, row.name, 552, row.y, 270, 32, 19, C.ink, { bold: true });
  textBox(slide, row.tag, 916, row.y + 3, 270, 28, 15, C.teal, { bold: true, align: "right" });
  textBox(slide, row.body, 552, row.y + 35, 634, 48, 15, C.muted);
  if (row.y < 442) box(slide, 552, row.y + 91, 634, 1, C.line);
}

// Bottom priorities strip
box(slide, 438, 558, 842, 162, C.white);
box(slide, 438, 558, 9, 162, C.teal);
textBox(slide, "下周重点", 474, 580, 138, 28, 17, C.teal, { bold: true });
textBox(slide, "扩大代表性样本回归测试，核对跨源字段质量；推进 OQMD 适配器与断点恢复测试。", 474, 615, 698, 48, 18, C.ink, { bold: true });
textBox(slide, "风险提示：上游 API 速率限制与超大归档会影响全量同步，批量任务需保留限速、续传与许可记录。", 474, 674, 720, 24, 13, C.muted);

slide.speakerNotes.textFrame.setText(
  "内容依据本地仓库 README_zh.md、document/dft/overview.md、document/dft/materialscloud.md、normalizers/dft/standard.yaml 及当前工作区模块整理。统计日期：2026-09-18。Materials Cloud 约 10.5 万条为文档中四个数据集记录数之和的近似值。语法检查：core、crawler、sources、normalizers、tests compileall 通过。",
);

const candidatePath = path.join(TMP_DIR, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const preview = await presentation.export({ slide, format: "png", scale: 1.5 });
await fs.writeFile(path.join(TMP_DIR, "weekly-report-preview.png"), new Uint8Array(await preview.arrayBuffer()));
const layout = await slide.export({ format: "layout" });
await fs.writeFile(path.join(TMP_DIR, "weekly-report.layout.json"), await layout.text());

const requirements = {
  explicitTotalSlideCount: 1,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
};
const fontPolicy = {
  basis: "design",
  families: [FONT],
};
const stagingDir = path.join(workspaceDir, ".codex-finalizer");
await fs.mkdir(stagingDir, { recursive: true });
const finalCandidatePath = path.join(stagingDir, "candidate-weekly-report.pptx");
await fs.copyFile(candidatePath, finalCandidatePath);

const result = await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath: finalCandidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  fontPolicy,
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "PsiCrawler_项目周报_2026-09-18.validation.json"),
});

console.log(JSON.stringify({ final: FINAL_PPTX, preview: path.join(TMP_DIR, "weekly-report-preview.png"), result }, null, 2));
