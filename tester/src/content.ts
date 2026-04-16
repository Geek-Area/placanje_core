export type DocEndpointGroup = "public" | "consumer" | "merchant" | "webhook";

export type EndpointDoc = {
  id: string;
  group: DocEndpointGroup;
  title: string;
  method: "GET" | "POST";
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
  { id: "webhook", label: "Bank webhook" },
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
      "Merchant onboarding plus organization and POS sub-accounts, where the POS account creates the payment request that later gets updated by the bank callback.",
    points: [
      "Uses form_type=ips internally.",
      "Parent organization sees child POS accounts.",
      "POS rows start as awaiting_payment and move after webhook processing.",
    ],
    defaultEndpointGroup: "merchant",
    actions: [
      { label: "Open merchant APIs", group: "merchant" },
      { label: "Open webhook API", group: "webhook" },
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
      "Webhook signature verification and transaction status updates",
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
      "Create child POS accounts under /sub-accounts",
      "POST /transactions from the selected POS account",
      "Bank or demo webhook marks the row as completed later",
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
      "A POS payment is created before the customer pays, so the bank callback has an existing record to update.",
  },
];

export const transactionFieldGlossary = [
  {
    field: "payment_ref",
    meaning: "Backend-generated reference used to correlate the payment record and bank callback.",
    whenFilled: "Always on creation",
  },
  {
    field: "form_type",
    meaning: "Internal product bucket. regular = pay slips, ips = merchant POS.",
    whenFilled: "Always on creation",
  },
  {
    field: "status",
    meaning: "Lifecycle state of the payment record.",
    whenFilled: "Always on creation, updated later",
  },
  {
    field: "merchant_account_id",
    meaning: "Links the row to a merchant organization or POS account when the flow is merchant-driven.",
    whenFilled: "Merchant POS only",
  },
  {
    field: "reference_model / reference_number",
    meaning: "Serbian payment reference data used in the IPS payload.",
    whenFilled: "Optional, but recommended",
  },
  {
    field: "bank_transaction_ref",
    meaning: "Reference echoed back by the bank or demo webhook after completion.",
    whenFilled: "Webhook-completed payments",
  },
  {
    field: "completed_at",
    meaning: "Timestamp recorded when the payment is marked as completed.",
    whenFilled: "Completed payments only",
  },
  {
    field: "qr_string",
    meaning: "Generated IPS payload string. Frontend can turn this into a visible QR image.",
    whenFilled: "Creation responses and share responses",
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
    title: "Create POS sub-account",
    method: "POST",
    path: "/v1/merchant/accounts/{account_id}/sub-accounts",
    auth: "Bearer JWT",
    description:
      "Creates the POS or store-level account under the selected organization. This POS account is the actual source of payment creation.",
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
      "Parent organizations can see child POS accounts in the merchant list endpoint.",
    ],
    testSectionId: "testing-merchant",
  },
  {
    id: "merchant-create-transaction",
    group: "merchant",
    title: "Create POS IPS transaction",
    method: "POST",
    path: "/v1/merchant/accounts/{account_id}/transactions",
    auth: "Bearer JWT",
    description:
      "Creates the merchant IPS payment request. This is the row the webhook updates later.",
    requestExample: {
      amount: "450.00",
      payment_description: "Test payment",
      reference_model: "97",
      reference_number: "12345",
    },
    responseExample: {
      transaction_id: "4e630023-7ebc-4635-af1d-b6c988f47341",
      payment_ref: "PLC-E52D9ED2B4A467BB",
      status: "awaiting_payment",
      qr_string:
        "K:PR|V:01|C:1|R:160000000000000000|N:Matija\\nTamoNegde\\nNis|I:RSD450,00|SF:289|S:Test payment|RO:9712345",
    },
    notes: [
      "Use a POS account id here, not a random user id.",
      "The frontend can render the returned qr_string immediately.",
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
      "The history becomes useful after POS creation and webhook completion.",
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
    id: "webhook-status",
    group: "webhook",
    title: "Bank IPS status callback",
    method: "POST",
    path: "/v1/webhooks/bank/{provider}/ips-status",
    auth: "Server-to-server",
    description:
      "This is not a browser endpoint. A bank integration or the tester’s fake webhook signs the payload and marks the matching payment_ref as completed.",
    requestExample: {
      headers: {
        "X-Signature": "hex-hmac-signature",
      },
      body: {
        payment_ref: "PLC-E52D9ED2B4A467BB",
        bank_transaction_ref: "BANK-DEMO-001",
        status: "completed",
        amount: "450.00",
        completed_at: "2026-04-15T00:10:00.000Z",
      },
    },
    responseExample: {
      status: "ok",
    },
    notes: [
      "The signature must match BANK_WEBHOOK_SECRET on the backend.",
      "The frontend should never expose the webhook secret.",
      "The tester can simulate this flow locally for MVP validation.",
    ],
    testSectionId: "testing-pos",
  },
];

export const frontendChecklist = [
  "Use Supabase Auth in the client, then send the returned access_token as Bearer JWT to authenticated backend endpoints.",
  "Treat qr_string as backend-generated source data. The frontend can convert it into an actual QR image client-side.",
  "Store backend base URL, Supabase URL, and publishable key as frontend config. Store BANK_WEBHOOK_SECRET only on the backend or in internal tools.",
  "For merchant flows, fetch merchant accounts first, then let the user select the organization or POS account before creating child accounts or POS payments.",
];
