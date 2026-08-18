# Nested Proxmox on the HP server (th2 USB flow)

This is the **outer-host** stage of the th2 USB installation. The flow is:

```
HP server  ──USB──▶  Proxmox VE (outer host)
                         └── nested Proxmox VE (VM, this script)
                                 └── VPN-for-mobile service (../vpn-mobile)
```

1. The th2 USB installs Proxmox VE on the HP server (the *outer* host).
2. `nested-proxmox-setup.sh` carves out a **Proxmox-inside-Proxmox** VM.
3. Inside that nested node you run [`../vpn-mobile`](../vpn-mobile) so it serves
   the mobile SSH/SSL-tunnel configs.

## Why nested

Running Proxmox inside a Proxmox VM lets you keep the VPN service fully isolated
(its own cluster, snapshots, backups) without dedicating separate hardware. The
inner node can still run its own KVM guests because the script enables **nested
virtualization** and gives the VM CPU type `host`.

## Requirements (outer host)

- Proxmox VE already installed on the HP server (`qm` available).
- CPU virtualization enabled in BIOS (Intel VT-x / AMD-V).
- The Proxmox VE installer ISO uploaded to a storage, e.g.
  `local:iso/proxmox-ve_8.iso` (Datacenter → Storage → ISO Images → Upload).
- Enough RAM/disk for a second Proxmox (>= 8 GB RAM, >= 64 GB disk recommended).

## Usage

Run on the HP server as root. **Review first with `--dry-run`:**

```bash
./nested-proxmox-setup.sh --iso local:iso/proxmox-ve_8.iso --dry-run
```

Then create it for real (and start it):

```bash
./nested-proxmox-setup.sh \
  --iso local:iso/proxmox-ve_8.iso \
  --vmid 9000 --name nested-pve \
  --cores 4 --mem 8192 --disk 64 \
  --storage local-lvm --bridge vmbr0 \
  --start
```

| Option | Default | Meaning |
|--------|---------|---------|
| `--iso` | *(required)* | Proxmox VE installer ISO volume id |
| `--vmid` | `9000` | VM id for the nested node |
| `--name` | `nested-pve` | VM name |
| `--cores` | `4` | vCPUs |
| `--mem` | `8192` | RAM (MB) |
| `--disk` | `64` | system disk (GB) |
| `--storage` | `local-lvm` | storage for the VM disk |
| `--bridge` | `vmbr0` | network bridge |
| `--start` | off | start the VM after creating |
| `--dry-run` | off | print `qm` commands without running |

## What the script does

1. **Enables nested virtualization** — writes `options kvm-intel nested=1`
   (or `kvm-amd`) and reloads the module. If VMs are running and the module is
   busy, it tells you to reboot the host to activate it.
2. **Creates the VM** with `--cpu host`, UEFI (OVMF), q35 machine, a virtio-scsi
   system disk, a NIC on your bridge, and the installer ISO as a CD-ROM, booting
   from CD first.

It stops there — booting the VM and running the Proxmox installer is
interactive, so you finish that in the console.

## After the inner Proxmox is installed

1. Give the inner node an IP on your `vmbr0` network during install.
2. Clone this repo inside the inner node and run the mobile VPN setup:

   ```bash
   git clone <this-repo>
   sh 3/vpn-mobile/autorun-usb.sh
   ```

That generates the importable mobile VPN configs (see
[`../vpn-mobile/README.md`](../vpn-mobile/README.md)) from the nested node.

## Notes / gotchas

- Nested KVM is for **labs**; performance is lower than bare metal and it is not
  a supported production topology.
- If `qm start` complains about `vmx`/`svm` not present in the guest, the host
  reboot to activate `nested=1` was skipped — reboot and retry.
- Three levels deep (VMs inside the *inner* Proxmox) also works because the inner
  VM inherits CPU `host`, but expect further performance loss.
