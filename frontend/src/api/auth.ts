/**
 * Auth API - login, register, logout
 */
import { apiPost, API_BASE, ApiError, extractError } from "./base";

export interface LoginResponse {
  user_id: number;
  email: string;
  is_admin: boolean;
  is_approved: boolean;
  display_name: string | null;
  avatar_path: string | null;
  unit_system: string;
  sync_hour: number;
}

export interface RegisterResponse {
  user_id: number;
  email: string;
  is_admin: boolean;
  is_approved: boolean;
}

export async function login(email: string, password: string): Promise<LoginResponse | null> {
  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function register(email: string, password: string): Promise<RegisterResponse> {
  const res = await fetch(`${API_BASE}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const { detail } = await extractError(res, "Registration failed");
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

export async function logout(): Promise<void> {
  return apiPost("/logout", undefined, "Logout failed");
}
