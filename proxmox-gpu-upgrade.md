# Proxmox GPU Upgrade Guide

Adding a discrete GPU to the Proxmox host for local LLM inference (Ollama).

**Host:** `192.168.1.45` — Intel i9-14900K, 64 GB RAM, PVE 8.4.16
**Target consumers:** VM 111 `ollama-gpu` (Ollama inference) and/or LXC 108 `openwebui` (Ollama :11434)

---

## 1. Current state

- The i9-14900K has an iGPU (UHD Graphics 770) — fine for display/QuickSync, not for LLM inference.
- VM 111 `ollama-gpu` runs Ollama but without a discrete GPU it is CPU-bound.
- No discrete GPU is currently installed (this doc covers the upgrade).

## 2. Choosing the GPU

For Ollama, VRAM is the deciding factor — the whole model must fit in VRAM for full-speed inference.

| Card | VRAM | Runs comfortably | Notes |
|---|---|---|---|
| **RTX 5060 Ti 16GB** ⭐ | 16 GB GDDR7 | 7B–14B Q4/Q5, 24B tight | 448 GB/s bandwidth, 180 W, MSRP $429 (street ~$540 new / ~$460 used, Jul 2026) |
| RTX 4060 Ti 16GB | 16 GB | 7B–14B Q4/Q5, 24B tight | Only 288 GB/s — 5060 Ti is 56% faster for same money; skip |
| RTX 3090 (used) | 24 GB | up to 32B Q4 | Best value for 24 GB, ~350 W, check warranty |
| RTX 4090 | 24 GB | up to 32B Q4, fastest | Expensive, ~450 W, 3.5-slot |
| RTX 5090 | 32 GB | 70B Q2/Q3, 32B Q6 | Overkill unless going big |

**RTX 5060 Ti 16GB — measured Ollama numbers (Q4_K_M):**

- DeepSeek-Coder 6.7B: ~101 tok/s
- Mistral 7B: ~90 tok/s
- Llama 3.1 8B: ~75 tok/s
- Llama2 13B: ~53 tok/s / 14B-class: ~51 tok/s

Why it fits this host well: 180 W TDP means **no PSU upgrade needed** (single 8-pin, most cards are 2-slot), and LLM inference speed is bandwidth-bound — its GDDR7 gives it the throughput ceiling for the 7B–14B models that fit in 16 GB. The only reason to spend more is wanting 24B–32B models, which need a 24 GB card.

Practical checks before buying:

- **PSU**: 14900K alone can pull 250 W+. For a 3090/4090 you want **1000 W+** with the right PCIe/12VHPWR connectors. For a 4060 Ti, 750 W is fine.
- **Physical fit**: modern cards are 3+ slots and 300+ mm long — measure the case.
- **Slot**: install in the top PCIe x16 slot (CPU lanes).

NVIDIA over AMD for Ollama — CUDA support is first-class; ROCm works but is more friction.

## 3. BIOS settings

Reboot into BIOS and set:

- **VT-d (Intel Virtualization for Directed I/O)**: Enabled — required for passthrough
- **Above 4G Decoding**: Enabled
- **Resizable BAR**: Enabled
- **Primary display**: iGPU — keeps the host console on the iGPU so the discrete card is free for passthrough

## 4. Host preparation (IOMMU + VFIO)

On the Proxmox host (`ssh root@192.168.1.45`):

```bash
# 1. Enable IOMMU — PVE 8 boots via systemd-boot or GRUB depending on install.
#    GRUB: edit /etc/default/grub
GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"
# then: update-grub
#    systemd-boot: append the same flags to /etc/kernel/cmdline, then: proxmox-boot-tool refresh

# 2. Load VFIO modules
cat >> /etc/modules <<'EOF'
vfio
vfio_iommu_type1
vfio_pci
EOF

# 3. Keep host drivers off the card (VM passthrough path only)
cat > /etc/modprobe.d/blacklist-gpu.conf <<'EOF'
blacklist nouveau
blacklist nvidia
blacklist nvidiafb
EOF

update-initramfs -u -k all
reboot
```

Verify after reboot:

```bash
dmesg | grep -e DMAR -e IOMMU          # should show "IOMMU enabled"
lspci -nn | grep -i nvidia             # note the PCI ID, e.g. 01:00.0 and 01:00.1 (audio)
# Check the GPU is in its own IOMMU group:
find /sys/kernel/iommu_groups/ -type l | sort -V
```

Snapshot first, per house rules: `vzdump 111 --mode snapshot` (VM) / `pct snapshot 108 pre-gpu` (LXC) before touching configs.

## 5. Option A — Full passthrough to VM 111 (recommended)

Cleanest isolation; the VM owns the card and runs its own NVIDIA driver.

```bash
# Bind the card (video + audio function) to vfio-pci — use IDs from lspci -nn
echo "options vfio-pci ids=10de:XXXX,10de:YYYY" > /etc/modprobe.d/vfio.conf
update-initramfs -u -k all && reboot

# Attach to VM 111 (must be q35 machine type; check with: qm config 111)
qm set 111 --machine q35
qm set 111 --hostpci0 01:00,pcie=1,x-vga=0
qm start 111
```

Inside VM 111:

```bash
# Debian/Ubuntu guest
apt install nvidia-driver nvidia-cuda-toolkit   # or NVIDIA's .run installer
nvidia-smi                                      # card should appear
systemctl restart ollama
ollama run llama3.1 "hello"                     # watch nvidia-smi — VRAM should fill
```

Notes:

- Pass **all functions** of the card (`01:00` not `01:00.0`) — video + audio must move together.
- If the VM won't start with the card attached, check `journalctl -b` for IOMMU group conflicts.
- Give VM 111 more RAM if loading bigger models (currently 8 GB; model load buffers through guest RAM).

## 6. Option B — Share GPU with LXC 108 (openwebui)

If you'd rather the container's Ollama (:11434) get the GPU instead of VM 111. Driver lives on the **host**; the container borrows the device nodes. Skip the blacklist step from §4 for this path — the host needs the NVIDIA driver loaded.

```bash
# On the host
apt install pve-headers-$(uname -r)
# Install NVIDIA driver on the host (from NVIDIA .run or Debian repo)
nvidia-smi   # must work on the host first

# LXC 108 config — /etc/pve/lxc/108.conf
lxc.cgroup2.devices.allow: c 195:* rwm
lxc.cgroup2.devices.allow: c 234:* rwm
lxc.cgroup2.devices.allow: c 509:* rwm
lxc.mount.entry: /dev/nvidia0 dev/nvidia0 none bind,optional,create=file
lxc.mount.entry: /dev/nvidiactl dev/nvidiactl none bind,optional,create=file
lxc.mount.entry: /dev/nvidia-uvm dev/nvidia-uvm none bind,optional,create=file
lxc.mount.entry: /dev/nvidia-uvm-tools dev/nvidia-uvm-tools none bind,optional,create=file
```

Inside LXC 108, install the **same driver version** with `--no-kernel-module`, then `nvidia-smi` should work and Ollama picks up the GPU on restart.

You cannot do both A and B with one card — pick where Ollama should live. Recommendation: **Option A (VM 111)** — it's already named `ollama-gpu`, and point LXC 108's OpenWebUI at VM 111's Ollama endpoint instead of its local one.

## 7. Verification checklist

- [ ] `dmesg | grep IOMMU` shows enabled on host
- [ ] `nvidia-smi` works in VM 111 (or LXC 108)
- [ ] `ollama ps` shows model loaded with GPU, not `100% CPU`
- [ ] Inference speed sanity check: 7B Q4 model should hit 40+ tok/s on any card above vs ~5-10 tok/s on CPU
- [ ] OpenWebUI (192.168.1.38:8080) points at the GPU-backed Ollama endpoint
- [ ] Host still boots to console on iGPU
- [ ] Snapshots taken before changes; rollback tested: `pct rollback <id> <name>`

## 8. Gotchas specific to this host

- **local-lvm has only ~16 GB VG free** — if VM 111's disk needs to grow for model storage, don't grow it on local-lvm; models can live on an nvme-zfs-backed second disk instead.
- **PSU headroom**: 14900K + 3090-class card can spike past 800 W transiently — undervolt/power-limit the GPU (`nvidia-smi -pl 300`) costs ~5% inference speed for a lot of stability.
- Windows VMs 101/102 (MT5 bridges) share the host — schedule the reboot window around trading hours since IOMMU changes require host reboots.
