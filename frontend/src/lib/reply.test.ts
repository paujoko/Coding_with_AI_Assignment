import { foldReply, withoutLines } from "./reply";

test("a short reply is never folded", () => {
  const f = foldReply("Design drawn.\nThree diagrams saved.");
  expect(f.hiddenLines).toBe(0);
});

test("a long reply shows the first paragraph and folds the rest", () => {
  const f = foldReply("Tasks now have a priority.\n\nThe requirements changed in two places.\nThe design follows.\nAnd the tests.");
  expect(f.hiddenLines).toBe(3);
  expect(f.visible).toHaveLength(1);
  expect(f.all).toHaveLength(2);
});

test("a failure or an open question in a later paragraph is not folded away", () => {
  const f = foldReply("Tests written.\n\nThey cover every criterion in detail.\nSecond line.\n\n2 tests failed: delete and archive.");
  expect(f.visible.map((b) => (b.kind === "p" ? b.lines[0] : ""))).toEqual(["Tests written.", "2 tests failed: delete and archive."]);
  expect(f.hiddenLines).toBe(2);
});

test("a long list in the visible part is cut to three items", () => {
  const items = Array.from({ length: 11 }, (_, i) => `- Item${i}`).join("\n");
  const f = foldReply(items);
  const list = f.visible[0];
  expect(list.kind === "list" && list.items).toHaveLength(3);
  expect(f.hiddenLines).toBe(8);
});

test("lines shown elsewhere are taken out with the lead-in that introduced them", () => {
  const text = "Imported todo/models.py.\nDesign and code disagree (checked by code):\n- A is in the code.\n- B is in the code.";
  expect(withoutLines(text, ["A is in the code.", "B is in the code."])).toBe("Imported todo/models.py.");
  expect(withoutLines(text, [])).toBe(text);
});
