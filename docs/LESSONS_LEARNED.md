# Lessons learned

Mistakes and surprises from building and testing Opacra, each with the rule that stops it
happening again. Newest first. Read this before a release, a drill or a launch step.

## 13–14 Oct 2026: v0.2.4 release preparation

| What went wrong | Why | Rule from now on |
|---|---|---|
| The full three-node functional test failed one check: block 1's difficulty | Since v0.1.3 block 1 costs 10,000 (security audit fix), but the test's Python reference was never updated, because the full test was not re-run after v0.1.3. The chain and opacra-audit were right; the test was stale. | Run the full functional test (`contrib/testnet/functional_test.py`) before every release, and after any consensus change in the same commit. |
| The site's Linux command could check an old download if run twice | `wget -q` saves a second copy as `.tar.gz.1`, and the hash check then reads the first file. | Download commands write to a fixed name (`wget -qO <file> <url>`). |
| A test package built before the final commit still contained `__pycache__` | It was built from the working tree before the fix landed. | Release files are always built from a clean, committed tree; check the tarball's file list before signing. |
| Claude's `pkill -f` matched its own shell again (exit 144) | Same mistake as 12 Oct: the pattern appears in the command line that runs pkill. | Never use `pkill -f`/`pgrep -f` with a pattern typed in the same command; use `pgrep -x <name>` or a PID. |

## 12 Oct 2026: emergency checkpoint drill, payment tests

| What went wrong | Why | Rule from now on |
|---|---|---|
| No Opacra node could validate DNS emergency checkpoints from 11 Oct | The internet's DNSSEC root key changed on 11 Oct 2026 (KSK-2024, tag 38696) and the code, inherited from Monero, only trusted the old key (20326). Fixed in v0.2.4 (commit db37dec). | Track outside changes the coin depends on (root DNSSEC keys, OS libraries, Windows rules) in the launch checklist. After every release and every month, check the seed's log says `DNS checkpoint enforced`; treat the "emergency checkpoints unreadable" phone alert as urgent. |
| The seed's DNS fallback list was out of date | Five public DNS servers hard-coded by Monero years ago; some are unreliable now. | The seed sets `DNS_PUBLIC=tcp://1.1.1.1` (systemd drop-in `/etc/systemd/system/opacrad.service.d/dns.conf`). Replace the built-in list in a later release. |
| The seed log filled 100 MB a day with `bad_weak_ptr` error traces since 6 Oct, unnoticed | The node logs a full trace for every dropped peer connection, even when it handles it. Harmless, but it hides real problems and wastes disk. | Quieter logging in v0.2.4. Look at the seed's log size and newest lines at each audit. |
| During the drill, Claude blamed a "crash" on the new checkpoint before checking | The error storm happened to be visible at the same time. The log showed it had been going on since 6 Oct. | Before naming a cause: check when the symptom started, and whether the thing blamed actually happened (here, the seed had never enforced the checkpoint). Say "possible cause" until the evidence is in. |
| The first fund payment never left; the wallet showed the fee but nothing was sent | The final `Y` did not register, and the output was not read. | A payment counts only when the wallet prints "Transaction successfully submitted" with an ID. Check the receiving side with `show_transfers in`. |
| A wallet password was typed at the wallet's command prompt, in plain text | The red "Password needed (output received)" message invites people to type the password straight away. | Type passwords only when the wallet asks "Wallet password:" or "Enter password". Clearer message in v0.2.4. |
| Wallet passwords got mixed up (testnet fund, pc2, testnet-wallet) | Several wallets, several passwords, none labelled. | Every saved password is labelled with its wallet file name and machine, kept with the USB backups. |
| Testers' Windows laptop refused the unsigned program | Windows 11 Smart App Control blocks unsigned programs, with no "run anyway". | Never turn Smart App Control off. Testers on such machines use Linux/WSL until releases are signed (SignPath first, Certum as fallback, before mainnet). |

## 11 Oct 2026: alerts and chain audit

| What went wrong | Why | Rule from now on |
|---|---|---|
| A git bundle could not be pulled ("couldn't find remote ref main") | The bundle was made from a commit range without naming the branch. | Make bundles with `git bundle create <file> <base>..main`, and check with `git bundle list-heads` that `refs/heads/main` is in it. |
| The first alert script ignored thresholds already agreed in the security plan | It was built from scratch without rereading the plan. | Before building anything, read the matching plan document and follow what it already decided. |
| ntfy.sh e-mail alerts were planned but no longer work without an account | The service changed its rules. | Check a service's current documentation before building on it. |
| The CPU of the spare test PC reached 95 °C while mining | Old machine, half the CPU threads by default. | Default miner threads become a quarter in v0.2.4; check temperatures in the first hour on any new machine. |

## 10–11 Oct 2026: launch and testnet 2

| What went wrong | Why | Rule from now on |
|---|---|---|
| A lone node answered BUSY to mining | A node only mines once a peer reports at least its own height. | Launch with at least two connected seeds; start a lone node with `--offline`. Recorded in `LAUNCH_CHECKLIST.md`. |
| Checkpoints were read only when a block arrived | Inherited Monero behaviour. | Fixed in v0.2.1: re-read every 5 minutes. |
| Testers were asked to install XMRig on Windows; Defender blocked it | Every XMRig build is flagged as unwanted software. | Testers use the one-click launcher; keep instructions to "download, unzip, double-click". |
