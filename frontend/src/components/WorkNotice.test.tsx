import { fireEvent, render, screen } from "@testing-library/react";
import { WorkNotice } from "./WorkNotice";

test("while an agent works elsewhere: which step, for how long, and the way back", () => {
  const went: number[] = [];
  const since = new Date(Date.now() - 151_000).toISOString();
  render(<WorkNotice title="Code" state="running" since={since} onShow={() => went.push(1)} />);
  const notice = screen.getByRole("status");
  expect(notice).toHaveTextContent("Code is being worked on");
  expect(screen.getByText(/^2:3[1-2]$/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Back to Code" }));
  expect(went).toEqual([1]);
});

test("when it is done Wings does not jump: the notice says it is ready", () => {
  const went: number[] = [];
  render(<WorkNotice title="Code" state="ready" since={null} onShow={() => went.push(1)} />);
  expect(screen.getByRole("status")).toHaveTextContent("Code is ready");
  expect(screen.queryByText(/being worked on/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Show it" }));
  expect(went).toEqual([1]);
});

test("a run that failed elsewhere says so", () => {
  render(<WorkNotice title="Tests" state="failed" since={null} onShow={() => {}} />);
  expect(screen.getByRole("status")).toHaveTextContent("Tests did not finish");
  expect(screen.getByRole("button", { name: "Show it" })).toBeInTheDocument();
});
