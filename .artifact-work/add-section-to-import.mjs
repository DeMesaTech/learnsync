import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/krisscelalmario/OneDrive/Desktop/learnsync/entrep_students_revised_sections.xlsx";
const outputDir = "C:/Users/krisscelalmario/OneDrive/Desktop/learnsync/outputs/student-section-import";
const outputPath = `${outputDir}/entrep_students_revised_sections.xlsx`;

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sectionByStudent = new Map();
const studentKey = (email, yearLevel) => `${String(email).trim().toLowerCase()}|${String(yearLevel).trim()}`;

for (const sheetName of ["Year 1", "Year 2", "Year 3", "Year 4"]) {
  const values = workbook.worksheets.getItem(sheetName).getUsedRange(true).values;
  let activeSection = null;

  for (const row of values) {
    const first = row[0];
    if (typeof first === "string" && /^SECTION\b/i.test(first.trim())) {
      const second = row[1];
      const fromSecondCell = typeof second === "string" ? second.trim() : "";
      const fromFirstCell = first.replace(/^SECTION\s*/i, "").replace(/\s*\(\d+\s+students\)\s*$/i, "").trim();
      activeSection = fromSecondCell || fromFirstCell;
      if (!activeSection) throw new Error(`Missing section value in ${sheetName}`);
      continue;
    }

    const email = row[7];
    if (activeSection && typeof first === "string" && typeof email === "string" && email.includes("@")) {
      const key = studentKey(email, row[6]);
      if (sectionByStudent.has(key)) throw new Error(`Duplicate student record ${key} in year tabs`);
      sectionByStudent.set(key, activeSection);
    }
  }
}

const importSheet = workbook.worksheets.getItem("Sheet1");
const importValues = importSheet.getUsedRange(true).values;
const missingStudents = [];
const sectionValues = [["section"]];
for (const row of importValues.slice(1)) {
  const key = studentKey(row[7], row[6]);
  const section = sectionByStudent.get(key);
  if (!section) missingStudents.push(key);
  sectionValues.push([section ?? null]);
}

if (missingStudents.length) throw new Error(`No section found for ${missingStudents.length} imported students: ${missingStudents.slice(0, 10).join(", ")}`);
if (sectionByStudent.size !== importValues.length - 1) throw new Error(`Section mapping has ${sectionByStudent.size} students; import has ${importValues.length - 1}`);

const rowCount = sectionValues.length;
importSheet.getRange(`H1:H${rowCount}`).copyTo(importSheet.getRange(`I1:I${rowCount}`), "all");
importSheet.getRange(`I1:I${rowCount}`).values = sectionValues;
importSheet.getRange("I1").format.columnWidth = 12;

const verifyRange = await workbook.inspect({
  kind: "table",
  range: "Sheet1!A1:I12",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 9,
});
console.log(verifyRange.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const preview = await workbook.render({ sheetName: "Sheet1", range: "A1:I25", scale: 1, format: "png" });
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(`${outputDir}/sheet1-preview.png`, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`Wrote ${outputPath} with ${sectionByStudent.size} student sections.`);
