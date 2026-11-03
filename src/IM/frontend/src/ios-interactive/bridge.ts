export type NativeRequest = Record<string, unknown> & {type: string};

declare global {
  interface Window {
    webkit: {messageHandlers: {intelligentUI: {postMessage(value: NativeRequest): Promise<unknown>}}};
    nanoSetStatus(value: {disabled: boolean}): void;
  }
}

/** Only native code owns authentication, persistence and conversation authority. */
export const nativeRequest = (request: NativeRequest) => window.webkit.messageHandlers.intelligentUI.postMessage(request);
