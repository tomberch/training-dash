import { createContext, useContext } from "react";
import type { User } from "../api";

interface UserContextValue {
  user: User;
  updateUser: (user: User) => void;
  decrementPendingSuggestions: (by?: number) => void;
}

export const UserContext = createContext<UserContextValue | null>(null);

export function useUser(): UserContextValue {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error("useUser must be used within a UserContext.Provider");
  }
  return context;
}

/**
 * Hook to get the user if available, without throwing.
 * Returns null when outside the UserContext (e.g., in tests or loading states).
 */
export function useUserOptional(): User | null {
  const context = useContext(UserContext);
  return context?.user ?? null;
}

/**
 * Hook to decrement pending suggestions count.
 * No-op when outside the UserContext.
 */
export function useDecrementPendingSuggestions(): (by?: number) => void {
  const context = useContext(UserContext);
  return context?.decrementPendingSuggestions ?? (() => {});
}
