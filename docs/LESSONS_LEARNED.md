# Lessons learned

Mistakes and surprises from building and testing Opacra, each with the rule that stops it
happening again. Newest first. Read this before a release, a drill or a launch step.

## 26 Oct 2026: testnet 3 launch day

Launched at 20:00 SAST (18:00 UTC) as planned; everything below was fixed the same evening.

| What went wrong | Why | Rule from now on |
|---|---|---|
| The PC pulled an old bundle, and the site page was first built from an old copy | Windows saved the new downloads as `opacra-v026 (1).bundle` and `opacra-site-v15 (1).html` next to older files with the same names | Every file sent for a release gets a unique, dated name; check its size or hash before using it |
| A stage name typed into a command ran into the next line, and the downloads came back empty | Pasting a value and a command block together on a server terminal | When Claude already knows a value, put it into the commands; otherwise set it alone on one line and `echo` it before use. `wget` without `-q`, so a 404 shows |
| Seed 1's node stopped at start: "Failed to store HTTP SSL cert/key" | The runbook re-created `/var/lib/opacra/testnet3` as root (`install -d` for the explorer's `lmdb` folder), so the node, running as `opacra`, could not write its RPC certificate there | Create node data folders owned by `opacra` (`install -d -o opacra -g opacra` on the network folder itself), and test the install steps exactly as the runbook gives them |
| Both seeds ignored the new DNS records until restarted | They first asked at T, before the records existed, and the node's resolver kept that "no such record" answer | Restart the seeds once the records answer (`dig`), and check `dns_checkpoint_serial`; next release: cap how long the node remembers a "no record" answer |
| The Windows launcher refused every new wallet's address and closed | The wallet writes the address with no line ending; `findstr /x` only matches a line that ends in one. The launcher test only used short addresses ending in CRLF | Test with the real artifact (a real wallet's file), not a stand-in. Fixed and the zip re-issued that evening |
| The seeds' alert kept saying "checkpoints unreadable" after they had accepted the records | The node logs nothing when the only record is block 0, so the alert script, which reads the log, never saw a recovery | Next release: log the first successful read of each set. Until the first daily checkpoint, check `dns_checkpoint_serial` instead |
| "What serial number?" at the busiest moment | The step said "the number from `date +%s`" instead of giving it | At launch steps, give exact values, not instructions to make them |

## 25 Oct 2026: review of the 24 Oct update

| What went wrong | Why | Rule from now on |
|---|---|---|
| The 24 Oct fix let a node lift an emergency checkpoint by itself when the record went missing, and a replayed older DNS answer counts as missing | I tested a withdrawal, not what else could look like one. DNSSEC proves an answer was signed, not that it is current | When a change lets a node undo a protection on its own, ask what an attacker can make it see (replays, stale data, outages) and test that too. Fixed: records carry a serial and older ones are refused |
| The first serial check read the number with `>>`, which accepts `-1` as the largest possible value, and saved it: one bad record would have locked every node out for good. It also accepted the same serial with different records | I tested replays (lower serials), not malformed, oversized or equal ones | Anything a node reads from outside and keeps (DNS, files, peers) is checked strictly for format and range before it is saved, and every "refuse X" rule is tested with X's edge cases: negative, huge, equal, duplicated |
| The serial was saved as accepted before the conflict check, so a set the node ignored came back after a restart, failed, and left it with no checkpoints | "Accepted" was decided in one place and "in force" in another | Record state as accepted only where it actually takes effect, and test restarts after every refusal path |
| Testing a node booted with its clock 3 days behind showed Monero's pool drops every transaction then: its age is "now − receive time" in unsigned numbers | Upstream code assumes the clock never goes backwards | Every age or interval computed from the clock must handle a clock that goes backwards (treat a future time as age 0) |
| I fixed that one case, told the reviewer the guard copied an unaffected `get_transaction_stats` (it came from `get_transaction_backlog`; `get_transaction_stats` had the same flaw and crashed the node from one RPC call), and suggested reporting it to Monero, whose development branch had already fixed both. The DNS refresh had the same flaw too | I fixed the instance the test found and didn't sweep for the pattern or check upstream's current code | When a bug class turns up, grep every instance (`now -`, `time(NULL) -`) and fix or clear each one, and read upstream's development branch before saying anything about upstream |
| A test ran a new daemon with a three-week-old wallet from the same folder, and every build's version line named an older commit | Only the daemon had been rebuilt in `build/release`; Monero stamps the commit when `cmake` configures, not at each build | Build daemon and wallets together, re-run `cmake` before the test gate, and set `BIN=` explicitly |
| A test node banned 127.0.0.1, and with it the test's own RPC calls, while waiting for its first block | A new wallet's block requests fail until block 1 exists; Monero bans an IP after 3 failed requests | Test nodes that a fresh wallet talks to run with `--disable-rpc-ban` |
| The 3-node functional test was cut off by a one-hour limit while still mining, and left its three nodes running | It mines at real difficulty (about an hour to block 121), and it didn't catch SIGTERM, so its cleanup never ran | Every test catches SIGTERM and stops what it started; give the functional test 3 hours |
| My note to the reviewer gave four test counts one too high (6 checks reported as 7, and so on) | My gate script counted lines containing "PASS", which also matched each test's "ALL CHECKS PASSED" line | Count only the check lines (`PASS ` / `FAIL ` at the start of a line), or take the number from the test's own summary |
| A test wrote `checkpoints.json` into `testnet/`; the node reads `testnet3/` | I assumed Monero's folder name | Find data folders from what the node created (its `lmdb` folder), never by assumed names |
| After a restart the node held no DNS checkpoints until DNS answered, so a refused or missing answer would have lifted an emergency checkpoint | The DNS set lived only in memory | Protections that must survive an outage must also survive a restart: save them and restore them at startup |
| A note to a reviewer credited him with advice he hadn't given (launchers enforcing), and it reversed a decision | Two review texts arrived a day apart, and I didn't track which said what | Keep each reviewer's report and advice in its own file, and quote the report when citing it |
| I recommended that home miners enforce checkpoints, assuming a wrong record can be withdrawn in minutes | True for a typo, false for a hijacked registrar account, where the attacker controls what is published | Judge a recovery step by the worst case it must handle, not the common one |

## 24 Oct 2026: second independent audit, upstream sync

| What went wrong | Why | Rule from now on |
|---|---|---|
| Opacra was 97 commits behind Monero, including security fixes (P2P, parsers, mempool, wallet, reserve proofs) | Nobody checked upstream after the fork | Every month and before every release: `git log <last synced>..upstream/release-v0.18` (in a full clone, not the shallow repository), then apply or explicitly decline each commit |
| Resolving a conflict with "take upstream's version" (`git checkout --theirs`) nearly replaced Opacra's DNS servers and probe host with Monero's | `--theirs` takes the whole file, not just the conflicting lines | Resolve only the conflict markers; after each resolution, diff the file against the last Opacra commit and check every Opacra change is still there |
| Upstream moved the "too far in the future" check into a shared function, which on Opacra would have hard-rejected side-chain blocks before proof of work and blamed the peer | A clean-looking upstream refactor met an Opacra rule in the same function | When upstream touches a function Opacra changed, list Opacra's rules for it and rerun the tests that cover them (block_rules_test for timestamps) |
| `install-alerts.sh` ended silently with exit code 2 on a server with no alerts yet | `set -e -o pipefail` and a filename pattern that matched nothing | Test setup scripts on a fresh server as well as an existing one (stubbed systemctl/apt) |
| The full functional test ran against a 13-day-old v0.2.1 build and failed the new fund-marking check | Its default was `build/release`, while today's build was in `build/portable`; the log printed the folder but not the version. The "no ring member is a fund output" check passed anyway, because an old node marks nothing | Tests pick the newest build and print its version first; check that line before reading results. Every "none found" check needs a partner check proving the thing can be found |
| The rerun of the full test talked to the first run's old wallet programs and failed the decoy check | The first run stopped at a failed check without shutting down its wallet programs; the rerun's new ones could not take the ports, and nothing noticed | Test scripts stop everything they started on any exit, refuse to start when their ports are taken, and check their own processes are still running |
| The explorer bundle had no `main` branch, so `git pull <bundle> main` failed on the PC | It was made with `git bundle create … f8b1939..HEAD`, which stores only `HEAD` | Bundle the branch by name (`… <base>..main`) and check with `git bundle list-heads` before sending |
| I told the advisor a wrong DNS checkpoint would only stall miners for minutes; it deleted every block above it on every enforcing node | Monero's checkpoint rollback throws the removed blocks away, and I described the effect without reading the rollback code or testing a withdrawal | Before stating what a failure costs, read the code path and test it end to end (the record published, then withdrawn). Fixed: the blocks are kept and restored |
| A test read the chain tip with `get_last_block_header` and got an empty answer | That call answers BUSY on a node that is not synchronised, and a node with no peers never is | In tests of lone nodes, read blocks by height; check every RPC answer's `status` |
| A launch runbook started the seeds while DNS still held testnet 2's checkpoint, which they would have kept enforcing | Runbook order, plus Monero's keep-until-restart behaviour | Delete old records before launch day; add new records after the seeds start. From v0.2.6 nodes follow DNS without a restart |

## 23 Oct 2026: release candidate v0.2.5

| What went wrong | Why | Rule from now on |
|---|---|---|
| On testnet 3's genesis day, `make_genesis.py verify` failed: "The node did not start" | The code still held the practice genesis as testnet's checkpoint at block 0, and since 18 Oct testnet loads its built-in checkpoints, so the new genesis failed it. The practice run on 18 Oct came before that change | `make_genesis.py apply` removes the network's old checkpoints (a new genesis makes them all wrong). After any change to start-up or checkpoint code, rerun the genesis procedure end to end |
| The testnet 3 runbook still published the downloads and pushed the genesis to GitHub 90 minutes before mining opened, after the mainnet runbook had been fixed | The two runbooks were updated separately after the review, and the rehearsal one was missed | A rehearsal follows the real day's order exactly. When one runbook changes, check the other the same day |

## 19 Oct 2026: independent review fixes

| What went wrong | Why | Rule from now on |
|---|---|---|
| The launch checklist said to publish the genesis hash and the release a week before mining opened | Nobody asked what someone could do with the genesis in that week: mine a private chain and take over at launch | Anything that reveals the genesis (source, binaries, hash, a running seed, the DNS record) stays private until the launch minute. The coin now also refuses blocks dated before the launch time |
| An emergency checkpoint at block 1 or 2 would have crashed or misled every enforcing node | Monero's rollback (`height - 2`) wraps around below 2; Monero never checkpoints such low heights | Test every safety tool at the edges (block 1, block 2, the first minutes), not only in the middle of a chain |
| `save-side-chain` and `make_checkpoint.sh` worked on whatever node answered, testnet or mainnet | Defaults pointed at the testnet port | Emergency tools take the network explicitly and check the node is on it before printing anything to publish |
| The Windows launcher's address check from v0.2.2 had quietly gone when the launcher was rewritten | Rewrites dropped an earlier fix with no test to catch it | When rewriting a script, list the fixes the old one carried and keep each; batch-file checks are tested on real Windows (wine's `findstr` gives wrong answers) |
| The functional test was stopped at the 1-hour limit just before it finished, and had to be run again | The limit was guessed, not measured: the test mines 110 blocks at the startup difficulty, over an hour on a small machine | Give a long test a limit well above its measured run time (the functional test: 2 hours), and check the time a test took last time before starting it |
| Open review findings were nearly written into public repository docs | Writing up fixes and open items in one pass | Public files describe fixes only. Open findings stay in the private project docs until fixed. Before each commit, search the diff for finding IDs |

## 18 Oct 2026 (afternoon): release-candidate checks

| What went wrong | Why | Rule from now on |
|---|---|---|
| Testnet never loaded its built-in checkpoints or `checkpoints.json`; only DNS checkpoints worked there | Inherited from Monero: the daemon loads them on mainnet only | Fixed: testnet loads both like mainnet. Before calling a testnet "mainnet rules", search the code for every `TESTNET`/`MAINNET` branch |
| `save-side-chain restore` could not put the seed back on the honest chain | A checkpoint rolls a node back 2 blocks below the split; the saved file started at the split | `save` keeps the 10 shared blocks below the split too; `restore` checks every block became the tip, since `submit_block` answers "OK" for blocks it only stores |
| Hetzner support said no to nodes, builds and tests on its servers (written reply, 18 Oct) | Its terms ban crypto nodes, even with mining off | Before putting anything crypto on a host, get the host's answer in writing. Hetzner keeps only the website and downloads; seeds run at Contabo, whose policy allows nodes |
| Making the GitHub repo public showed "pushed by InvoiceSA" on its early-October pushes | Those pushes were made from another GitHub account, before the opacra-dev account existed; GitHub keeps who pushed in the Actions and activity history, and it can't be edited | The repo was recreated and the history pushed again as opacra-dev; the old one is private as `opacra-old`. Push only with `github-opacra` (check with `ssh -T github-opacra`), and look at a repo's Actions and activity pages before making it public |
| The first public CI build failed at its last step, packaging | `package_release.sh` had only ever been run with no argument; the workflow passes the relative folder `dist`, and one step runs tar from a temporary folder, so the path broke. The workflow was committed "untested until its first run" | Run every script and workflow step exactly as it will be called (same arguments, from the same folder, into a clean output folder) before handing it over. Fixed in 66410c1; build #2 passed both jobs |
| The rehearsal network died mid-run | The workspace restarted | Long runs keep their data on disk and can be resumed; check `uptime` when every node is suddenly down |

## 18 Oct 2026: attack and recovery rehearsal

| What went wrong | Why | Rule from now on |
|---|---|---|
| The emergency guide's checkpoint choice ("newest honest block, 5 below the tip") leaves enforcing nodes stalled after an attack has landed | A node rolls back only 2 blocks below a failed checkpoint and refuses side blocks below a checkpoint, so the attacker's earlier blocks stay and the honest ones can't come back | After a landed attack, checkpoint the first honest block after the split. Save the honest blocks first (`save-side-chain save`). Guide updated |
| The guide's first draft of a save command would have saved the attacker's blocks | Asking a node for blocks by height returns its current (attacker's) chain | Side-chain blocks are fetched by hash from `get_alternate_chains`; the tool does this and was tested on regtest |
| A checkpoint alone does not keep the honest chain going | Home miners don't enforce DNS checkpoints by default, so they stay on the attacker's chain; seeds don't mine | Decided 18 Oct: the launchers enforce DNS checkpoints |
| Seeds block honest home nodes that relayed the attacker's chain, for 24 hours | A checkpoint mismatch counts as misbehaviour | Done 18 Oct: 10-minute block, no scoring; rehearsed the same afternoon |
| Test results counted "OK" that were really "BUSY" | The script checked for errors, not the `status` field | Check the status field of every RPC answer, not just the absence of an error |

## 13–14 Oct 2026: v0.2.4 release preparation

| What went wrong | Why | Rule from now on |
|---|---|---|
| The full three-node functional test failed one check: block 1's difficulty | Since v0.1.3 block 1 costs 10,000 (security audit fix), but the test's Python reference was never updated, because the full test was not re-run after v0.1.3. The chain and opacra-audit were right; the test was stale. | Run the full functional test (`contrib/testnet/functional_test.py`) before every release, and after any consensus change in the same commit. |
| The site's Linux command could check an old download if run twice | `wget -q` saves a second copy as `.tar.gz.1`, and the hash check then reads the first file. | Download commands write to a fixed name (`wget -qO <file> <url>`). |
| A test package built before the final commit still contained `__pycache__` | It was built from the working tree before the fix landed. | Release files are always built from a clean, committed tree; check the tarball's file list before signing. |
| The seed's phone alerts kept saying "emergency checkpoints unreadable" after v0.2.4 fixed them | The alert script's pattern for `DNS checkpoint enforced` expected the hash without the `<...>` brackets the node prints, so it never saw the line. Its test used a hand-written line, not one copied from a real log. | Test log-reading code against lines copied from a real node log. After a release, check `opacra-alert status` agrees with the node's log. |
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
