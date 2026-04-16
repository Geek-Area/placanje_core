import { useEffect, useState } from "react";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import QRCode from "qrcode";

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
  type DocEndpointGroup,
  type EndpointDoc,
} from "./content";

type ActiveTab = "admin" | "pos" | "documentation" | "testing";

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
  mcc: string | null;
  active: boolean;
  effective_role: string | null;
};

type MerchantSessionData = {
  user_id: string;
  email: string;
  display_name: string | null;
  accounts: MerchantAccount[];
};

type MerchantTransactionSummary = {
  id: string;
  payment_ref: string;
  status: string;
  bank_credit_transfer_identificator?: string | null;
  bank_status_code?: string | null;
  bank_status_description?: string | null;
  qr_string?: string | null;
};

type MerchantTransactionsResponse = {
  items: MerchantTransactionSummary[];
  limit: number;
  offset: number;
};

type MerchantStatsResponse = {
  account_id: string;
  total_transactions: number;
  completed_transactions: number;
  awaiting_payment_transactions: number;
  expired_transactions: number;
  total_completed_amount: string;
};

type PosAccountContext = {
  id: string;
  account_type: string;
  display_name: string;
  payee_name: string;
  payee_account_number: string | null;
  payee_address: string | null;
  payee_city: string | null;
  mcc: string | null;
};

type PosSessionData = {
  username: string;
  merchant_account: PosAccountContext;
};

type PosLoginResponse = PosSessionData & {
  session_token: string;
  expires_at: string;
};

type PosCredentialsResponse = {
  merchant_account_id: string;
  username: string;
  active: boolean;
};

type QuickSetupResult = {
  mainAccount: MerchantAccount;
  posAccount: MerchantAccount;
  credentials: PosCredentialsResponse;
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
            <StatusPill tone={endpoint.method === "GET" ? "warm" : "accent"}>
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
    "admin",
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
  const [lastInviteId, setLastInviteId] = useState("");
  const [lastPaymentRef, setLastPaymentRef] = useState("");
  const [lastTransactionId, setLastTransactionId] = useState("");
  const [lastBankCreditTransferId, setLastBankCreditTransferId] = useState("");
  const [lastShareSlug, setLastShareSlug] = useState("");
  const [lastSubscriptionId, setLastSubscriptionId] = useState("");
  const [merchantSessionData, setMerchantSessionData] = useState<MerchantSessionData | null>(
    null,
  );
  const [lastQuickSetup, setLastQuickSetup] = useState<QuickSetupResult | null>(null);
  const [lastPosTransaction, setLastPosTransaction] =
    useState<MerchantTransactionSummary | null>(null);
  const [lastPosQrImage, setLastPosQrImage] = useState("");
  const [lastMerchantTransactionsData, setLastMerchantTransactionsData] =
    useState<MerchantTransactionsResponse | null>(null);
  const [lastMerchantStatsData, setLastMerchantStatsData] =
    useState<MerchantStatsResponse | null>(null);
  const [posSessionToken, setPosSessionToken] = usePersistentState<string>(
    "placanje-core-pos-session-token",
    "",
  );
  const [posSessionData, setPosSessionData] = useState<PosSessionData | null>(null);
  const [lastPosCredentials, setLastPosCredentials] =
    useState<PosCredentialsResponse | null>(null);

  const [authForm, setAuthForm] = useState({
    email: "",
    password: "",
  });
  const [posAuthForm, setPosAuthForm] = useState({
    username: "pos1",
    password: "test1234",
  });
  const [merchantSignupForm, setMerchantSignupForm] = useState({
    display_name: "",
    payee_account_number: "",
    payee_name: "",
    payee_address: "",
    payee_city: "",
    mcc: "",
  });
  const [subAccountForm, setSubAccountForm] = useState({
    display_name: "",
    payee_name: "",
    payee_account_number: "",
    payee_address: "",
    payee_city: "",
    mcc: "",
  });
  const [inviteForm, setInviteForm] = useState({
    email: "",
    role: "operator",
  });
  const [quickSetupForm, setQuickSetupForm] = useState({
    owner_email_hint: "owner/admin login first",
    main_display_name: "Test Firma",
    main_payee_name: "Test Firma DOO",
    main_payee_account_number: "160000000000000000",
    main_payee_address: "Bulevar Test 1",
    main_payee_city: "Beograd",
    main_mcc: "5411",
    pos_display_name: "POS 1",
    pos_payee_name: "POS 1",
    pos_payee_account_number: "160000000000000000",
    pos_payee_address: "Bulevar Test 1",
    pos_payee_city: "Beograd",
    pos_mcc: "5411",
    pos_username: "pos1",
    pos_password: "test1234",
  });
  const [posCredentialsForm, setPosCredentialsForm] = useState({
    username: "pos1",
    password: "test1234",
  });
  const [acceptInviteForm, setAcceptInviteForm] = useState({
    token: "",
  });
  const [bankProfileForm, setBankProfileForm] = useState({
    provider: "banca_intesa",
    bank_user_id: "",
    terminal_identificator: "",
  });
  const [posTransactionForm, setPosTransactionForm] = useState({
    amount: "450.00",
    payment_description: "Test payment",
    reference_model: "97",
    reference_number: "12345",
  });
  const [bankSyncForm, setBankSyncForm] = useState({
    transaction_id: "",
  });
  const [requestToPayForm, setRequestToPayForm] = useState({
    amount: "450.00",
    debtor_account_number: "",
    one_time_code: "",
    debtor_reference: "",
    debtor_name: "",
    debtor_address: "",
    payment_purpose: "IPS pokaži test",
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
  const selectedPosAccount =
    selectedAccount?.account_type === "pos" ? selectedAccount : null;
  const visiblePosAccounts = merchantAccounts.filter((account) => account.account_type === "pos");
  const visibleOrganizationAccounts = merchantAccounts.filter(
    (account) => account.account_type === "organization",
  );
  const filteredEndpoints = endpointDocs.filter(
    (endpoint) => endpoint.group === activeEndpointGroup,
  );
  const endpointGroupSummary: Record<DocEndpointGroup, string> = {
    public:
      "Use these for Plaćanje.RS public pay-slip creation and shared read-only pay-slip pages.",
    consumer:
      "Use these when a signed-in consumer creates or lists their own Pay slips.",
    merchant:
      "Use these for Instant.Plaćanje.RS merchant onboarding, session lookup, POS hierarchy, and merchant reporting.",
    bank:
      "Use these when the selected POS account must talk to the bank: bank profile setup, SKENIRAJ status sync, and POKAŽI requestToPay.",
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
      setMerchantSessionData(null);
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

  useEffect(() => {
    if (!posSessionToken) {
      setPosSessionData(null);
      return;
    }

    let cancelled = false;

    async function loadPosSession() {
      try {
        const response = await apiRequest<PosSessionData>(config.backendUrl, "/v1/pos/session", {
          token: posSessionToken,
        });
        if (cancelled) {
          return;
        }
        setPosSessionData(response);
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : String(error);
        setPosSessionToken("");
        setPosSessionData(null);
        setLogs((current) => [
          {
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            title: "POS session refresh failed",
            data: { message },
            createdAt: new Date().toISOString(),
          },
          ...current,
        ]);
      }
    }

    void loadPosSession();

    return () => {
      cancelled = true;
    };
  }, [config.backendUrl, posSessionToken, setPosSessionToken]);

  useEffect(() => {
    if (visiblePosAccounts.length === 1 && selectedAccount?.account_type !== "pos") {
      setSelectedAccountId(visiblePosAccounts[0].id);
    }
  }, [selectedAccount, setSelectedAccountId, visiblePosAccounts]);

  useEffect(() => {
    let cancelled = false;

    async function renderQr() {
      if (!lastPosTransaction?.qr_string) {
        setLastPosQrImage("");
        return;
      }

      try {
        const dataUrl = await QRCode.toDataURL(lastPosTransaction.qr_string, {
          margin: 1,
          width: 320,
          color: {
            dark: "#111111",
            light: "#ffffff",
          },
        });
        if (!cancelled) {
          setLastPosQrImage(dataUrl);
        }
      } catch {
        if (!cancelled) {
          setLastPosQrImage("");
        }
      }
    }

    void renderQr();

    return () => {
      cancelled = true;
    };
  }, [lastPosTransaction]);

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
    setMerchantSessionData(null);
    setLastInviteId("");
    setLastInviteToken("");
    setLastTransactionId("");
    setLastBankCreditTransferId("");
  }

  async function handleMerchantSession() {
    const response = await runAction("Load owner context", () =>
      apiRequest<MerchantSessionData>(config.backendUrl, "/v1/merchant/session", {
        token,
      }),
    );
    setMerchantSessionData(response);
  }

  async function handleMerchantLogout() {
    if (!supabaseClient || !token) {
      return;
    }
    await runAction("Log out owner session", () =>
      apiRequest(config.backendUrl, "/v1/merchant/logout", {
        method: "POST",
        token,
      }),
    );
    await supabaseClient.auth.signOut();
    setMerchantAccounts([]);
    setSelectedAccountId("");
    setMerchantSessionData(null);
  }

  async function handleMerchantSignup() {
    const response = await runAction("Merchant signup", () =>
      apiRequest<MerchantAccount>(config.backendUrl, "/v1/merchant/signup", {
        method: "POST",
        token,
        body: {
          ...merchantSignupForm,
          mcc: merchantSignupForm.mcc || null,
        },
      }),
    );
    setSelectedAccountId(response.id);
    await refreshMerchantAccounts();
  }

  async function handleQuickSetup() {
    const response = await runAction<QuickSetupResult>("Quick POS setup", async () => {
      const mainAccount = await apiRequest<MerchantAccount>(
        config.backendUrl,
        "/v1/merchant/signup",
        {
          method: "POST",
          token,
          body: {
            display_name: quickSetupForm.main_display_name,
            payee_name: quickSetupForm.main_payee_name,
            payee_account_number: quickSetupForm.main_payee_account_number,
            payee_address: quickSetupForm.main_payee_address,
            payee_city: quickSetupForm.main_payee_city,
            mcc: quickSetupForm.main_mcc || null,
          },
        },
      );

      const posAccount = await apiRequest<MerchantAccount>(
        config.backendUrl,
        `/v1/merchant/accounts/${mainAccount.id}/sub-accounts`,
        {
          method: "POST",
          token,
          body: {
            display_name: quickSetupForm.pos_display_name,
            payee_name: quickSetupForm.pos_payee_name,
            payee_account_number: quickSetupForm.pos_payee_account_number || null,
            payee_address: quickSetupForm.pos_payee_address,
            payee_city: quickSetupForm.pos_payee_city,
            mcc: quickSetupForm.pos_mcc || null,
          },
        },
      );

      const credentials = await apiRequest<PosCredentialsResponse>(
        config.backendUrl,
        `/v1/merchant/accounts/${posAccount.id}/pos-credentials`,
        {
          method: "PUT",
          token,
          body: {
            username: quickSetupForm.pos_username,
            password: quickSetupForm.pos_password,
          },
        },
      );

      return {
        mainAccount,
        posAccount,
        credentials,
      };
    });

    setLastQuickSetup(response);
    setLastPosCredentials(response.credentials);
    setSelectedAccountId(response.posAccount.id);
    setMerchantSignupForm({
      display_name: response.mainAccount.display_name,
      payee_account_number: response.mainAccount.payee_account_number ?? "",
      payee_name: response.mainAccount.payee_name ?? "",
      payee_address: response.mainAccount.payee_address ?? "",
      payee_city: response.mainAccount.payee_city ?? "",
      mcc: response.mainAccount.mcc ?? "",
    });
    setSubAccountForm({
      display_name: response.posAccount.display_name,
      payee_name: response.posAccount.payee_name ?? "",
      payee_account_number: response.posAccount.payee_account_number ?? "",
      payee_address: response.posAccount.payee_address ?? "",
      payee_city: response.posAccount.payee_city ?? "",
      mcc: response.posAccount.mcc ?? "",
    });
    setPosCredentialsForm({
      username: response.credentials.username,
      password: quickSetupForm.pos_password,
    });
    setPosAuthForm({
      username: response.credentials.username,
      password: quickSetupForm.pos_password,
    });
    await refreshMerchantAccounts();
  }

  async function handleCreateSubAccount() {
    const response = await runAction("Create POS account", () =>
      apiRequest<MerchantAccount>(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/sub-accounts`,
        {
          method: "POST",
          token,
          body: {
            ...subAccountForm,
            mcc: subAccountForm.mcc || null,
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
      apiRequest<{ token?: string; invite_id?: string }>(
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
    if (response.invite_id) {
      setLastInviteId(response.invite_id);
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

  async function handleRevokeInvite() {
    await runAction("Revoke merchant invite", () =>
      apiRequest(config.backendUrl, `/v1/merchant/invites/${lastInviteId}/revoke`, {
        method: "POST",
        token,
      }),
    );
    setLastInviteId("");
    setLastInviteToken("");
    setAcceptInviteForm({ token: "" });
  }

  async function handleUpsertBankProfile() {
    await runAction("Configure bank profile", () =>
      apiRequest(config.backendUrl, `/v1/merchant/accounts/${selectedAccountId}/bank-profile`, {
        method: "PUT",
        token,
        body: bankProfileForm,
      }),
    );
  }

  async function handleUpsertPosCredentials() {
    const response = await runAction<PosCredentialsResponse>("Create POS credentials", () =>
      apiRequest(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/pos-credentials`,
        {
          method: "PUT",
          token,
          body: posCredentialsForm,
        },
      ),
    );
    setLastPosCredentials(response);
    setPosAuthForm({
      username: response.username,
      password: posCredentialsForm.password,
    });
  }

  async function handlePosLogin() {
    const response = await runAction<PosLoginResponse>("POS login", () =>
      apiRequest(config.backendUrl, "/v1/pos/session", {
        method: "POST",
        body: posAuthForm,
      }),
    );
    setPosSessionToken(response.session_token);
    setPosSessionData({
      username: response.username,
      merchant_account: response.merchant_account,
    });
  }

  async function handlePosSessionRefresh() {
    if (!posSessionToken) {
      return;
    }
    const response = await runAction<PosSessionData>("POS session", () =>
      apiRequest(config.backendUrl, "/v1/pos/session", {
        token: posSessionToken,
      }),
    );
    setPosSessionData(response);
  }

  async function handlePosLogout() {
    if (!posSessionToken) {
      return;
    }
    await runAction("POS logout", () =>
      apiRequest(config.backendUrl, "/v1/pos/logout", {
        method: "POST",
        token: posSessionToken,
      }),
    );
    setPosSessionToken("");
    setPosSessionData(null);
  }

  async function handlePosTerminalCreateTransaction() {
    const response = await runAction<{
      payment_ref: string;
      status: string;
      qr_string: string;
      transaction_id: string;
      bank_credit_transfer_identificator?: string | null;
    }>("POS create transaction", () =>
      apiRequest(config.backendUrl, "/v1/pos/transactions", {
        method: "POST",
        token: posSessionToken,
        body: posTransactionForm,
      }),
    );
    setLastPaymentRef(response.payment_ref);
    setLastTransactionId(response.transaction_id);
    setBankSyncForm({ transaction_id: response.transaction_id });
    setLastBankCreditTransferId(response.bank_credit_transfer_identificator ?? "");
    setLastPosTransaction({
      id: response.transaction_id,
      payment_ref: response.payment_ref,
      status: response.status,
      bank_credit_transfer_identificator: response.bank_credit_transfer_identificator ?? null,
      qr_string: response.qr_string,
    });
  }

  async function handlePosTerminalTransactions() {
    const response = await runAction<MerchantTransactionsResponse>("POS transactions", () =>
      apiRequest(config.backendUrl, "/v1/pos/transactions", {
        token: posSessionToken,
      }),
    );
    setLastMerchantTransactionsData(response);
  }

  async function handlePosTerminalStats() {
    const response = await runAction<MerchantStatsResponse>("POS stats", () =>
      apiRequest(config.backendUrl, "/v1/pos/stats", {
        token: posSessionToken,
      }),
    );
    setLastMerchantStatsData(response);
  }

  async function handlePosTerminalSyncBankStatus() {
    const response = await runAction<MerchantTransactionSummary>("POS sync bank status", () =>
      apiRequest(
        config.backendUrl,
        `/v1/pos/transactions/${bankSyncForm.transaction_id}/sync-bank-status`,
        {
          method: "POST",
          token: posSessionToken,
        },
      ),
    );
    setLastPaymentRef(response.payment_ref);
    setLastTransactionId(response.id);
    setLastBankCreditTransferId(response.bank_credit_transfer_identificator ?? "");
    setLastPosTransaction(response);
  }

  async function handleCreatePosTransaction() {
    const response = await runAction<{
      payment_ref: string;
      status: string;
      qr_string: string;
      transaction_id: string;
      bank_credit_transfer_identificator?: string | null;
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
    setLastTransactionId(response.transaction_id);
    setBankSyncForm({ transaction_id: response.transaction_id });
    setLastBankCreditTransferId(response.bank_credit_transfer_identificator ?? "");
    setLastPosTransaction({
      id: response.transaction_id,
      payment_ref: response.payment_ref,
      status: response.status,
      bank_credit_transfer_identificator: response.bank_credit_transfer_identificator ?? null,
      qr_string: response.qr_string,
    });
    setWebhookForm((current) => ({
      ...current,
      payment_ref: response.payment_ref,
      amount: posTransactionForm.amount,
    }));
  }

  async function handleSyncBankStatus() {
    const response = await runAction<MerchantTransactionSummary>("Sync bank status", () =>
      apiRequest(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/transactions/${bankSyncForm.transaction_id}/sync-bank-status`,
        {
          method: "POST",
          token,
        },
      ),
    );
    setLastPaymentRef(response.payment_ref);
    setLastTransactionId(response.id);
    setLastBankCreditTransferId(response.bank_credit_transfer_identificator ?? "");
    setLastPosTransaction(response);
  }

  async function handleRequestToPay() {
    const response = await runAction<MerchantTransactionSummary>("Request to pay (POKAZI)", () =>
      apiRequest(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/request-to-pay`,
        {
          method: "POST",
          token,
          body: requestToPayForm,
        },
      ),
    );
    setLastPaymentRef(response.payment_ref);
    setLastTransactionId(response.id);
    setLastBankCreditTransferId(response.bank_credit_transfer_identificator ?? "");
    setLastPosTransaction(response);
    setBankSyncForm({ transaction_id: response.id });
  }

  async function handleMerchantTransactions() {
    const response = await runAction<MerchantTransactionsResponse>("List account transactions", () =>
      apiRequest(
        config.backendUrl,
        `/v1/merchant/accounts/${selectedAccountId}/transactions`,
        {
          token,
        },
      ),
    );
    setLastMerchantTransactionsData(response);
  }

  async function handleMerchantStats() {
    const response = await runAction<MerchantStatsResponse>("Get account stats", () =>
      apiRequest(config.backendUrl, `/v1/merchant/accounts/${selectedAccountId}/stats`, {
        token,
      }),
    );
    setLastMerchantStatsData(response);
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
            className={`tab-button ${activeTab === "admin" ? "active" : ""}`}
            onClick={() => setActiveTab("admin")}
          >
            Admin setup
          </button>
          <button
            type="button"
            className={`tab-button ${activeTab === "pos" ? "active" : ""}`}
            onClick={() => setActiveTab("pos")}
          >
            POS terminal
          </button>
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
            Advanced
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
                  Open advanced tools
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
                  is why unpaid POS rows exist: the bank sync flow needs something stable to update later.
                </p>
                <ul className="note-list">
                  <li>`payment_ref` is the stable backend reference for the payment.</li>
                  <li>`status` changes later when the bank confirms or rejects the payment.</li>
                  <li>`qr_string` is the payload the frontend turns into a visible QR image.</li>
                </ul>
              </section>
            </div>
          </div>
        ) : activeTab === "admin" ? (
          <div className="workspace-layout">
            <div className="content-stack">
              <section className="surface mode-hero">
                <div className="section-heading">
                  <p className="eyebrow">Admin setup</p>
                  <h2>Napravi test firmu, jedan POS i dodeli POS login</h2>
                </div>
                <p className="section-copy">
                  Ovo je ekran za tebe. Uloguješ se kao owner, klikneš quick setup ili ručno
                  napraviš firmu i POS, i dodeliš jednom korisniku pristup tom POS nalogu.
                </p>
                <div className="story-actions">
                  <button type="button" className="ghost-button" onClick={() => setActiveTab("pos")}>
                    Open POS terminal view
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => setActiveTab("testing")}
                  >
                    Open advanced tools
                  </button>
                </div>
              </section>

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Runtime config</p>
                  <h2>Unesi backend i Supabase projekat jednom</h2>
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
                    Demo webhook secret (optional)
                    <input
                      value={config.bankWebhookSecret}
                      onChange={(event) => updateConfig("bankWebhookSecret", event.target.value)}
                    />
                  </label>
                </div>
              </section>

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Owner login</p>
                  <h2>Uloguj se kao glavni korisnik koji pravi naloge</h2>
                </div>
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
                    onClick={() => void handleSignIn()}
                    disabled={!supabaseClient || !!busy}
                  >
                    Sign in as owner
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleMerchantSession()}
                    disabled={!token || !!busy}
                  >
                    Check logged-in user
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void refreshMerchantAccounts()}
                    disabled={!token || !!busy}
                  >
                    Refresh visible accounts
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleSignOut()}
                    disabled={!supabaseClient || !!busy}
                  >
                    Log out
                  </button>
                </div>
              </section>

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Quick setup</p>
                  <h2>Jedan klik za test firmu + jedan POS</h2>
                </div>
                <p className="section-copy">
                  Ako nemaš prave podatke, ostavi ove test vrednosti. Ovo pravi test firmu,
                  jedan POS podnalog i odmah pravi POS login kredencijale za njega.
                </p>
                <div className="form-grid two">
                  <label>
                    Main account name
                    <input
                      value={quickSetupForm.main_display_name}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          main_display_name: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Main payee name
                    <input
                      value={quickSetupForm.main_payee_name}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          main_payee_name: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Main account number
                    <input
                      value={quickSetupForm.main_payee_account_number}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          main_payee_account_number: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Main city
                    <input
                      value={quickSetupForm.main_payee_city}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          main_payee_city: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="field-span-two">
                    Main address
                    <input
                      value={quickSetupForm.main_payee_address}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          main_payee_address: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    POS name
                    <input
                      value={quickSetupForm.pos_display_name}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          pos_display_name: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    POS payee name
                    <input
                      value={quickSetupForm.pos_payee_name}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          pos_payee_name: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    POS account number
                    <input
                      value={quickSetupForm.pos_payee_account_number}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          pos_payee_account_number: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    POS city
                    <input
                      value={quickSetupForm.pos_payee_city}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          pos_payee_city: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="field-span-two">
                    POS address
                    <input
                      value={quickSetupForm.pos_payee_address}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          pos_payee_address: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    POS username
                    <input
                      value={quickSetupForm.pos_username}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          pos_username: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    POS password
                    <input
                      type="password"
                      value={quickSetupForm.pos_password}
                      onChange={(event) =>
                        setQuickSetupForm((current) => ({
                          ...current,
                          pos_password: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => void handleQuickSetup()}
                    disabled={!token || !!busy}
                  >
                    Create test company + POS + POS login
                  </button>
                </div>
              </section>

              {lastQuickSetup ? (
                <section className="surface">
                  <div className="section-heading">
                    <p className="eyebrow">Result</p>
                    <h2>Quick setup finished</h2>
                  </div>
                  <div className="split-cards">
                    <article className="story-card tone-warm">
                      <h3>Main account</h3>
                      <p className="section-copy">{lastQuickSetup.mainAccount.display_name}</p>
                      <ul className="note-list compact">
                        <li>ID: {lastQuickSetup.mainAccount.id}</li>
                        <li>City: {lastQuickSetup.mainAccount.payee_city ?? "—"}</li>
                      </ul>
                    </article>
                    <article className="story-card tone-mint">
                      <h3>POS account</h3>
                      <p className="section-copy">{lastQuickSetup.posAccount.display_name}</p>
                      <ul className="note-list compact">
                        <li>ID: {lastQuickSetup.posAccount.id}</li>
                        <li>Username: {lastQuickSetup.credentials.username}</li>
                        <li>Status: {lastQuickSetup.credentials.active ? "active" : "inactive"}</li>
                      </ul>
                    </article>
                  </div>
                </section>
              ) : null}

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Visible accounts</p>
                  <h2>Main accounts and POS accounts on the current user</h2>
                </div>
                <div className="split-cards">
                  <article className="story-card">
                    <h3>Main accounts</h3>
                    {visibleOrganizationAccounts.length === 0 ? (
                      <p className="section-copy">No main accounts loaded yet.</p>
                    ) : (
                      <div className="account-list">
                        {visibleOrganizationAccounts.map((account) => (
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
                  </article>
                  <article className="story-card">
                    <h3>POS accounts</h3>
                    {visiblePosAccounts.length === 0 ? (
                      <p className="section-copy">No POS accounts loaded yet.</p>
                    ) : (
                      <div className="account-list">
                        {visiblePosAccounts.map((account) => (
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
                  </article>
                </div>
              </section>

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">POS login credentials</p>
                  <h2>Napravi ili promeni login za izabrani POS</h2>
                </div>
                <p className="section-copy">
                  Izaberi POS karticu iznad, pa ovde postavi username i password koje će taj POS
                  korisnik koristiti za ulaz u POS terminal.
                </p>
                <div className="form-grid two">
                  <label>
                    POS username
                    <input
                      value={posCredentialsForm.username}
                      onChange={(event) =>
                        setPosCredentialsForm((current) => ({
                          ...current,
                          username: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    POS password
                    <input
                      type="password"
                      value={posCredentialsForm.password}
                      onChange={(event) =>
                        setPosCredentialsForm((current) => ({
                          ...current,
                          password: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => void handleUpsertPosCredentials()}
                    disabled={!token || !selectedPosAccount || !!busy}
                  >
                    Save POS login
                  </button>
                </div>
                {lastPosCredentials ? (
                  <ul className="note-list compact">
                    <li>Saved username: {lastPosCredentials.username}</li>
                    <li>Linked POS id: {lastPosCredentials.merchant_account_id}</li>
                  </ul>
                ) : null}
              </section>
            </div>

            <aside className="side-rail">
              <div className="rail-card accent-card">
                <p className="rail-title">What to send</p>
                <ul className="note-list compact">
                  <li>Send POS username and POS password only.</li>
                  <li>Do not send owner login.</li>
                  <li>Do not send Supabase URL or publishable key.</li>
                </ul>
              </div>
              <div className="rail-card">
                <p className="rail-title">Current runtime</p>
                <dl className="detail-list">
                  <div>
                    <dt>User</dt>
                    <dd>{session?.user.email ?? "Not signed in"}</dd>
                  </div>
                  <div>
                    <dt>Selected account</dt>
                    <dd>{selectedAccount?.display_name ?? "None"}</dd>
                  </div>
                  <div>
                    <dt>Backend</dt>
                    <dd>{config.backendUrl}</dd>
                  </div>
                </dl>
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
                  <p className="section-copy">No calls yet.</p>
                ) : (
                  <div className="log-list">
                    {logs.slice(0, 6).map((entry) => (
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
        ) : activeTab === "pos" ? (
          <div className="workspace-layout">
            <div className="content-stack">
              <section className="surface mode-hero">
                <div className="section-heading">
                  <p className="eyebrow">POS terminal</p>
                  <h2>Ovo je ekran koji POS korisnik zapravo treba da koristi</h2>
                </div>
                <p className="section-copy">
                  Ideja je prosta: POS korisnik se uloguje, vidi svoj POS, unese iznos i klikne
                  generate. Sve ostalo je sklonjeno sa strane.
                </p>
              </section>

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">POS login</p>
                  <h2>Uloguj se kao POS korisnik</h2>
                </div>
                <div className="form-grid two">
                  <label>
                    POS username
                    <input
                      value={posAuthForm.username}
                      onChange={(event) =>
                        setPosAuthForm((current) => ({
                          ...current,
                          username: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Password
                    <input
                      type="password"
                      value={posAuthForm.password}
                      onChange={(event) =>
                        setPosAuthForm((current) => ({
                          ...current,
                          password: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => void handlePosLogin()}
                    disabled={!!busy}
                  >
                    Sign in as POS user
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handlePosSessionRefresh()}
                    disabled={!posSessionToken || !!busy}
                  >
                    Refresh POS session
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handlePosLogout()}
                    disabled={!posSessionToken || !!busy}
                  >
                    Log out POS
                  </button>
                </div>
              </section>

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">My POS account</p>
                  <h2>Ovo je POS nalog koji je vezan za tvoj login</h2>
                </div>
                {!posSessionData ? (
                  <p className="section-copy">
                    Uloguj se sa POS username i password. Posle login-a ovde će se pojaviti samo
                    jedan POS nalog koji pripada tom loginu.
                  </p>
                ) : (
                  <div className="account-list">
                    <div className="account-item terminal-account active">
                      <span className="account-line">
                        <strong>{posSessionData.merchant_account.display_name}</strong>
                        <StatusPill>{posSessionData.merchant_account.account_type}</StatusPill>
                      </span>
                      <span className="account-subline">
                        username {posSessionData.username} ·{" "}
                        {posSessionData.merchant_account.payee_city ?? "—"}
                      </span>
                    </div>
                  </div>
                )}
              </section>

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Generate</p>
                  <h2>Unesi iznos i generiši merchant IPS</h2>
                </div>
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
                    onClick={() => void handlePosTerminalCreateTransaction()}
                    disabled={!posSessionToken || !posSessionData || !!busy}
                  >
                    Generate IPS QR
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handlePosTerminalTransactions()}
                    disabled={!posSessionToken || !posSessionData || !!busy}
                  >
                    See my transactions
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handlePosTerminalStats()}
                    disabled={!posSessionToken || !posSessionData || !!busy}
                  >
                    See my stats
                  </button>
                </div>
              </section>

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Generated result</p>
                  <h2>Poslednji generisani IPS zapis</h2>
                </div>
                {lastPosTransaction ? (
                  <div className="split-cards">
                    <article className="story-card tone-mint">
                      <h3>Payment data</h3>
                      <ul className="note-list compact">
                        <li>Payment ref: {lastPosTransaction.payment_ref}</li>
                        <li>Status: {lastPosTransaction.status}</li>
                        <li>
                          Bank reference:{" "}
                          {lastPosTransaction.bank_credit_transfer_identificator ?? "None"}
                        </li>
                      </ul>
                    </article>
                    <article className="story-card">
                      <h3>QR preview</h3>
                      {lastPosQrImage ? (
                        <div className="qr-preview-shell">
                          <img
                            className="qr-preview-image"
                            src={lastPosQrImage}
                            alt="Generated IPS QR"
                          />
                        </div>
                      ) : (
                        <p className="section-copy">QR preview is not ready yet.</p>
                      )}
                      <p className="code-label">QR payload</p>
                      <pre className="code-block">
                        {lastPosTransaction.qr_string ?? "No qr_string returned yet."}
                      </pre>
                    </article>
                  </div>
                ) : (
                  <p className="section-copy">
                    Nema još generisanog IPS zapisa. Izaberi POS i klikni Generate IPS QR.
                  </p>
                )}
                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>Optional bank status check</h3>
                  </div>
                  <p className="section-copy">
                    Ovo koristiš tek kada taj POS ima pravi bank profile. Bez bank podataka,
                    možeš da generišeš test QR, ali ne i da dobiješ stvarnu potvrdu banke.
                  </p>
                  <div className="form-grid two">
                    <label>
                      Transaction ID to sync
                      <input
                        value={bankSyncForm.transaction_id || lastTransactionId}
                        onChange={(event) =>
                          setBankSyncForm({ transaction_id: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Last bank reference
                      <input value={lastBankCreditTransferId} readOnly />
                    </label>
                  </div>
                  <div className="inline-actions">
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handlePosTerminalSyncBankStatus()}
                      disabled={!posSessionToken || !posSessionData || !bankSyncForm.transaction_id || !!busy}
                    >
                      Check if bank confirmed it
                    </button>
                  </div>
                </div>
              </section>

              <section className="surface">
                <div className="section-heading">
                  <p className="eyebrow">My data</p>
                  <h2>Poslednji odgovor za transakcije i statistiku</h2>
                </div>
                <div className="split-cards">
                  <article className="story-card">
                    <h3>Transactions</h3>
                    {lastMerchantTransactionsData ? (
                      <pre className="code-block">
                        {JSON.stringify(lastMerchantTransactionsData, null, 2)}
                      </pre>
                    ) : (
                      <p className="section-copy">
                        Klikni <strong>See my transactions</strong> da vidiš odgovor ovde.
                      </p>
                    )}
                  </article>
                  <article className="story-card">
                    <h3>Stats</h3>
                    {lastMerchantStatsData ? (
                      <pre className="code-block">
                        {JSON.stringify(lastMerchantStatsData, null, 2)}
                      </pre>
                    ) : (
                      <p className="section-copy">
                        Klikni <strong>See my stats</strong> da vidiš odgovor ovde.
                      </p>
                    )}
                  </article>
                </div>
              </section>
            </div>

            <aside className="side-rail">
              <div className="rail-card accent-card">
                <p className="rail-title">Plain English</p>
                <ul className="note-list compact">
                  <li>Sign in with POS username and password.</li>
                  <li>Your POS account appears automatically.</li>
                  <li>Enter amount.</li>
                  <li>Click Generate IPS QR.</li>
                </ul>
              </div>
              <div className="rail-card">
                <p className="rail-title">Current POS context</p>
                <dl className="detail-list">
                  <div>
                    <dt>POS username</dt>
                    <dd>{posSessionData?.username ?? "Not signed in"}</dd>
                  </div>
                  <div>
                    <dt>Selected POS</dt>
                    <dd>{posSessionData?.merchant_account.display_name ?? "No POS selected"}</dd>
                  </div>
                </dl>
              </div>
              {posSessionData ? (
                <div className="rail-card">
                  <p className="rail-title">Current session</p>
                  <dl className="detail-list">
                    <div>
                      <dt>Username</dt>
                      <dd>{posSessionData.username}</dd>
                    </div>
                    <div>
                      <dt>POS account id</dt>
                      <dd>{posSessionData.merchant_account.id}</dd>
                    </div>
                  </dl>
                </div>
              ) : null}
            </aside>
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
                    Demo webhook secret (optional)
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
                  <h2>Login, visible accounts, and logout</h2>
                </div>
                <p className="section-copy">
                  Prosto rečeno: ovde proveravaš ko je trenutno ulogovan. Supabase radi login,
                  a backend iz tokena čita kojim merchant nalozima taj korisnik sme da pristupi.
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
                    onClick={() => void handleMerchantSession()}
                    disabled={!token || !!busy}
                  >
                    Check logged-in user
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void refreshMerchantAccounts()}
                    disabled={!token || !!busy}
                  >
                    Refresh visible accounts
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleMerchantLogout()}
                    disabled={!token || !supabaseClient || !!busy}
                  >
                    Log out everywhere
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleSignOut()}
                    disabled={!supabaseClient || !!busy}
                  >
                    Log out only here
                  </button>
                </div>
              </section>

              <section id="testing-merchant" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Step 2</p>
                  <h2>Main account, POS, and bank setup</h2>
                </div>
                <div className="form-grid two">
                  <label>
                    Main account name
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
                  <label>
                    MCC
                    <input
                      placeholder="5411"
                      value={merchantSignupForm.mcc}
                      onChange={(event) =>
                        setMerchantSignupForm((current) => ({
                          ...current,
                          mcc: event.target.value,
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
                    Create main account
                  </button>
                </div>

                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>Selected main or POS account</h3>
                  </div>
                  <p className="section-copy">
                    Choose the main account to create a POS. Choose a POS only for bank setup,
                    transactions, or stats.
                  </p>
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
                    <h3>Create POS account</h3>
                  </div>
                  <p className="section-copy">
                    This is the shop/store account that the POS user should actually use in the POS app.
                  </p>
                  <div className="form-grid two">
                    <label>
                      POS name
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
                    <label>
                      POS MCC
                      <input
                        placeholder="5411"
                        value={subAccountForm.mcc}
                        onChange={(event) =>
                          setSubAccountForm((current) => ({
                            ...current,
                            mcc: event.target.value,
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
                    Create POS account
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handleMerchantTransactions()}
                      disabled={!token || !selectedAccountId || !!busy}
                    >
                      List this account transactions
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handleMerchantStats()}
                      disabled={!token || !selectedAccountId || !!busy}
                    >
                      Get this account stats
                    </button>
                  </div>
                </div>

                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>Give user access to this POS</h3>
                  </div>
                  <p className="section-copy">
                    Prvo napraviš login nalog, pa ga ovde vežeš na njegov
                    POS podnalog. `Revoke invite` znači: poništi pozivnicu ako je još nije iskoristio.
                  </p>
                  <div className="form-grid two">
                    <label>
                      User email
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
                      Give access to this POS
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
                      Accept access for current user
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => void handleRevokeInvite()}
                      disabled={!token || !lastInviteId || !!busy}
                    >
                      Cancel invite
                    </button>
                  </div>
                </div>

                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>Bank profile for selected POS</h3>
                  </div>
                  <p className="section-copy">
                    Bank profile su podaci koje banka dodeli tom podnalogu: bank username i TID.
                    To nije POS login, to je identitet prodajnog mesta prema banci.
                  </p>
                  <div className="form-grid two">
                    <label>
                      Provider
                      <input
                        value={bankProfileForm.provider}
                        onChange={(event) =>
                          setBankProfileForm((current) => ({
                            ...current,
                            provider: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Bank user ID
                      <input
                        placeholder="user from bank"
                        value={bankProfileForm.bank_user_id}
                        onChange={(event) =>
                          setBankProfileForm((current) => ({
                            ...current,
                            bank_user_id: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Terminal identificator (TID)
                      <input
                        placeholder="TID12345"
                        value={bankProfileForm.terminal_identificator}
                        onChange={(event) =>
                          setBankProfileForm((current) => ({
                            ...current,
                            terminal_identificator: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </div>
                  <div className="inline-actions">
                    <button
                      type="button"
                      onClick={() => void handleUpsertBankProfile()}
                      disabled={!token || !selectedAccountId || !!busy}
                    >
                      Save bank profile
                    </button>
                  </div>
                </div>
              </section>

              <section id="testing-pos" className="surface">
                <div className="section-heading">
                  <p className="eyebrow">Step 3</p>
                  <h2>Merchant IPS flows: SKENIRAJ and POKAŽI</h2>
                </div>
                <div className="split-cards">
                  <article className="story-card tone-mint">
                    <h3>SKENIRAJ</h3>
                    <p className="section-copy">
                      POS korisnik unese iznos, backend napravi QR trgovca, kupac ga skenira u svojoj
                      bank app, a naš backend zatim proverava kod banke da li je uplata stvarno
                      prošla.
                    </p>
                  </article>
                  <article className="story-card tone-warm">
                    <h3>POKAŽI</h3>
                    <p className="section-copy">
                      Kupac pokaže svoj QR kod. POS ili aplikacija pročita podatke kupca i naš
                      backend odmah šalje banci zahtev za plaćanje. Odgovor je odmah uspeh ili
                      greška.
                    </p>
                  </article>
                </div>

                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>SKENIRAJ: create merchant QR and sync status</h3>
                  </div>
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
                      Create merchant QR transaction
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
                  <div className="form-grid two">
                    <label>
                      Transaction ID to sync
                      <input
                        value={bankSyncForm.transaction_id || lastTransactionId}
                        onChange={(event) =>
                          setBankSyncForm({ transaction_id: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Last bank reference
                      <input value={lastBankCreditTransferId} readOnly />
                    </label>
                  </div>
                  <div className="inline-actions">
                    <button
                      type="button"
                      onClick={() => void handleSyncBankStatus()}
                      disabled={!token || !selectedAccountId || !bankSyncForm.transaction_id || !!busy}
                    >
                      Sync bank status
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
                </div>

                <div className="subsurface">
                  <div className="section-heading compact">
                    <h3>POKAŽI: send requestToPay from buyer QR data</h3>
                  </div>
                  <p className="section-copy">
                    Ovde ručno unosiš ono što bi normalno došlo skeniranjem QR-a kupca: račun
                    kupca i jednokratni kod. Backend to prosleđuje banci.
                  </p>
                  <div className="form-grid two">
                    <label>
                      Amount
                      <input
                        value={requestToPayForm.amount}
                        onChange={(event) =>
                          setRequestToPayForm((current) => ({
                            ...current,
                            amount: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Debtor account number
                      <input
                        placeholder="160000000000000000"
                        value={requestToPayForm.debtor_account_number}
                        onChange={(event) =>
                          setRequestToPayForm((current) => ({
                            ...current,
                            debtor_account_number: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      One-time code (OTP)
                      <input
                        placeholder="optional"
                        value={requestToPayForm.one_time_code}
                        onChange={(event) =>
                          setRequestToPayForm((current) => ({
                            ...current,
                            one_time_code: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Debtor reference
                      <input
                        placeholder="optional"
                        value={requestToPayForm.debtor_reference}
                        onChange={(event) =>
                          setRequestToPayForm((current) => ({
                            ...current,
                            debtor_reference: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Debtor name
                      <input
                        placeholder="optional"
                        value={requestToPayForm.debtor_name}
                        onChange={(event) =>
                          setRequestToPayForm((current) => ({
                            ...current,
                            debtor_name: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Debtor address
                      <input
                        placeholder="optional"
                        value={requestToPayForm.debtor_address}
                        onChange={(event) =>
                          setRequestToPayForm((current) => ({
                            ...current,
                            debtor_address: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label className="field-span-two">
                      Payment purpose
                      <input
                        value={requestToPayForm.payment_purpose}
                        onChange={(event) =>
                          setRequestToPayForm((current) => ({
                            ...current,
                            payment_purpose: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </div>
                  <div className="inline-actions">
                    <button
                      type="button"
                      onClick={() => void handleRequestToPay()}
                      disabled={!token || !selectedAccountId || !!busy}
                    >
                      Send requestToPay
                    </button>
                  </div>
                </div>

                <details className="subsurface foldout">
                  <summary>
                    <span>Legacy dev-only fake webhook</span>
                    <StatusPill>Optional</StatusPill>
                  </summary>
                  <div className="foldout-body">
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
                    </div>
                  </div>
                </details>
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
                    <dt>User</dt>
                    <dd>{session?.user.email ?? "Not signed in"}</dd>
                  </div>
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
                    <dt>Last transaction id</dt>
                    <dd>{lastTransactionId || "None"}</dd>
                  </div>
                  <div>
                    <dt>Last bank ref</dt>
                    <dd>{lastBankCreditTransferId || "None"}</dd>
                  </div>
                  <div>
                    <dt>Last share slug</dt>
                    <dd>{lastShareSlug || "None"}</dd>
                  </div>
                </dl>
              </div>

              {merchantSessionData ? (
                <div className="rail-card">
                  <p className="rail-title">Current owner session</p>
                  <dl className="detail-list">
                    <div>
                      <dt>Email</dt>
                      <dd>{merchantSessionData.email}</dd>
                    </div>
                    <div>
                      <dt>Visible accounts</dt>
                      <dd>{merchantSessionData.accounts.length}</dd>
                    </div>
                  </dl>
                </div>
              ) : null}

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
