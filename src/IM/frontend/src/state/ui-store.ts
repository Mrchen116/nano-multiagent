import { create } from "zustand";

type Workspace = "chat" | "settings";

interface UiState {
  workspace: Workspace;
  setWorkspace: (workspace: Workspace) => void;
}

export const useUiStore = create<UiState>((set) => ({
  workspace: "chat",
  setWorkspace: (workspace) => set({ workspace })
}));
