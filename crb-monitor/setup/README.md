# Move these two files into `.github/workflows/`

The automated jobs are GitHub Actions workflows. They only run from the
repository's `.github/workflows/` folder, which could not be written to directly
from here. You can move them in either of these ways:

**In File Explorer:** in the `S-Paudel.github.io` folder, create a folder named
`.github`, and inside it a folder named `workflows`. Move `crb-scan.yml` and
`crb-issue.yml` into it, then commit and push. You can then delete this `setup`
folder.

**On github.com:** in the repository, choose **Add file → Create new file**. Type
`.github/workflows/crb-scan.yml` as the name, paste in the contents of
`crb-scan.yml`, and commit. Repeat for `crb-issue.yml`.
