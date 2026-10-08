# Setting up the CRB Monitor automation

These steps only need doing once, and take about 10 minutes. You can use GitHub Desktop for the files.

The monitor runs three automatic jobs:

| File | What it does | When | Keys needed |
|---|---|---|---|
| `crb-surveillance.yml` | Checks GBIF + iNaturalist for new beetle records and e-mails you an alert | every day | none |
| `crb-scan.yml` | Collects new coconut palm photos and screens them for damage | every Monday (NZ Tuesday) | `HF_TOKEN` (optional) |
| `crb-issue.yml` | Runs when you click "Send for analysis" or a review button on the page | on demand | none |

---

## Step 1 — Move the three files into `.github\workflows`

GitHub only runs automation files from a folder called `.github\workflows`.

1. In **GitHub Desktop**, open the `S-Paudel.github.io` repository and choose
   **Repository → Show in Explorer** (Ctrl+Shift+F).
2. In that window, right-click → **New → Folder** and name it `.github`.
   If Windows rejects the name, type `.github.` with a dot at the end; Windows drops the extra dot.
3. Open `.github` and create a folder inside it called `workflows`.
4. Open `crb-monitor\setup\`, select **`crb-surveillance.yml`, `crb-scan.yml` and
   `crb-issue.yml`**, press **Ctrl+X**, go to `.github\workflows\` and press **Ctrl+V**.
5. Back in GitHub Desktop, type a summary such as "Add CRB Monitor". Click
   **Commit to main**, then **Push origin**.

If the push fails with a message about **"workflow scope"**, go to **File → Options →
Accounts**, sign out, sign back in, and push again.

About two minutes later, both pages are live:
https://s-paudel.github.io/crb-surveillance.html and https://s-paudel.github.io/crb-monitor.html

---

## Step 2 — Let the jobs save their results

In GitHub Desktop, choose **Repository → View on GitHub** (Ctrl+Shift+G). Then:

1. **Settings → Actions → General.** Scroll to **Workflow permissions**, choose
   **Read and write permissions**, and click **Save**.
2. **Settings → General → Features.** Make sure **Issues** is ticked.

---

## Step 3 — Make sure alert e-mails reach you

Alerts arrive as GitHub issues titled **"[CRB alert] …"**.

1. On the repository page, click **Watch** (top right) and choose **All Activity**.
   You can also use **Custom → Issues**.
2. Check that GitHub has your preferred e-mail address under **github.com →
   Settings → Notifications → Default notifications email**.

---

## Step 4 — Run the first surveillance check

1. Open the **Actions** tab. If GitHub asks, click **I understand my workflows, go
   ahead and enable them**.
2. Click **CRB monitor — daily surveillance** → **Run workflow** → **Run workflow**.
3. It takes about a minute. A green tick means it worked. After that it runs every morning.

The page already holds a starting record of 94 beetle records, captured on
9 October 2026. From now on, anything new produces an alert.

---

## Step 5 (optional) — Turn on automatic palm-damage analysis

The weekly photo scan always collects and pre-filters new coconut palm photos. To have
it also run Aubrey Moore's damage detector, it needs access to Meta's SAM3 model:

1. Create a free account at https://huggingface.co/join.
2. Open https://huggingface.co/facebook/sam3, fill in the short access form and accept
   the licence. Approval can take from minutes to a couple of days.
3. Go to https://huggingface.co/settings/tokens → **Create new token** → type
   **Read** → **Create token**. Copy the token (it starts with `hf_`).
4. In the repository, go to **Settings → Secrets and variables → Actions → New
   repository secret**. Set **Name** to `HF_TOKEN` and paste the token into
   **Secret**, then click **Add secret**.

GitHub's free machines have no graphics card, so they analyse about 10 photos a week.
The rest wait in a queue that a GPU machine can clear (see `../README.md`).

---

## If something goes wrong

- **A run fails at "Commit results"** → Step 2.1 wasn't saved.
- **No alert e-mails** → Step 3. Also check the **Issues** tab; if an issue is there,
  only the e-mail settings need fixing.
- **The log says "detector unavailable"** → `HF_TOKEN` is missing, or SAM3 access isn't
  approved yet. Photos still get collected and wait in the queue.
- **Nothing happens after "Send for analysis"** → check that `crb-issue.yml` is in
  `.github\workflows\` (Step 1).
