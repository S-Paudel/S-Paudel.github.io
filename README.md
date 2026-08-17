# sulav-paudel-website

A single-page personal site — Personal / Professional / Community — built as
plain HTML, CSS and JS (no build step, no Jekyll), ready to host free on
GitHub Pages at a short URL.

## What's in here

```
index.html      the whole page (hero + Personal + Professional + Community + Contact)
style.css       all styling (design tokens at the top if you want to change colors/fonts)
script.js       mobile nav toggle, footer year, scroll-reveal, CV-link check
assets/
  favicon.svg   small tab icon
  (add Sulav_Paudel_CV.pdf here — see "Add your CV" below)
.nojekyll        tells GitHub Pages to skip the Jekyll build (not needed for a plain site)
```

---

## 1. Get your short URL live (GitHub Pages)

Your GitHub username is `S-Paudel`, so your free short URL will be:

```
https://s-paudel.github.io
```

Steps:

1. **Create a new repository** on GitHub named **exactly**:
   ```
   S-Paudel.github.io
   ```
   This exact name (`<username>.github.io`) is what makes GitHub serve it at
   the root short URL instead of `s-paudel.github.io/reponame`. Make it
   **Public**. Don't initialise it with a README (you're uploading one).

2. **Upload these files** to the repository. Easiest way if you don't use git
   day-to-day: on the repo page, click **"Add file" → "Upload files"**, drag
   in `index.html`, `style.css`, `script.js`, `.nojekyll`, and the whole
   `assets` folder, then commit directly to `main`.

   Or, from a terminal, if you have git installed:
   ```bash
   cd path/to/this/folder
   git init
   git add .
   git commit -m "Initial site"
   git branch -M main
   git remote add origin https://github.com/S-Paudel/S-Paudel.github.io.git
   git push -u origin main
   ```

3. **Turn on Pages**: in the repo, go to **Settings → Pages**. Under
   "Build and deployment", set **Source** to **"Deploy from a branch"**,
   branch **`main`**, folder **`/ (root)`**. Save.

4. Wait 1–2 minutes, then visit **https://s-paudel.github.io** — it should
   be live. GitHub also shows the live URL at the top of the Pages settings
   page once it's deployed.

5. Any time you edit a file and push/upload again, the site rebuilds
   automatically within a minute or two.

---

## 2. (Optional) Add a real custom domain later

If you ever want e.g. `sulavpaudel.com` instead of the `.github.io` address:

1. Buy the domain from any registrar (Namecheap, Google Domains successor,
   etc.).
2. In the registrar's DNS settings, add either:
   - an **A record** pointing `@` to GitHub's Pages IPs (`185.199.108.153`,
     `.109.153`, `.110.153`, `.111.153`), or
   - a **CNAME record** pointing `www` to `s-paudel.github.io`.
3. In your repo, **Settings → Pages → Custom domain**, enter your domain and
   save — GitHub creates a `CNAME` file in the repo automatically and
   provisions free HTTPS for you.

This is entirely optional — `s-paudel.github.io` is a perfectly good
permanent short URL on its own.

---

## 3. Add your CV

The hero button links to `assets/Sulav_Paudel_CV.pdf`, which doesn't exist
yet — Export your CV as a PDF, name it
exactly `Sulav_Paudel_CV.pdf`, and drop it into the `assets` folder (upload
via the GitHub web UI, same as step 2 above). The link will start working
immediately — no code changes needed.

---

## 4. What I built from real, public sources — and what's still a placeholder

Everything in **Professional** (timeline, publications, research focus) 

## 5. Editing later

Everything is plain HTML/CSS — no build tools required. Open `index.html`
in any text editor, find the section you want to change (look for the
`<!-- ============ SECTION ============ -->` comments), and edit the text
directly. Colors, fonts and spacing all live at the top of `style.css`
under `:root{ ... }` if you want to adjust the palette.
