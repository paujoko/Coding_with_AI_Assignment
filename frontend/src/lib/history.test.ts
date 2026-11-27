import type { Message } from "../api/types";
import { answersWithQuestions, behalfLabel, byWings, isDecision, typedByDeveloper } from "./history";

const at = "2026-11-25T10:00:00Z";
const m = (role: Message["role"], text: string, data: Message["data"] = {}, author = role === "agent" ? "Requirements" : role === "system" ? "wings" : "developer"): Message => ({
  phase: "requirements",
  role,
  text,
  author,
  data,
  created_at: at,
});

const asked = m("agent", "Q1. Terminal or browser?", {
  questions: [
    { id: "Q1", question: "Terminal or browser?", why: "", options: [] },
    { id: "Q2", question: "Save between runs?", why: "", options: [] },
  ],
});

test("decisions, words and Wings' entries are told apart", () => {
  const words = m("developer", "Keep it small");
  const choice = m("developer", "Run the tests", { decision: { action: "run" } });
  const behalf = m("system", "The requirements changed.", { on_behalf: { catch_up: true }, action: "revise" });
  expect([isDecision(words), isDecision(choice), isDecision(behalf)]).toEqual([false, true, false]);
  expect([byWings(words), byWings(choice), byWings(behalf)]).toEqual([false, false, true]);
  expect([typedByDeveloper(words), typedByDeveloper(choice), typedByDeveloper(behalf)]).toEqual([true, false, false]);
});

test("an old message without the new fields reads as typed by the developer", () => {
  expect(typedByDeveloper(m("developer", "Q1: CLI"))).toBe(true);
});

test("Wings says why it acted", () => {
  expect(behalfLabel({ change: 2 })).toBe("On your behalf, carrying change #2");
  expect(behalfLabel({ catch_up: true })).toBe("On your behalf, redoing this step");
  expect(behalfLabel({ catch_up: true, change: 1 })).toBe("On your behalf, carrying change #1");
});

test("answers are read next to the questions they answer", () => {
  const answer = m("developer", "Q1: Terminal\nQ2: Yes, in a file");
  expect(answersWithQuestions([asked, answer], 1)).toEqual([
    { id: "Q1", question: "Terminal or browser?", answer: "Terminal" },
    { id: "Q2", question: "Save between runs?", answer: "Yes, in a file" },
  ]);
});

test("words that are not all answers, or no questions before them, stay as they are", () => {
  expect(answersWithQuestions([asked, m("developer", "Q1: Terminal\nand make it fast")], 1)).toBeNull();
  expect(answersWithQuestions([m("developer", "Q1: Terminal")], 0)).toBeNull();
  expect(answersWithQuestions([asked, m("developer", "Q3: Blue")], 1)).toBeNull(); // no such question
});
