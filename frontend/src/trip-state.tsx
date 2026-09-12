import { createContext, type Dispatch, type PropsWithChildren, useContext, useEffect, useReducer } from "react";
import { api } from "./api";
import type { Trip } from "./contracts";

type TripState = { draft: Trip | null; draftId: string | null; selectedIds: string[]; activePlanId: string | null };
type TripAction =
  | { type: "set-draft"; draft: Trip }
  | { type: "set-draft-id"; draftId: string | null }
  | { type: "set-selection"; selectedIds: string[] }
  | { type: "set-active-plan"; planId: string | null }
  | { type: "clear" };

const initialState: TripState = { draft: null, draftId: null, selectedIds: [], activePlanId: null };
const TripStateContext = createContext<TripState>(initialState);
const TripDispatchContext = createContext<Dispatch<TripAction> | null>(null);

function reducer(state: TripState, action: TripAction): TripState {
  switch (action.type) {
    case "set-draft": return { ...state, draft: action.draft, draftId: action.draft.id, activePlanId: null };
    case "set-draft-id": return { ...state, draftId: action.draftId };
    case "set-selection": return { ...state, selectedIds: action.selectedIds };
    case "set-active-plan": return { ...state, activePlanId: action.planId };
    case "clear": return initialState;
  }
}

export function TripStateProvider({ children }: PropsWithChildren) {
  const [state, dispatch] = useReducer(reducer, initialState);
  useEffect(() => {
    const draftId = localStorage.getItem("packright-active-trip");
    if (!draftId) return;
    dispatch({ type: "set-draft-id", draftId });
    void api.getTrip(draftId).then(next => dispatch({ type: "set-draft", draft: next.trip })).catch(() => localStorage.removeItem("packright-active-trip"));
  }, []);
  useEffect(() => { if (state.draftId) localStorage.setItem("packright-active-trip", state.draftId); }, [state.draftId]);
  return (
    <TripStateContext.Provider value={state}>
      <TripDispatchContext.Provider value={dispatch}>{children}</TripDispatchContext.Provider>
    </TripStateContext.Provider>
  );
}

export const useTripState = () => useContext(TripStateContext);
export function useTripDispatch() {
  const dispatch = useContext(TripDispatchContext);
  if (!dispatch) throw new Error("useTripDispatch must be used within TripStateProvider");
  return dispatch;
}
