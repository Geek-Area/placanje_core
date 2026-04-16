import { useEffect, useState } from "react";
import type { Session, SupabaseClient } from "@supabase/supabase-js";

import {
  apiRequest,
  createSupabaseBrowserClient,
  getAccessToken,
  signBankWebhookPayload,
  type TesterConfig,
} from "./api";
import {
  endpointDocs,
  endpointGroups,
  flowCards,
  frontendChecklist,
  implementationLayers,
  productTracks,
  statusLifecycles,
  transactionFieldGlossary,
  type DocEndpointGroup,
  type EndpointDoc,
} from "./content";

type ActiveTab = "documentation" | "testing";

type LogEntry = {
  id: string;
  title: string;
  data: unknown;
  createdAt: string;
};

type MerchantAccount = {
  id: string;
  parent_account_id: string | null;
  account_type: string;
  slug: string;
  display_name: string;
  payee_name: string | null;
  payee_account_number: string | null;
  payee_address: string | null;
  payee_city: string | null;
  active: boolean;
  effective_role: string | null;
};

const defaultConfig: TesterConfig = {
  backendUrl: "http://127.0.0.1:8000",
  supabaseUrl: "",
  supabasePublishableKey: "",
  bankWebhookSecret: "change-me",
};

function usePersistentState<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : initialValue;
  });

  useEffect(() => {
    window.localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);

  return [value, setValue] as const;
}

function JsonBlock({ value }: { value: unknown | null }) {
  if (value === null) {
    return <pre className="code-block">No JSON body</pre>;
  }

  return <pre className="code-block">{JSON.stringify(value, null, 2)}</pre>;
}

function StatusPill({
  children,
  tone = "neutral",
}: {
  children: string;
  tone?: "neutral" | "accent" | "warm";
}) {
  return <span className={`status-pill status-pill-${tone}`}>{children}</span>;
}

function EndpointCard({
  endpoint,
  onOpenTest,
}: {
  endpoint: EndpointDoc;
  onOpenTest: (sectionId: string) => void;
}) {
  return (
    <article className="endpoint-card">
      <div className="endpoint-card-head">
        <div>
          <div className="endpoint-meta">
            <StatusPill tone={endpoint.method === "POST" ? "accent" : "warm"}>
              {endpoint.method}
            </StatusPill>
            <StatusPill>{endpoint.auth}</StatusPill>
          </div>
          <h3>{endpoint.title}</h3>
          <code className="endpoint-path">{endpoint.path}</code>
        </div>
        {endpoint.testSectionId ? (
          <button
            type="button"
            className="ghost-button"
            onClick={() => onOpenTest(endpoint.testSectionId!)}
          >
            Open in Testing
          </button>
        ) : null}
      </div>
      <p className="section-copy">{endpoint.description}</p>
      <div className="endpoint-grid">
        <div>
          <p className="code-label">Request</p>
          <JsonBlock value={endpoint.requestExample} />
        </div>
        <div>
          <p className="code-label">Response</p>
          <JsonBlock value={endpoint.responseExample} />
        </div>
      </div>
      <ul className="note-list">
        {endpoint.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </article>
  );
}

function App() {
  const [config, setConfig] = usePersistentState<TesterConfig>(
    "placanje-core-tester-config",
    defaultConfig,
  );
  const [activeTab, setActiveTab] = usePersistentState<ActiveTab>(
    "placanje-core-workbench-tab",
    "documentation",
  );
  const [activeEndpointGroup, setActiveEndpointGroup] =
    useState<DocEndpointGroup>("merchant");
  const [supabaseClient, setSupabaseClient] = useState<SupabaseClient | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [merchantAccounts, setMerchantAccounts] = useState<MerchantAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = usePersistentState<string>(
    "placanje-core-tester-selected-account-id",
    "",
  );
  const [lastInviteToken, setLastInviteToken] = useState("");
  const [lastPaymentRef, setLastPaymentRef] = useState("");
  const [lastShareSlug, setLastShareSlug] = useState("");
  const [lastSubscriptionId, setLastSubscriptionId] = useState("");

  const [authForm, setAuthForm] = useState({
    email: "",
    password: "",
  });
  const [merchantSignupForm, setMerchantSignupForm] = useState({
    display_name: "",
    payee_account_number: "",
    payee_name: "",
    payee_address: "",
    payee_city: "",
  });
  const [subAccountForm, setSubAccountForm] = useState({
    display_name: "",
    payee_name: "",
    payee_account_number: "",
    payee_address: "",
    payee_city: "",
  });
  const [inviteForm, setInviteForm] = useState({
    email: "",
    role: "operator",
  });
  const [acceptInviteForm, setAcceptInviteForm] = useState({
    token: "",
  });
  const [posTransactionForm, setPosTransactionForm] = useState({
    amount: "450.00",
    payment_description: "Test payment",
    reference_model: "97",
    reference_number: "12345",
  });
  const [webhookForm, setWebhookForm] = useState({
    provider: "demo-bank",
    payment_ref: "",
    bank_transaction_ref: "BANK-DEMO-001",
    status: "completed",
    amount: "450.00",
    completed_at: new Date().toISOString(),
  });
  const [publicTransactionForm, setPublicTransactionForm] = useState({
    payee_name: "",
    payee_address: "",
    payee_city: "",
    payee_account_number: "",
    amount: "1500.00",
    payment_code: "289",
    reference_model: "97",
    reference_number: "12345",
    payment_description: "Public test",
  });
  const [shareLookupForm, setShareLookupForm] = useState({
    slug: "",
  });
  const [subscriptionForm, setSubscriptionForm] = useState({
    subscriber_email: "",
    subscriber_name: "",
    amount: "3000.00",
    currency: "RSD",
    payment_code: "289",
    reference_model: "97",
    reference_number: "20260501",
    payment_description: "Optional subscription test",
    cadence: "monthly",
    first_run_at: new Date().toISOString(),
  });

  const token = getAccessToken(session);
  const selectedAccount =
    merchantAccounts.find((account) => account.id === selectedAccountId) ?? null;
  const filteredEndpoints = endpointDocs.filter(
    (endpoint) => endpoint.group === activeEndpointGroup,
  );
  const endpointGroupSummary: Record<DocEndpointGroup, string> = {
    public:
      "Use these for Plaćanje.RS public pay-slip creation and shared read-only pay-slip pages.",
    consumer:
      "Use these when a signed-in consumer creates or lists their own Pay slips.",
    merchant:
      "Use these for Instant.Plaćanje.RS merchant onboarding, POS hierarchy, POS creation, and account reporting.",
    webhook:
      "Use this only for bank-side or internal callback handling. It is not a browser-facing endpoint.",
  };
  const documentationMetrics = [
    { label: "Core frontend flows", value: "3" },
    { label: "Core endpoint groups", value: `${endpointGroups.length}` },
    { label: "Primary payment record states", value: "draft / awaiting / completed" },
  ];

  useEffect(() => {
    const client = createSupabaseBrowserClient(config);
    setSupabaseClient(client);
    if (!client) {
      setSession(null);
      return;
    }

    void client.auth.getSession().then(({ data }) => {
      setSession(data.session);
    });

    const { data } = client.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });

    return () => {
      data.subscription.unsubscribe();
    };
  }, [config]);

  useEffect(() => {
    if (!token) {
      setMerchantAccounts([]);
      setSelectedAccountId("");
      return;
    }

    let cancelled = false;

    async function loadMerchantAccounts() {
      try {
        const response = await apiRequest<{ items: MerchantAccount[] }>(
          config.backendUrl,
          "/v1/merchant/accounts",
          { token },
        );
        if (cancelled) {
          return;
        }
        setMerchantAccounts(response.items);
        setSelectedAccountId((current) =>
          response.items.some((account) => account.id === current)
            ? current
            : (response.items[0]?.id ?? ""),
        );
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : String(error);
        setLogs((current) => [
          {
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            title: "List merchant accounts failed",
            data: { message },
            createdAt: new Date().toISOString(),
          },
          ...current,
        ]);
      }
    }

    void loadMerchantAccounts();

    return () => {
      cancelled = true;
    };
  }, [config.backendUrl, token, setSelectedAccountId]);

  function updateConfig(field: keyof TesterConfig, value: string) {
    setConfig((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function pushLog(title: string, data: unknown) {
    setLogs((current) => [
      {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        title,
        data,
        createdAt: new Date().toISOString(),
      },
      ...current,
    ]);
  }

  async function runAction<T>(label: string, action: () => Promise<T>) {
    try {
      setBusy(label);
      const result = await action();
      pushLog(label, result);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      pushLog(`${label} failed`, { message });
      throw error;
    } finally {
      setBusy(null);
    }
  }

  function jumpToTesting(sectionId: string) {
    setActiveTab("testing");
    window.setTimeout(() => {
      document.getElementById(sectionId)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 120);
  }

  function jumpToDocs(sectionId: string) {
    setActiveTab("documentation");
    window.setTimeout(() => {
      document.getElementById(sectionId)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 120);
  }

  function openEndpointGroup(group: DocEndpointGroup) {
    setActiveEndpointGroup(group);
    jumpToDocs("docs-reference");
  }

  async function refreshMerchantAccounts() {
    if (!token) {
      return;
    }

    const response = await runAction("List merchant accounts", () =>
      apiRequest<{ items: MerchantAccount[] }>(config.backendUrl, "/v1/merchant/accounts", {
        token,
      }),
    );

    setMerchantAccounts(response.items);
    setSelectedAccountId((current) =>
      response.items.some((account) => account.id === current)
        ? current
        : (response.items[0]?.id ?? ""),
    );
  }

  async function handleSignUp() {
    if (!supabaseClient) {
      return;
    }
    await runAction("Supabase sign up", () =>
      supabaseClient.auth.signUp({
        email: authForm.email,
        password: authForm.password,
      }),
    );
  }

  async function handleSignIn() {
    if (!supabaseClient) {
      return;
    }
    await runAction("Supabase sign in", () =>
      supabaseClient.auth.signInWithPassword({
        email: authForm.email,
        password: authForm.password,
      }),
    );
  }

  async function handleSignOut() {
    if (!supabaseClient) {
      return;
    }
    await runAction("Supabase sign out", () => supabaseClient.auth.signOut());
    setMerchantAccounts([]);
    setSelectedAccountId("");
  }

  async function handleMerchantSignup() {
    const response = await runAction("Merchant signup", () =>
      apiRequest<MerchantAccount>(config.backendUrl, "/v1/merchant/signup", {
        method: "POST",
        token,
        body: merchantSignupForm,
      }),
    );
    setSelectedAccountId(response.id);
    await refreshMerchantAccounts();
  }

  async function handleCreateSubAccount() {
    const response = await runAction("Create POS sub-account", () =>
      apiRequest<MerchantAccount>(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/sub-accounts`,
        {
          method: "POST",
          token,
          body: {
            ...subAccountForm,
            payee_account_number: subAccountForm.payee_account_number || null,
          },
        },
      ),
    );
    setSelectedAccountId(response.id);
    await refreshMerchantAccounts();
  }

  async function handleInviteCashier() {
    const response = await runAction("Invite cashier", () =>
      apiRequest<{ token?: string }>(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/invites`,
        {
          method: "POST",
          token,
          body: inviteForm,
        },
      ),
    );
    if (response.token) {
      setLastInviteToken(response.token);
      setAcceptInviteForm({ token: response.token });
    }
  }

  async function handleAcceptInvite() {
    await runAction("Accept merchant invite", () =>
      apiRequest(config.backendUrl, "/v1/merchant/invites/accept", {
        method: "POST",
        token,
        body: acceptInviteForm,
      }),
    );
    await refreshMerchantAccounts();
  }

  async function handleCreatePosTransaction() {
    const response = await runAction<{
      payment_ref: string;
      status: string;
      qr_string: string;
      transaction_id: string;
    }>("Create POS transaction", () =>
      apiRequest(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/transactions`,
        {
          method: "POST",
          token,
          body: posTransactionForm,
        },
      ),
    );
    setLastPaymentRef(response.payment_ref);
    setWebhookForm((current) => ({
      ...current,
      payment_ref: response.payment_ref,
      amount: posTransactionForm.amount,
    }));
  }

  async function handleMerchantTransactions() {
    await runAction("List account transactions", () =>
      apiRequest(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/transactions`,
        {
          token,
        },
      ),
    );
  }

  async function handleMerchantStats() {
    await runAction("Get account stats", () =>
      apiRequest(config.backendUrl, `/v1/merchant/accounts/${selectedAccountId}/stats`, {
        token,
      }),
    );
  }

  async function handleWebhook() {
    const signature = await signBankWebhookPayload(config.bankWebhookSecret, {
      provider: webhookForm.provider,
      payment_ref: webhookForm.payment_ref,
      bank_transaction_ref: webhookForm.bank_transaction_ref,
      status: webhookForm.status,
      amount: webhookForm.amount,
      completed_at: webhookForm.completed_at,
    });

    await runAction("Send signed fake bank webhook", async () => {
      const url = new URL(
        `/v1/webhooks/bank/${webhookForm.provider}/ips-status`,
        config.backendUrl.endsWith("/") ? config.backendUrl : `${config.backendUrl}/`,
      );
      const response = await fetch(url.toString(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Signature": signature,
        },
        body: JSON.stringify({
          payment_ref: webhookForm.payment_ref,
          bank_transaction_ref: webhookForm.bank_transaction_ref,
          status: webhookForm.status,
          amount: webhookForm.amount,
          completed_at: webhookForm.completed_at,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error?.message ?? "Webhook call failed");
      }
      return data;
    });
  }

  async function handlePublicTransaction() {
    const response = await runAction<{ share_slug: string }>("Create public pay slip", () =>
      apiRequest(config.backendUrl, "/v1/public/transactions", {
        method: "POST",
        body: publicTransactionForm,
      }),
    );
    setLastShareSlug(response.share_slug);
    setShareLookupForm({ slug: response.share_slug });
  }

  async function handlePublicShareLookup() {
    await runAction("Get public share", () =>
      apiRequest(config.backendUrl, `/v1/public/share/${shareLookupForm.slug}`),
    );
  }

  async function handleConsumerProfile() {
    await runAction("Get consumer profile", () =>
      apiRequest(config.backendUrl, "/v1/me", {
        token,
      }),
    );
  }

  async function handleConsumerTransaction() {
    const response = await runAction<{ share_slug: string }>(
      "Create consumer pay slip",
      () =>
        apiRequest(config.backendUrl, "/v1/me/transactions", {
          method: "POST",
          token,
          body: {
            ...publicTransactionForm,
            payer_name: session?.user.email ?? null,
          },
        }),
    );
    setLastShareSlug(response.share_slug);
    setShareLookupForm({ slug: response.share_slug });
  }

  async function handleConsumerTransactions() {
    await runAction("List my transactions", () =>
      apiRequest(config.backendUrl, "/v1/me/transactions", { token }),
    );
  }

  async function handleConsumerSubscriptions() {
    await runAction("List my subscriptions", () =>
      apiRequest(config.backendUrl, "/v1/me/subscriptions", { token }),
    );
  }

  async function handleCreateSubscription() {
    const response = await runAction<{ id: string }>("Create subscription", () =>
      apiRequest(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/subscriptions`,
        {
          method: "POST",
          token,
          body: subscriptionForm,
        },
      ),
    );
    setLastSubscriptionId(response.id);
  }

  async function handlePauseSubscription() {
    await runAction("Pause subscription", () =>
      apiRequest(
        config.backendUrl,
        `/v1/merchant/subscriptions/${lastSubscriptionId}/pause`,
        {
          method: "POST",
          token,
        },
      ),
    );
  }

  async function handleResumeSubscription() {
    await runAction("Resume subscription", () =>
      apiRequest(
        config.backendUrl,
        `/v1/merchant/subscriptions/${lastSubscriptionId}/resume`,
        {
          method: "POST",
          token,
        },
      ),
    );
  }

  async function handleRunDueSubscriptions() {
    await runAction("Run due subscriptions job", () =>
      apiRequest(config.backendUrl, "/v1/dev/jobs/run-due-subscriptions", {
        method: "POST",
        body: { limit: 100 },
      }),
    );
  }

  async function handleExpirePosTransactions() {
    await runAction("Expire POS transactions job", () =>
      apiRequest(config.backendUrl, "/v1/dev/jobs/expire-pos-transactions", {
        method: "POST",
        body: { minutes: 30 },
      }),
    );
  }

  return (
    <div className="app-shell">
      <div className="ambient-layer" aria-hidden="true" />
      <div className="page">
        <header className="masthead">
          <div className="masthead-copy">
            <p className="eyebrow">Placanje Core Workbench</p>
            <h1>Implementation documentation and live backend testing in one surface.</h1>
            <p className="hero-copy">
              This workbench is built for the two MVP products that matter now: public pay
              slips and merchant IPS POS payments. Documentation explains the contract;
              testing exercises the real backend without writing raw fetch calls by hand.
            </p>
          </div>
          <div className="hero-meta">
            <div className="metric-card">
              <span className="metric-label">Session</span>
              <strong>{session?.user.email ?? "Not signed in"}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">Selected account</span>
              <strong>{selectedAccount?.display_name ?? "None"}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">Busy</span>
              <strong>{busy ?? "Idle"}</strong>
            </div>
          </div>
        </header>

        <nav className="tab-bar" aria-label="Workbench sections">
          <button
            type="button"
            className={`tab-button ${activeTab === "documentation" ? "active" : ""}`}
            onClick={() => setActiveTab("documentation")}
          >
            Documentation
          </button>
          <button
            type="button"
            className={`tab-button ${activeTab === "testing" ? "active" : ""}`}
            onClick={() => setActiveTab("testing")}
          >
            Testing
          </button>
        </nav>

        {activeTab === "documentation" ? (
          <div className="docs-layout">
            <aside className="side-rail">
              <div className="rail-card">
                <p className="rail-title">Jump to</p>
                <button type="button" className="rail-link" onClick={() => jumpToDocs("docs-overview")}>
                  Overview
                </button>
                <button type="button" className="rail-link" onClick={() => jumpToDocs("docs-contract")}>
                  Frontend contract
                </button>
                <button type="button" className="rail-link" onClick={() => jumpToDocs("docs-flows")}>
                  Frontend flows
                </button>
                <button type="button" className="rail-link" onClick={() => jumpToDocs("docs-reference")}>
                  Endpoint reference
                </button>
                <button type="button" className="rail-link" onClick={() => jumpToDocs("docs-records")}>
                  Payment record model
                </button>
              </div>
              <div className="rail-card">
                <p className="rail-title">Implementation checklist</p>
                <ul className="note-list compact">
                  {frontendChecklist.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div className="rail-card accent-card">
                <p className="rail-title">Quick handoff note</p>
                <p className="section-copy">
                  Internal enum values stay as they are. In product language and frontend
                  copy, treat <code>regular</code> as <strong>Pay slips</strong>.
                </p>
                <button type="button" className="ghost-button" onClick={() => setActiveTab("testing")}>
                  Switch to Testing
                </button>
              </div>
            </aside>

            <div className="content-stack">
              <section id="docs-overview" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Overview</p>
                  <h2>What this backend already covers</h2>
                </div>
                <div className="metrics-grid">
                  {documentationMetrics.map((metric) => (
                    <div key={metric.label} className="metric-card large">
                      <span className="metric-label">{metric.label}</span>
                      <strong
                        className={`metric-value ${
                          metric.value.length > 18 ? "metric-value-long" : ""
                        }`}
                      >
                        {metric.value}
                      </strong>
                    </div>
                  ))}
                </div>
                <div className="story-grid">
                  {productTracks.map((track) => (
                    <article
                      key={track.title}
                      className={`story-card product-card ${
                        track.defaultEndpointGroup ? "is-clickable" : ""
                      }`}
                      role={track.defaultEndpointGroup ? "button" : undefined}
                      tabIndex={track.defaultEndpointGroup ? 0 : undefined}
                      onClick={() =>
                        track.defaultEndpointGroup
                          ? openEndpointGroup(track.defaultEndpointGroup)
                          : jumpToDocs("docs-records")
                      }
                      onKeyDown={(event) => {
                        if (
                          !track.defaultEndpointGroup &&
                          !track.actions?.some((action) => action.sectionId === "docs-records")
                        ) {
                          return;
                        }
                        if (event.key !== "Enter" && event.key !== " ") {
                          return;
                        }
                        event.preventDefault();
                        if (track.defaultEndpointGroup) {
                          openEndpointGroup(track.defaultEndpointGroup);
                          return;
                        }
                        jumpToDocs("docs-records");
                      }}
                    >
                      <p className="eyebrow soft">{track.eyebrow}</p>
                      <h3>{track.title}</h3>
                      <p className="section-copy">{track.summary}</p>
                      <ul className="note-list compact">
                        {track.points.map((point) => (
                          <li key={point}>{point}</li>
                        ))}
                      </ul>
                      {track.actions?.length ? (
                        <div className="story-actions">
                          {track.actions.map((action) => (
                            <button
                              key={action.label}
                              type="button"
                              className="ghost-button story-action"
                              onClick={(event) => {
                                event.stopPropagation();
                                if (action.group) {
                                  openEndpointGroup(action.group);
                                  return;
                                }
                                if (action.sectionId) {
                                  jumpToDocs(action.sectionId);
                                }
                              }}
                            >
                              {action.label}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              </section>

              <section id="docs-contract" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Contract</p>
                  <h2>How frontend and backend split responsibility</h2>
                </div>
                <div className="split-cards">
                  {implementationLayers.map((layer) => (
                    <article
                      key={layer.title}
                      className={`story-card ${layer.tone === "mint" ? "tone-mint" : "tone-warm"}`}
                    >
                      <h3>{layer.title}</h3>
                      <ul className="note-list compact">
                        {layer.items.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
              </section>

              <section id="docs-flows" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Frontend flows</p>
                  <h2>Three flows a frontend implementer actually needs</h2>
                </div>
                <div className="story-grid">
                  {flowCards.map((flow) => (
                    <article key={flow.title} className="story-card">
                      <p className="eyebrow soft">{flow.subtitle}</p>
                      <h3>{flow.title}</h3>
                      <ol className="step-list">
                        {flow.steps.map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ol>
                      <div className="inline-actions">
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => jumpToTesting(flow.testSectionId)}
                        >
                          Open related test section
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
                <div className="lifecycle-grid">
                  {statusLifecycles.map((lifecycle) => (
                    <article key={lifecycle.name} className="lifecycle-card">
                      <h3>{lifecycle.name}</h3>
                      <div className="pill-row">
                        {lifecycle.states.map((state) => (
                          <StatusPill key={state} tone="accent">
                            {state}
                          </StatusPill>
                        ))}
                      </div>
                      <p className="section-copy">{lifecycle.note}</p>
                    </article>
                  ))}
                </div>
              </section>

              <section id="docs-reference" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Endpoint reference</p>
                  <h2>Real payload shapes for frontend integration</h2>
                </div>
                <div className="filter-bar">
                  {endpointGroups.map((group) => (
                    <button
                      key={group.id}
                      type="button"
                      className={`filter-chip ${
                        activeEndpointGroup === group.id ? "active" : ""
                      }`}
                      onClick={() => setActiveEndpointGroup(group.id)}
                    >
                      {group.label}
                    </button>
                  ))}
                </div>
                <p className="section-copy compact-copy">
                  {endpointGroupSummary[activeEndpointGroup]}
                </p>
                <div className="endpoint-stack">
                  {filteredEndpoints.map((endpoint) => (
                    <EndpointCard
                      key={endpoint.id}
                      endpoint={endpoint}
                      onOpenTest={jumpToTesting}
                    />
                  ))}
                </div>
              </section>

              <section id="docs-records" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Payment record model</p>
                  <h2>What the stored transaction row really means</h2>
                </div>
                <p className="section-copy">
                  This backend stores payment records, not only bank-confirmed settlements. That
                  is why unpaid POS rows exist: the webhook needs something stable to update later.
                </p>
                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        <th>Field</th>
                        <th>Meaning</th>
                        <th>When it is filled</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactionFieldGlossary.map((row) => (
                        <tr key={row.field}>
                          <td>
                            <code>{row.field}</code>
                          </td>
                          <td>{row.meaning}</td>
                          <td>{row.whenFilled}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </div>
        ) : (
          <div className="workspace-layout">
            <div className="content-stack">
              <section id="testing-config" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Runtime config</p>
                  <h2>Point the workbench at the backend and Supabase project</h2>
                </div>
                <div className="form-grid two">
                  <label>
                    Backend URL
                    <input
                      value={config.backendUrl}
                      onChange={(event) => updateConfig("backendUrl", event.target.value)}
                    />
                  </label>
                  <label>
                    Supabase URL
                    <input
                      value={config.supabaseUrl}
                      onChange={(event) => updateConfig("supabaseUrl", event.target.value)}
                    />
                  </label>
                  <label>
                    Supabase publishable key
                    <input
                      value={config.supabasePublishableKey}
                      onChange={(event) =>
                        updateConfig("supabasePublishableKey", event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Bank webhook secret
                    <input
                      value={config.bankWebhookSecret}
                      onChange={(event) =>
                        updateConfig("bankWebhookSecret", event.target.value)
                      }
                    />
                  </label>
                </div>
              </section>

              <section id="testing-auth" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Step 1</p>
                  <h2>Supabase Auth in the browser</h2>
                </div>
                <p className="section-copy">
                  Auth stays on the client side. The workbench signs in with Supabase, then
                  forwards the JWT to authenticated backend endpoints.
                </p>
                <div className="form-grid two">
                  <label>
                    Email
                    <input
                      value={authForm.email}
                      onChange={(event) =>
                        setAuthForm((current) => ({ ...current, email: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Password
                    <input
                      type="password"
                      value={authForm.password}
                      onChange={(event) =>
                        setAuthForm((current) => ({ ...current, password: event.target.value }))
                      }
                    />
                  </label>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => void handleSignUp()}
                    disabled={!supabaseClient || !!busy}
                  >
                    Sign up
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleSignIn()}
                    disabled={!supabaseClient || !!busy}
                  >
                    Sign in
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleSignOut()}
                    disabled={!supabaseClient || !!busy}
                  >
                    Sign out
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void refreshMerchantAccounts()}
                    disabled={!token || !!busy}
                  >
                    Refresh merchant accounts
                  </button>
                </div>
              </section>

              <section id="testing-merchant" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Step 2</p>
                  <h2>Merchant organization and POS account setup</h2>
                </div>
                <div className="form-grid two">
                  <label>
                    Organization name
                    <input
                      value={merchantSignupForm.display_name}
                      onChange={(event) =>
                        setMerchantSignupForm((current) => ({
                          ...current,
                          display_name: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Payee account number
                    <input
                      placeholder="160000000000000000"
                      value={merchantSignupForm.payee_account_number}
                      onChange={(event) =>
                        setMerchantSignupForm((current) => ({
                          ...current,
                          payee_account_number: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Payee name
                    <input
                      value={merchantSignupForm.payee_name}
                      onChange={(event) =>
                        setMerchantSignupForm((current) => ({
                          ...current,
                          payee_name: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Payee address
                    <input
                      value={merchantSignupForm.payee_address}
                      onChange={(event) =>
                        setMerchantSignupForm((current) => ({
                          ...current,
                          payee_address: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Payee city
                    <input
                      value={merchantSignupForm.payee_city}
                      onChange={(event) =>
                        setMerchantSignupForm((current) => ({
                          ...current,
                          payee_city: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => void handleMerchantSignup()}
                    disabled={!token || !!busy}
                  >
                    Merchant signup
                  </button>
                </div>

                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>Selected merchant account</h3>
                  </div>
                  <select
                    value={selectedAccountId}
                    onChange={(event) => setSelectedAccountId(event.target.value)}
                  >
                    <option value="">Select account</option>
                    {merchantAccounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.display_name} ({account.account_type}, role:{" "}
                        {account.effective_role ?? "none"})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>Create POS sub-account</h3>
                  </div>
                  <p className="section-copy">
                    POS means Point of Sale: one shop, station, or cashier context underneath
                    the merchant organization.
                  </p>
                  <div className="form-grid two">
                    <label>
                      POS display name
                      <input
                        value={subAccountForm.display_name}
                        onChange={(event) =>
                          setSubAccountForm((current) => ({
                            ...current,
                            display_name: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      POS payee name
                      <input
                        value={subAccountForm.payee_name}
                        onChange={(event) =>
                          setSubAccountForm((current) => ({
                            ...current,
                            payee_name: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      POS payee account number
                      <input
                        placeholder="160000000000000000"
                        value={subAccountForm.payee_account_number}
                        onChange={(event) =>
                          setSubAccountForm((current) => ({
                            ...current,
                            payee_account_number: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      POS address
                      <input
                        value={subAccountForm.payee_address}
                        onChange={(event) =>
                          setSubAccountForm((current) => ({
                            ...current,
                            payee_address: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      POS city
                      <input
                        value={subAccountForm.payee_city}
                        onChange={(event) =>
                          setSubAccountForm((current) => ({
                            ...current,
                            payee_city: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </div>
                  <div className="inline-actions">
                    <button
                      type="button"
                      onClick={() => void handleCreateSubAccount()}
                      disabled={!token || !selectedAccountId || !!busy}
                    >
                      Create POS sub-account
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handleMerchantTransactions()}
                      disabled={!token || !selectedAccountId || !!busy}
                    >
                      List account transactions
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handleMerchantStats()}
                      disabled={!token || !selectedAccountId || !!busy}
                    >
                      Get account stats
                    </button>
                  </div>
                </div>

                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>Merchant invite</h3>
                  </div>
                  <p className="section-copy">
                    Use this only when you want another signed-in user to operate a selected
                    merchant account. The invite token is tied to the invited email.
                  </p>
                  <div className="form-grid two">
                    <label>
                      Cashier email
                      <input
                        value={inviteForm.email}
                        onChange={(event) =>
                          setInviteForm((current) => ({
                            ...current,
                            email: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Role
                      <select
                        value={inviteForm.role}
                        onChange={(event) =>
                          setInviteForm((current) => ({
                            ...current,
                            role: event.target.value,
                          }))
                        }
                      >
                        <option value="operator">operator</option>
                        <option value="viewer">viewer</option>
                        <option value="admin">admin</option>
                      </select>
                    </label>
                  </div>
                  <div className="inline-actions">
                    <button
                      type="button"
                      onClick={() => void handleInviteCashier()}
                      disabled={!token || !selectedAccountId || !!busy}
                    >
                      Invite cashier
                    </button>
                  </div>
                  <label>
                    Invite token
                    <input
                      value={acceptInviteForm.token || lastInviteToken}
                      onChange={(event) => setAcceptInviteForm({ token: event.target.value })}
                    />
                  </label>
                  <div className="inline-actions">
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handleAcceptInvite()}
                      disabled={!token || !acceptInviteForm.token || !!busy}
                    >
                      Accept invite with current signed-in user
                    </button>
                  </div>
                </div>
              </section>

              <section id="testing-pos" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Step 3</p>
                  <h2>POS IPS transaction and demo webhook</h2>
                </div>
                <p className="section-copy">
                  Create the merchant payment request first. The webhook is what moves that row
                  from <code>awaiting_payment</code> to a completed state.
                </p>
                <div className="form-grid two">
                  <label>
                    Amount
                    <input
                      value={posTransactionForm.amount}
                      onChange={(event) =>
                        setPosTransactionForm((current) => ({
                          ...current,
                          amount: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Description
                    <input
                      value={posTransactionForm.payment_description}
                      onChange={(event) =>
                        setPosTransactionForm((current) => ({
                          ...current,
                          payment_description: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Reference model
                    <input
                      value={posTransactionForm.reference_model}
                      onChange={(event) =>
                        setPosTransactionForm((current) => ({
                          ...current,
                          reference_model: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Reference number
                    <input
                      value={posTransactionForm.reference_number}
                      onChange={(event) =>
                        setPosTransactionForm((current) => ({
                          ...current,
                          reference_number: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => void handleCreatePosTransaction()}
                    disabled={!token || !selectedAccountId || !!busy}
                  >
                    Create POS transaction
                  </button>
                </div>

                <div className="form-grid two">
                  <label>
                    Payment ref
                    <input
                      value={webhookForm.payment_ref || lastPaymentRef}
                      onChange={(event) =>
                        setWebhookForm((current) => ({
                          ...current,
                          payment_ref: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Bank transaction ref
                    <input
                      value={webhookForm.bank_transaction_ref}
                      onChange={(event) =>
                        setWebhookForm((current) => ({
                          ...current,
                          bank_transaction_ref: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Amount
                    <input
                      value={webhookForm.amount}
                      onChange={(event) =>
                        setWebhookForm((current) => ({
                          ...current,
                          amount: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Completed at
                    <input
                      value={webhookForm.completed_at}
                      onChange={(event) =>
                        setWebhookForm((current) => ({
                          ...current,
                          completed_at: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => void handleWebhook()}
                    disabled={!webhookForm.payment_ref || !!busy}
                  >
                    Send fake signed webhook
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleExpirePosTransactions()}
                    disabled={!!busy}
                  >
                    Run POS expiry job
                  </button>
                </div>
              </section>

              <section id="testing-public" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Step 4</p>
                  <h2>Public pay slips</h2>
                </div>
                <p className="section-copy">
                  This is the unauthenticated creation flow. It returns the share slug and the
                  IPS payload string immediately.
                </p>
                <div className="form-grid two">
                  <label>
                    Payee name
                    <input
                      value={publicTransactionForm.payee_name}
                      onChange={(event) =>
                        setPublicTransactionForm((current) => ({
                          ...current,
                          payee_name: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Payee account number
                    <input
                      value={publicTransactionForm.payee_account_number}
                      onChange={(event) =>
                        setPublicTransactionForm((current) => ({
                          ...current,
                          payee_account_number: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Payee address
                    <input
                      value={publicTransactionForm.payee_address}
                      onChange={(event) =>
                        setPublicTransactionForm((current) => ({
                          ...current,
                          payee_address: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Payee city
                    <input
                      value={publicTransactionForm.payee_city}
                      onChange={(event) =>
                        setPublicTransactionForm((current) => ({
                          ...current,
                          payee_city: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Amount
                    <input
                      value={publicTransactionForm.amount}
                      onChange={(event) =>
                        setPublicTransactionForm((current) => ({
                          ...current,
                          amount: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Payment code
                    <input
                      value={publicTransactionForm.payment_code}
                      onChange={(event) =>
                        setPublicTransactionForm((current) => ({
                          ...current,
                          payment_code: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Reference model
                    <input
                      value={publicTransactionForm.reference_model}
                      onChange={(event) =>
                        setPublicTransactionForm((current) => ({
                          ...current,
                          reference_model: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Reference number
                    <input
                      value={publicTransactionForm.reference_number}
                      onChange={(event) =>
                        setPublicTransactionForm((current) => ({
                          ...current,
                          reference_number: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="field-span-two">
                    Payment description
                    <input
                      value={publicTransactionForm.payment_description}
                      onChange={(event) =>
                        setPublicTransactionForm((current) => ({
                          ...current,
                          payment_description: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
                <div className="inline-actions">
                  <button type="button" onClick={() => void handlePublicTransaction()} disabled={!!busy}>
                    Create public pay slip
                  </button>
                </div>

                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>Shared pay slip lookup</h3>
                  </div>
                  <label>
                    Share slug
                    <input
                      value={shareLookupForm.slug || lastShareSlug}
                      onChange={(event) => setShareLookupForm({ slug: event.target.value })}
                    />
                  </label>
                  <div className="inline-actions">
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handlePublicShareLookup()}
                      disabled={!shareLookupForm.slug || !!busy}
                    >
                      Get public share
                    </button>
                  </div>
                </div>
              </section>

              <section id="testing-consumer" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Step 5</p>
                  <h2>Consumer pay slips and account history</h2>
                </div>
                <p className="section-copy">
                  These use the same pay-slip shape as the public flow, but the row is linked to
                  the signed-in consumer and can be listed later.
                </p>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => void handleConsumerProfile()}
                    disabled={!token || !!busy}
                  >
                    Get consumer profile
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleConsumerTransaction()}
                    disabled={!token || !!busy}
                  >
                    Create consumer pay slip
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleConsumerTransactions()}
                    disabled={!token || !!busy}
                  >
                    List my transactions
                  </button>
                </div>
              </section>

              <details className="surface foldout">
                <summary>
                  <span>Appendix: optional subscription and internal-only checks</span>
                  <StatusPill>Not core MVP</StatusPill>
                </summary>
                <div className="foldout-body">
                  <p className="section-copy">
                    These controls stay in the repo for future work, but they are intentionally
                    de-emphasized in the product story and API docs.
                  </p>
                  <div className="form-grid two">
                    <label>
                      Subscriber email
                      <input
                        value={subscriptionForm.subscriber_email}
                        onChange={(event) =>
                          setSubscriptionForm((current) => ({
                            ...current,
                            subscriber_email: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Subscriber name
                      <input
                        value={subscriptionForm.subscriber_name}
                        onChange={(event) =>
                          setSubscriptionForm((current) => ({
                            ...current,
                            subscriber_name: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Amount
                      <input
                        value={subscriptionForm.amount}
                        onChange={(event) =>
                          setSubscriptionForm((current) => ({
                            ...current,
                            amount: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Cadence
                      <select
                        value={subscriptionForm.cadence}
                        onChange={(event) =>
                          setSubscriptionForm((current) => ({
                            ...current,
                            cadence: event.target.value,
                          }))
                        }
                      >
                        <option value="monthly">monthly</option>
                        <option value="weekly">weekly</option>
                      </select>
                    </label>
                    <label>
                      First run at
                      <input
                        value={subscriptionForm.first_run_at}
                        onChange={(event) =>
                          setSubscriptionForm((current) => ({
                            ...current,
                            first_run_at: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Reference number
                      <input
                        value={subscriptionForm.reference_number}
                        onChange={(event) =>
                          setSubscriptionForm((current) => ({
                            ...current,
                            reference_number: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </div>
                  <div className="inline-actions">
                    <button
                      type="button"
                      onClick={() => void handleCreateSubscription()}
                      disabled={!token || !selectedAccountId || !!busy}
                    >
                      Create subscription
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handlePauseSubscription()}
                      disabled={!token || !lastSubscriptionId || !!busy}
                    >
                      Pause subscription
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handleResumeSubscription()}
                      disabled={!token || !lastSubscriptionId || !!busy}
                    >
                      Resume subscription
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handleRunDueSubscriptions()}
                      disabled={!!busy}
                    >
                      Run due subscriptions job
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handleConsumerSubscriptions()}
                      disabled={!token || !!busy}
                    >
                      List my subscriptions
                    </button>
                  </div>
                </div>
              </details>
            </div>

            <aside className="side-rail">
              <div className="rail-card">
                <p className="rail-title">Current runtime</p>
                <dl className="detail-list">
                  <div>
                    <dt>Backend</dt>
                    <dd>{config.backendUrl}</dd>
                  </div>
                  <div>
                    <dt>Supabase</dt>
                    <dd>{config.supabaseUrl || "Not set"}</dd>
                  </div>
                  <div>
                    <dt>Last payment ref</dt>
                    <dd>{lastPaymentRef || "None"}</dd>
                  </div>
                  <div>
                    <dt>Last share slug</dt>
                    <dd>{lastShareSlug || "None"}</dd>
                  </div>
                </dl>
              </div>

              <div className="rail-card">
                <p className="rail-title">Merchant account context</p>
                {merchantAccounts.length === 0 ? (
                  <p className="section-copy">
                    Sign in and refresh merchant accounts to populate this list.
                  </p>
                ) : (
                  <div className="account-list">
                    {merchantAccounts.map((account) => (
                      <button
                        key={account.id}
                        type="button"
                        className={`account-item ${
                          account.id === selectedAccountId ? "active" : ""
                        }`}
                        onClick={() => setSelectedAccountId(account.id)}
                      >
                        <span className="account-line">
                          <strong>{account.display_name}</strong>
                          <StatusPill>{account.account_type}</StatusPill>
                        </span>
                        <span className="account-subline">
                          role {account.effective_role ?? "none"} · {account.payee_city ?? "—"}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="rail-card">
                <div className="rail-head">
                  <p className="rail-title">Activity log</p>
                  <button
                    type="button"
                    className="mini-button"
                    onClick={() => setLogs([])}
                    disabled={logs.length === 0}
                  >
                    Clear
                  </button>
                </div>
                {logs.length === 0 ? (
                  <p className="section-copy">
                    No calls yet. Run actions from the testing panels to build a request log.
                  </p>
                ) : (
                  <div className="log-list">
                    {logs.map((entry) => (
                      <article key={entry.id} className="log-entry">
                        <div className="log-head">
                          <strong>{entry.title}</strong>
                          <span>{new Date(entry.createdAt).toLocaleTimeString()}</span>
                        </div>
                        <pre>{JSON.stringify(entry.data, null, 2)}</pre>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
