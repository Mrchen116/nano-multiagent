import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { setLanguage } from "../../../i18n";
import type { PermissionRequest } from "../chat-types";
import { PermissionCard } from "./permission-card";

it("distinguishes an unconfirmed decision and accepts the later resolved event", async () => {
  await act(async () => setLanguage("en"));
  const request: PermissionRequest = {request_id: "p", tool_name: "bash", tool_input: {command: "pwd"}, question: "Allow?", status: "pending", options: [{id:"deny",label:"Deny",description:""}]};
  const onResolved = vi.fn();
  const fetchFn = vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:"decision_unconfirmed"}), {status:409}));
  const props = { request, onResolved, fetchFn, endpoint: "/im/v1/agents/a/work/permissions/p" };
  const view = render(<PermissionCard {...props} />);
  await userEvent.click(screen.getByRole("button", {name:"Deny"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("It may already have taken effect");
  expect(onResolved).not.toHaveBeenCalled();
  view.rerender(<PermissionCard {...props} request={{...request,status:"resolved"}} />);
  expect(screen.queryByRole("region")).not.toBeInTheDocument();
});

it("keeps a submitted decision locked until the Gateway confirms, including a refreshed card", async () => {
  await act(async () => setLanguage("en"));
  const request: PermissionRequest = {request_id:"shared",tool_name:"bash",tool_input:{command:"pwd"},question:"Allow?",status:"pending",options:[{id:"allow_once",label:"Allow once",description:""},{id:"deny",label:"Deny",description:""}]};
  const fetchFn = vi.fn().mockResolvedValue(new Response(JSON.stringify({status:"submitted",request_id:"shared",decision:"deny",decided_by:"other-member"})));
  const props = {request,fetchFn,onResolved:vi.fn(),conversationId:"group",messageId:"m"};
  const view = render(<PermissionCard {...props}/>);
  await userEvent.click(screen.getByRole("button",{name:"Allow once"}));
  expect(await screen.findByRole("status")).toHaveTextContent("Waiting for the device to confirm");
  expect(screen.getByRole("status")).toHaveTextContent("Deny");
  expect(screen.queryByRole("button",{name:"Allow once"})).toBeNull();
  view.unmount();
  const restored = render(<PermissionCard {...props} request={{...request,status:"submitted",decision:"deny",decided_by:"other-member"}}/>);
  expect(screen.getByRole("status")).toHaveTextContent("Waiting for the device to confirm");
  restored.rerender(<PermissionCard {...props} request={{...request,status:"resolved",decision:"deny"}}/>);
  expect(screen.queryByRole("status")).toBeNull();
});
