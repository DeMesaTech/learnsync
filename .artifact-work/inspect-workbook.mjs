import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const input = await FileBlob.load("C:/Users/krisscelalmario/OneDrive/Desktop/learnsync/entrep_students_revised_sections.xlsx");
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItem("Sheet1");
console.log(await workbook.inspect({ kind: "computedStyle", sheetId: "Sheet1", range: "A1:I8", maxChars: 3000 }));
const rendered = await workbook.render({ sheetName: "Sheet1", range: "A1:I25", scale: 1, format: "png" });
await fs.writeFile("C:/Users/krisscelalmario/OneDrive/Desktop/learnsync/.artifact-work/sheet1-before.png", new Uint8Array(await rendered.arrayBuffer()));
