import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { AttachmentDropzone } from "./attachment-dropzone";

function makeFile(name: string, type: string): File {
  return new File([new Uint8Array(4)], name, { type });
}

function dataTransferOf(files: File[]): DataTransfer {
  const items: { kind: string; type: string; getAsFile: () => File }[] = files.map((f) => ({
    kind: "file",
    type: f.type,
    getAsFile: () => f
  }));
  return {
    files: files as unknown as FileList,
    items: items as unknown as DataTransferItemList,
    types: ["Files"]
  } as unknown as DataTransfer;
}

describe("AttachmentDropzone", () => {
  test("calls onAdd with dropped files", () => {
    const onAdd = vi.fn();
    render(
      <AttachmentDropzone onAdd={onAdd}>
        <span>child</span>
      </AttachmentDropzone>
    );
    const zone = screen.getByText("child").parentElement!;
    const file = makeFile("a.png", "image/png");
    fireEvent.dragOver(zone, { dataTransfer: dataTransferOf([file]) });
    fireEvent.drop(zone, { dataTransfer: dataTransferOf([file]) });
    expect(onAdd).toHaveBeenCalledWith([file]);
  });

  test("disables file drops without disabling independent child actions", () => {
    const onAdd = vi.fn();
    const retry = vi.fn();
    render(<AttachmentDropzone onAdd={onAdd} disabled><button onClick={retry}>Retry request</button></AttachmentDropzone>);
    const button = screen.getByRole('button', {name:'Retry request'});
    fireEvent.drop(button.parentElement!, {dataTransfer:dataTransferOf([makeFile('a.png','image/png')])});
    expect(onAdd).not.toHaveBeenCalled();
    expect(button.closest('[aria-disabled="true"]')).toBeNull();
    fireEvent.click(button);
    expect(retry).toHaveBeenCalledOnce();
  });
});
