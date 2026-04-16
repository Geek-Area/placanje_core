import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";

export type TesterConfig = {
  backendUrl: string;
  supabaseUrl: string;
  supabasePublishableKey: string;
  bankWebhookSecret: string;
};

export function createSupabaseBrowserClient(
  config: TesterConfig,
): SupabaseClient | null {
  if (!config.supabaseUrl || !config.supabasePublishableKey) {
    return null;
  }

  return createClient(config.supabaseUrl, config.supabasePublishableKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });
}

export async function apiRequest<T>(
  backendUrl: string,
  path: string,
  options: {
    method?: string;
    token?: string | null;
    body?: unknown;
  } = {},
): Promise<T> {
  const url = new URL(path, backendUrl.endsWith("/") ? backendUrl : `${backendUrl}/`);
  const response = await fetch(url.toString(), {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  const text = await response.text();
  const parsed = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const message =
      parsed?.error?.message ??
      parsed?.message ??
      `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return parsed as T;
}

export async function signBankWebhookPayload(
  secret: string,
  payload: {
    provider: string;
    payment_ref: string;
    bank_transaction_ref: string;
    status: string;
    amount: string;
    completed_at: string;
  },
): Promise<string> {
  const ordered: Record<string, string> = {
    amount: payload.amount,
    bank_transaction_ref: payload.bank_transaction_ref,
    completed_at: payload.completed_at,
    payment_ref: payload.payment_ref,
    provider: payload.provider,
    status: payload.status,
  };
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(JSON.stringify(ordered)),
  );
  return Array.from(new Uint8Array(signature))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function getAccessToken(session: Session | null): string | null {
  return session?.access_token ?? null;
}
