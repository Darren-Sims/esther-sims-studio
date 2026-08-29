# Punch list

Outstanding items for the Esther Sims Studio admin app / site integration.

## Privacy policy (esthersimsstudio.co.uk/resources/privacy-policy)

- [ ] **Retention wording** — update the "Data Retention" section to describe
      the actual delete-vs-anonymize split: pure leads (no commission) are
      deleted after 3 years; clients with a commission are anonymized
      instead, with their invoices kept longer for UK tax record-keeping.
      The current wording ("securely deletes or anonymizes it") is vague
      about which applies when.
- [ ] **Sub-processors disclosure** — add a "Who We Share Your Information
      With" section naming Neon (database hosting, London/eu-west-2) and
      Render (app hosting, Frankfurt) alongside Webflow, since the contact
      form now feeds data into both.
- [ ] **Contact form fields** — the "Direct Submissions" section is generic;
      name the actual fields captured (name, email, commission request,
      whether they have a UK postal address, how they heard about the
      studio, gift voucher interest) and state the purpose (managing
      commission enquiries).
- [ ] **"Payment details" claim** — the policy says payment details are
      collected directly, but nothing in the app or contact form actually
      captures client card/payment info (invoices are settled by bank
      transfer using the studio's own details). Confirm this is accurate
      or remove/adjust it.

## Infrastructure

- [ ] **Render auto-deploy isn't firing on git push** — every deploy so far
      has needed a manual trigger via the Render API/dashboard after
      pushing to `main`. Check the GitHub↔Render connection under
      Settings → Build & Deploy on the Render dashboard.
- [ ] **Webflow integration shows unauthorized (401)** in this session even
      after reconnecting — likely needs a fresh session to pick up the
      new auth grant. Needed to inspect/manage the site (forms, webhooks,
      pages) via API instead of the dashboard.
- [ ] **Render free tier cold starts** — the live demo spins down after
      inactivity and takes ~30-50s to wake on the next request. Consider
      upgrading to a paid `starter` plan (~$7/mo) if this matters for
      live client demos.
