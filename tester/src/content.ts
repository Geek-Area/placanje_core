export type DocEndpointGroup = "public" | "consumer" | "merchant" | "bank";

export type EndpointDoc = {
  id: string;
  group: DocEndpointGroup;
  title: string;
  method: "GET" | "POST" | "PUT";
  path: string;
  auth: "Public" | "Bearer JWT" | "Server-to-server";
  description: string;
  requestExample: unknown | null;
  responseExample: unknown;
  notes: string[];
  testSectionId?: string;
};

export type ProductTrack = {
  title: string;
  eyebrow: string;
  summary: string;
  points: string[];
  defaultEndpointGroup?: DocEndpointGroup;
  actions?: Array<{
    label: string;
    group?: DocEndpointGroup;
    sectionId?: string;
  }>;
};

export const endpointGroups: Array<{ id: DocEndpointGroup; label: string }> = [
  { id: "public", label: "Public pay slips" },
  { id: "consumer", label: "Consumer" },
  { id: "merchant", label: "Merchant POS" },
  { id: "bank", label: "Bank sync" },
];

export const productTracks: ProductTrack[] = [
  {
    title: "Plaćanje.RS",
    eyebrow: "Public pay slips",
    summary:
      "Anonymous or lightweight user flows for creating a pay slip, generating an IPS QR string, and sharing a public payment request.",
    points: [
      "Uses form_type=regular internally.",
      "Returns a share slug and a ready-to-render qr_string.",
      "Best for public forms, small payment requests, and link-based flows.",
    ],
    defaultEndpointGroup: "public",
    actions: [
      { label: "Open public APIs", group: "public" },
      { label: "Open consumer APIs", group: "consumer" },
    ],
  },
  {
    title: "Instant.Plaćanje.RS",
    eyebrow: "Merchant POS",
    summary:
      "Owner creates POS accounts and POS logins, and each POS can generate its own IPS QR or send request-to-pay from buyer QR data.",
    points: [
      "Uses form_type=ips internally.",
      "Owner sees the company account and its POS accounts.",
      "SKENIRAJ rows start as awaiting_payment.",
      "POKAŽI sends buyer data to the bank and returns success or failure.",
    ],
    defaultEndpointGroup: "merchant",
    actions: [
      { label: "Open merchant APIs", group: "merchant" },
      { label: "Open bank sync APIs", group: "bank" },
    ],
  },
  {
    title: "Shared transaction storage",
    eyebrow: "One backend contract",
    summary:
      "Both products write into the same payment-record history so the frontend can query one backend while the product surface stays split by use case.",
    points: [
      "Transactions are payment records, not only settled money movements.",
      "Share links and payment refs are created by the backend.",
      "The same API can power staging, admin tools, and production frontends.",
    ],
    actions: [{ label: "Open payment record model", sectionId: "docs-records" }],
  },
];

export const implementationLayers = [
  {
    title: "Frontend owns",
    tone: "warm",
    items: [
      "Supabase sign-in and sign-out in the browser",
      "Collecting form data for pay slips or POS actions",
      "Rendering qr_string as an IPS QR image if you want a visible QR",
      "Calling backend endpoints with the JWT when the flow is authenticated",
    ],
  },
  {
    title: "Backend owns",
    tone: "mint",
    items: [
      "JWT verification and account authorization",
      "Creating payment_ref, share_slug, and stored payment records",
      "Merchant hierarchy and POS account permissions",
      "Bank profile handling, QR references, and transaction status updates",
    ],
  },
];

export const flowCards = [
  {
    title: "Public Pay slips flow",
    subtitle: "No user session required",
    steps: [
      "POST /v1/public/transactions",
      "Receive share_slug, share_url, payment_ref, qr_string",
      "Render or share the pay slip page",
      "Optional: GET /v1/public/share/{slug} to hydrate the share page",
    ],
    testSectionId: "testing-public",
  },
  {
    title: "Consumer Pay slips flow",
    subtitle: "Supabase session + JWT required",
    steps: [
      "Sign in with Supabase on the client",
      "Send Bearer token to /v1/me and /v1/me/transactions",
      "Store the pay slip under the consumer profile",
      "List history with GET /v1/me/transactions",
    ],
    testSectionId: "testing-consumer",
  },
  {
    title: "Merchant POS flow",
    subtitle: "Organization owner or operator",
    steps: [
      "POST /v1/merchant/signup once for the organization",
      "Create POS accounts under /sub-accounts",
      "Attach the bank profile (bank user id + TID) to the selected POS account",
      "Use SKENIRAJ via POST /transactions or POKAŽI via POST /request-to-pay",
      "For SKENIRAJ call sync-bank-status until the bank returns a final status",
    ],
    testSectionId: "testing-merchant",
  },
];

export const statusLifecycles = [
  {
    name: "Public / consumer pay slips",
    states: ["draft", "completed later if bank confirmation exists"],
    note:
      "These start as stored payment requests. In MVP they give you a durable record plus shareable IPS payload.",
  },
  {
    name: "Merchant POS IPS",
    states: ["awaiting_payment", "completed", "expired"],
    note:
      "A POS payment is created before or during bank execution, so the backend always has a stable record to update after bank confirmation.",
  },
];

export const endpointDocs: EndpointDoc[] = [
  {
    id: "public-create",
    group: "public",
    title: "Create public pay slip",
    method: "POST",
    path: "/v1/public/transactions",
    auth: "Public",
    description:
      "Creates a stored payment request and returns the share slug plus IPS QR payload. Use this for unauthenticated pay-slip creation flows.",
    requestExample: {
      payee_name: "Maxi Pekara",
      payee_address: "Makenzijeva 12",
      payee_city: "Belgrade",
      payee_account_number: "160000000000000000",
      amount: "1500.00",
      currency: "RSD",
      payment_code: "289",
      reference_model: "97",
      reference_number: "12345",
      payment_description: "Public test",
    },
    responseExample: {
      transaction_id: "e412d6d8-839e-4525-9601-16fc5e379d95",
      payment_ref: "PLC-62F005A2F534AC49",
      share_slug: "v6bFme1IaK8",
      share_url: "https://api.example.com/v1/public/share/v6bFme1IaK8",
      qr_string:
        "K:PR|V:01|C:1|R:160000000000000000|N:Maxi Pekara\\nMakenzijeva 12\\nBelgrade|I:RSD1500,00|SF:289|S:Public test|RO:9712345",
      expires_at: "2026-05-14T23:45:43.741522Z",
      status: "draft",
    },
    notes: [
      "No JWT required.",
      "The backend stores this under form_type=regular internally.",
      "Use the returned qr_string to render the actual QR image client-side if needed.",
    ],
    testSectionId: "testing-public",
  },
  {
    id: "public-share",
    group: "public",
    title: "Read shared pay slip",
    method: "GET",
    path: "/v1/public/share/{slug}",
    auth: "Public",
    description:
      "Hydrates a public share page from the slug. This is the endpoint the share link page should call to render the stored payment request.",
    requestExample: null,
    responseExample: {
      transaction_id: "e412d6d8-839e-4525-9601-16fc5e379d95",
      payment_ref: "PLC-62F005A2F534AC49",
      form_type: "regular",
      status: "draft",
      payer_name: null,
      payee_name: "Maxi Pekara",
      payee_address: "Makenzijeva 12",
      payee_city: "Belgrade",
      payee_account_number: "160000000000000000",
      amount: "1500.00",
      currency: "RSD",
      payment_code: "289",
      reference_model: "97",
      reference_number: "12345",
      payment_description: "Public test",
      qr_string:
        "K:PR|V:01|C:1|R:160000000000000000|N:Maxi Pekara\\nMakenzijeva 12\\nBelgrade|I:RSD1500,00|SF:289|S:Public test|RO:9712345",
      expires_at: "2026-05-14T23:45:43.741522Z",
    },
    notes: [
      "The slug is the public-facing identifier, not the transaction UUID.",
      "This is the safest way to build a share page or public read-only payment page.",
    ],
    testSectionId: "testing-public",
  },
  {
    id: "consumer-profile",
    group: "consumer",
    title: "Get consumer profile",
    method: "GET",
    path: "/v1/me",
    auth: "Bearer JWT",
    description:
      "Returns the domain profile for the currently signed-in user and indicates whether they are registered as consumer and merchant.",
    requestExample: null,
    responseExample: {
      user_id: "82616ad0-e7a0-4f9c-ab91-0f5fec88fec0",
      email: "veljko.spasic@icthub.rs",
      display_name: null,
      consumer_registered: true,
      merchant_registered: true,
    },
    notes: [
      "Frontend signs in with Supabase, backend verifies the Bearer token.",
      "Useful for bootstrapping authenticated dashboards.",
    ],
    testSectionId: "testing-consumer",
  },
  {
    id: "consumer-create",
    group: "consumer",
    title: "Create consumer pay slip",
    method: "POST",
    path: "/v1/me/transactions",
    auth: "Bearer JWT",
    description:
      "Creates a pay slip under the current consumer account. Request body is the same as the public flow, but the row is linked to the signed-in user.",
    requestExample: {
      payer_name: "veljko.spasic@icthub.rs",
      payee_name: "Maxi Pekara",
      payee_address: "Makenzijeva 12",
      payee_city: "Belgrade",
      payee_account_number: "160000000000000000",
      amount: "1500.00",
      currency: "RSD",
      payment_code: "289",
      reference_model: "97",
      reference_number: "12345",
      payment_description: "Public test",
    },
    responseExample: {
      transaction_id: "c80babe1-6403-403f-bea7-37beb4b2e240",
      payment_ref: "PLC-8694BC8D02BB6326",
      share_slug: "ygytujSWUlE",
      share_url: "https://api.example.com/v1/public/share/ygytujSWUlE",
      qr_string:
        "K:PR|V:01|C:1|R:160000000000000000|N:Maxi Pekara\\nMakenzijeva 12\\nBelgrade|I:RSD1500,00|SF:289|P:veljko.spasic@icthub.rs|S:Public test|RO:9712345",
      expires_at: "2026-05-14T23:45:51.427269Z",
      status: "draft",
    },
    notes: [
      "Same creation shape as the public endpoint, but now you can also list the row from /v1/me/transactions.",
      "The tester auto-injects the signed-in email as payer_name.",
    ],
    testSectionId: "testing-consumer",
  },
  {
    id: "consumer-list",
    group: "consumer",
    title: "List consumer pay slips",
    method: "GET",
    path: "/v1/me/transactions",
    auth: "Bearer JWT",
    description:
      "Lists the authenticated user’s stored pay-slip records. This is the consumer history endpoint.",
    requestExample: null,
    responseExample: {
      items: [
        {
          id: "c80babe1-6403-403f-bea7-37beb4b2e240",
          form_type: "regular",
          status: "draft",
          payment_ref: "PLC-8694BC8D02BB6326",
          amount: "1500.00",
          currency: "RSD",
          payment_code: "289",
          payment_description: "Public test",
          payee_name: "Maxi Pekara",
          payee_account_number: "160000000000000000",
          merchant_account_id: null,
          reference_model: "97",
          reference_number: "12345",
          bank_transaction_ref: null,
          completed_at: null,
          created_at: "2026-04-14T23:45:51.380705Z",
        },
      ],
      limit: 50,
      offset: 0,
    },
    notes: [
      "Supports limit and offset query params.",
      "Use this for consumer history screens and account pages.",
    ],
    testSectionId: "testing-consumer",
  },
  {
    id: "merchant-session",
    group: "merchant",
    title: "Load current owner context",
    method: "GET",
    path: "/v1/merchant/session",
    auth: "Bearer JWT",
    description:
      "Returns the currently signed-in merchant user plus the merchant/POS accounts visible from that token.",
    requestExample: null,
    responseExample: {
      user_id: "82616ad0-e7a0-4f9c-ab91-0f5fec88fec0",
      email: "operator@example.com",
      display_name: "Operator",
      accounts: [
        {
          id: "03173421-b004-432b-9761-5a256deba118",
          account_type: "pos",
          display_name: "Lilly Shop 1",
          effective_role: "operator",
        },
      ],
    },
    notes: [
      "Use this after login if the frontend needs a single bootstrapping call.",
      "This is the plain answer to: who is logged in and what can they see?",
    ],
    testSectionId: "testing-auth",
  },
  {
    id: "merchant-logout",
    group: "merchant",
    title: "Log out owner session",
    method: "POST",
    path: "/v1/merchant/logout",
    auth: "Bearer JWT",
    description:
      "Revokes the current authenticated session through Supabase-backed logout. Use it when the current device should be logged out now.",
    requestExample: null,
    responseExample: {
      status: "revoked",
      scope: "global",
    },
    notes: [
      "This is about the user's login session, not about bank tokens or invite tokens.",
      "The tester also clears the browser session after this call.",
    ],
    testSectionId: "testing-auth",
  },
  {
    id: "merchant-signup",
    group: "merchant",
    title: "Create merchant organization",
    method: "POST",
    path: "/v1/merchant/signup",
    auth: "Bearer JWT",
    description:
      "Creates the top-level merchant organization account for the signed-in owner.",
    requestExample: {
      display_name: "Lilly",
      payee_name: "Gary",
      payee_account_number: "160000000000000000",
      payee_address: "Sveti Sava",
      payee_city: "Belgrade",
    },
    responseExample: {
      id: "900449ba-bf80-4763-86df-dfb8ea512456",
      parent_account_id: null,
      account_type: "organization",
      slug: "lilly-738987",
      display_name: "Lilly",
      payee_name: "Gary",
      payee_account_number: "160000000000000000",
      payee_address: "Sveti Sava",
      payee_city: "Belgrade",
      active: true,
      effective_role: "owner",
    },
    notes: [
      "Run this once per merchant organization.",
      "The caller becomes the owner of this account tree.",
    ],
    testSectionId: "testing-merchant",
  },
  {
    id: "merchant-sub-account",
    group: "merchant",
    title: "Create POS account",
    method: "POST",
    path: "/v1/merchant/accounts/{account_id}/sub-accounts",
    auth: "Bearer JWT",
    description:
      "Creates the POS or store-level account under the selected organization.",
    requestExample: {
      display_name: "Lilly Shop 1",
      payee_name: "Matija",
      payee_account_number: "160000000000000000",
      payee_address: "TamoNegde",
      payee_city: "Nis",
    },
    responseExample: {
      id: "03173421-b004-432b-9761-5a256deba118",
      parent_account_id: "900449ba-bf80-4763-86df-dfb8ea512456",
      account_type: "pos",
      slug: "lilly-shop-1-411ac2",
      display_name: "Lilly Shop 1",
      payee_name: "Matija",
      payee_account_number: "160000000000000000",
      payee_address: "TamoNegde",
      payee_city: "Nis",
      active: true,
      effective_role: "admin",
    },
    notes: [
      "POS stands for Point of Sale.",
      "Owner accounts can see POS accounts in the merchant list endpoint.",
    ],
    testSectionId: "testing-merchant",
  },
  {
    id: "merchant-create-transaction",
    group: "merchant",
    title: "Create SKENIRAJ merchant QR transaction",
    method: "POST",
    path: "/v1/merchant/accounts/{account_id}/transactions",
    auth: "Bearer JWT",
    description:
      "Creates the merchant-side IPS QR payment request. This is the SKENIRAJ flow where the customer scans the merchant QR and the backend later syncs the bank status.",
    requestExample: {
      amount: "450.00",
      payment_description: "Test payment",
      reference_model: "97",
      reference_number: "12345",
    },
    responseExample: {
      transaction_id: "4e630023-7ebc-4635-af1d-b6c988f47341",
      payment_ref: "PLC-E52D9ED2B4A467BB",
      bank_credit_transfer_identificator: "TID1234526106000001",
      status: "awaiting_payment",
      qr_string:
        "K:PT|V:01|C:1|R:160000000000000000|N:Matija\\nTamoNegde\\nNis|I:RSD450,00|SF:221|M:5411|RP:TID1234526106000001|S:Test payment",
    },
    notes: [
      "Use a POS account id here, not a random user id.",
      "The frontend can render the returned qr_string immediately.",
      "This is not a public PR pay-slip QR. It is a merchant IPS QR.",
    ],
    testSectionId: "testing-pos",
  },
  {
    id: "merchant-list-transactions",
    group: "merchant",
    title: "List POS or organization transactions",
    method: "GET",
    path: "/v1/merchant/accounts/{account_id}/transactions",
    auth: "Bearer JWT",
    description:
      "Returns transaction history for the selected merchant account.",
    requestExample: null,
    responseExample: {
      items: [],
      limit: 50,
      offset: 0,
    },
    notes: [
      "Supports limit and offset query params.",
      "The history becomes useful after POS creation and later bank completion or failure.",
    ],
    testSectionId: "testing-pos",
  },
  {
    id: "merchant-stats",
    group: "merchant",
    title: "Get account stats",
    method: "GET",
    path: "/v1/merchant/accounts/{account_id}/stats",
    auth: "Bearer JWT",
    description:
      "Summarizes counts and completed amount for a merchant account.",
    requestExample: null,
    responseExample: {
      account_id: "03173421-b004-432b-9761-5a256deba118",
      total_transactions: 0,
      completed_transactions: 0,
      awaiting_payment_transactions: 0,
      expired_transactions: 0,
      total_completed_amount: "0.00",
    },
    notes: [
      "Counts will stay zero until there are stored rows for that account.",
      "Useful for POS dashboards and owner overview screens.",
    ],
    testSectionId: "testing-pos",
  },
  {
    id: "bank-profile",
    group: "bank",
    title: "Attach bank profile to POS account",
    method: "PUT",
    path: "/v1/merchant/accounts/{account_id}/bank-profile",
    auth: "Bearer JWT",
    description:
      "Stores the bank-side identity for the selected POS account: provider, bank username, and TID.",
    requestExample: {
      provider: "banca_intesa",
      bank_user_id: "merchant_user_from_bank",
      terminal_identificator: "TID12345",
    },
    responseExample: {
      merchant_account_id: "03173421-b004-432b-9761-5a256deba118",
      provider: "banca_intesa",
      bank_user_id: "merchant_user_from_bank",
      terminal_identificator: "TID12345",
      active: true,
    },
    notes: [
      "Plain English: this is how the backend knows which bank POS identity belongs to this shop.",
      "Without this, SKENIRAJ sync and POKAŽI requestToPay cannot call the bank.",
    ],
    testSectionId: "testing-merchant",
  },
  {
    id: "bank-sync-status",
    group: "bank",
    title: "Sync SKENIRAJ transaction status with bank",
    method: "POST",
    path: "/v1/merchant/accounts/{account_id}/transactions/{transaction_id}/sync-bank-status",
    auth: "Bearer JWT",
    description:
      "Calls the bank POS backend checkCTStatus endpoint for the selected SKENIRAJ transaction and updates the local row with the newest bank status.",
    requestExample: null,
    responseExample: {
      id: "4e630023-7ebc-4635-af1d-b6c988f47341",
      payment_ref: "PLC-E52D9ED2B4A467BB",
      status: "completed",
      bank_status_code: "00",
      bank_status_description: "executed",
      bank_credit_transfer_identificator: "TID1234526106000001",
    },
    notes: [
      "Use this only for SKENIRAJ merchant QR flow.",
      "Status 82 means the bank still does not know the final outcome, so call it again after a short delay.",
    ],
    testSectionId: "testing-pos",
  },
  {
    id: "bank-request-to-pay",
    group: "bank",
    title: "Send POKAŽI requestToPay",
    method: "POST",
    path: "/v1/merchant/accounts/{account_id}/request-to-pay",
    auth: "Bearer JWT",
    description:
      "Accepts buyer-side QR data such as debtor account and OTP, then forwards requestToPay to the bank and stores the resulting merchant transaction row.",
    requestExample: {
      amount: "450.00",
      debtor_account_number: "340000000000000001",
      one_time_code: "123456",
      debtor_reference: "kupac-ref-1",
      debtor_name: "Petar Petrovic",
      debtor_address: "Nemanjina 1",
      payment_purpose: "Racun 15",
    },
    responseExample: {
      id: "9ef4b155-e9e0-43f9-9872-f8efcdb00d11",
      payment_ref: "PLC-DF9D10D11AFDB610",
      status: "completed",
      bank_status_code: "00",
      bank_status_description: "executed",
      bank_credit_transfer_identificator: "TID1234526106000002",
    },
    notes: [
      "Use this for POKAŽI only, not for merchant QR.",
      "In plain English: customer shows their QR, backend sends the bank request immediately, and the answer is success or failure.",
    ],
    testSectionId: "testing-pos",
  },
];

export const frontendChecklist = [
  "Use Supabase Auth in the client, then send the returned access_token as Bearer JWT to authenticated backend endpoints.",
  "Treat qr_string as backend-generated source data. The frontend can convert it into an actual QR image client-side.",
  "Store backend base URL, Supabase URL, and publishable key as frontend config. Store bank credentials and any webhook secret only on the backend or in internal tools.",
  "For merchant flows, fetch merchant accounts first, then let the user select the organization or POS account before creating child accounts or bank-driven POS payments.",
];
