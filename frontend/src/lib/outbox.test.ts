import type { ActionInfo, Message } from "../api/types";
import { type Outgoing, outgoing, unsent, withoutSent } from "./outbox";

const revise: ActionInfo = { name: "revise", label: "Revise", description: "", message_field: "feedback", input_schema: { properties: { feedback: { type: "string" } }, required: ["feedback"] } };
const generate: ActionInfo = { name: "generate", label: "Write tests", description: "", message_field: "guidance", input_schema: { properties: { guidance: { type: "string" } } } };
const run: ActionInfo = { name: "run", label: "Run tests", description: "", message_field: null, input_schema: {} };

const said = (text: string, at = "2026-11-25T10:00:00Z"): Message => ({ phase: "design", role: "developer", text, author: "developer", data: {}, created_at: at });
const reply = (text: string): Message => ({ phase: "design", role: "agent", text, author: "Design", data: {}, created_at: "2026-11-25T10:00:01Z" });

const base = { id: 1, project: "p", phase: "design", now: "2026-11-25T10:00:00Z", seen: [] as Message[], documents: [] };

test("the bubble says what the backend will save: the action's message field", () => {
  const o = outgoing({ ...base, action: revise, input: { feedback: "Add a Board class" }, attachments: [] });
  expect(o?.message).toMatchObject({ role: "developer", text: "Add a Board class", phase: "design" });
  expect(o?.state).toBe("sending");
});

test("an action without words makes no bubble, unless documents go with it (then its label, as the backend)", () => {
  expect(outgoing({ ...base, action: run, input: {}, attachments: [] })).toBeNull();
  expect(outgoing({ ...base, action: generate, input: {}, attachments: [] })).toBeNull();
  const docs = [{ id: "d1", name: "brief.pdf", media_type: "application/pdf", size: 1, chars: 1, created_at: "" }];
  const o = outgoing({ ...base, action: generate, input: {}, attachments: ["d1"], documents: docs });
  expect(o?.message.text).toBe("Write tests");
  expect(o?.message.data.attachments).toEqual([{ id: "d1", name: "brief.pdf" }]);
});

test("the bubble disappears once the backend has saved the same words, never before", () => {
  const o = outgoing({ ...base, action: revise, input: { feedback: "Again" }, attachments: [], seen: [said("Again"), reply("Done")] }) as Outgoing;
  // The developer said the same words earlier: that old message does not count as this one.
  expect(unsent([said("Again"), reply("Done")], [o])).toEqual([o]);
  expect(unsent([said("Again"), reply("Done"), said("Again", "2026-11-25T10:05:00Z"), reply("Done again")], [o])).toEqual([]);
});

test("a decision line or Wings' words with the same text never stand for the sent bubble (ADR 0022)", () => {
  const o = outgoing({ ...base, action: revise, input: { feedback: "Run the tests" }, attachments: [] }) as Outgoing;
  const line: Message = { ...said("Run the tests"), data: { decision: { action: "run" } } };
  const wings: Message = { ...said("Run the tests"), role: "system", author: "wings", data: { on_behalf: { catch_up: true } } };
  expect(unsent([line, wings], [o])).toEqual([o]);
});

test("a failed message stays visible, whatever the saved messages say", () => {
  const o = { ...(outgoing({ ...base, action: revise, input: { feedback: "x" }, attachments: [] }) as Outgoing), state: "failed" as const };
  expect(unsent([said("x"), said("x")], [o])).toEqual([o]);
});

test("Try again takes the sent words out of the box, but keeps anything new", () => {
  expect(withoutSent({ "revise.feedback": "Add a Board class ", "discuss.question": "Why?" }, "revise", { feedback: "Add a Board class" })).toEqual({ "discuss.question": "Why?" });
  expect(withoutSent({ "revise.feedback": "Something else" }, "revise", { feedback: "Add a Board class" })).toEqual({ "revise.feedback": "Something else" });
});
